from __future__ import annotations

import os
import traceback
import numpy as np
from typing import Generator

from app.engines.base_engine import BaseWhisperEngine
from app.models.settings import AppSettings

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

_BUILTIN_MODELS: dict[str, str] = {
    "openai/whisper-tiny":           "tiny",
    "openai/whisper-base":           "base",
    "openai/whisper-small":          "small",
    "openai/whisper-medium":         "medium",
    "openai/whisper-large-v1":       "large-v1",
    "openai/whisper-large-v2":       "large-v2",
    "openai/whisper-large-v3":       "large-v3",
    "openai/whisper-large-v3-turbo": "large-v3-turbo",
    # Kotoba faster 버전 (CTranslate2 포맷 → faster-whisper 직접 사용 가능)
    "kotoba-tech/kotoba-whisper-v2.0-faster": "kotoba-tech/kotoba-whisper-v2.0-faster",
}

# CUDA compute type 시도 순서
_CUDA_COMPUTE_ORDER = ["float16", "int8_float16", "int8"]
_CPU_COMPUTE = "int8"


class FasterWhisperEngine(BaseWhisperEngine):
    """faster-whisper / CTranslate2 기반 전사 엔진."""

    def __init__(self) -> None:
        self._model = None
        self._model_name: str = ""
        self._device: str = "cpu"
        self._compute_type: str = _CPU_COMPUTE

    def load_model(self, model_name: str, settings: AppSettings) -> None:
        """모델을 로드합니다. 더미 추론으로 cublas 오류를 사전에 감지하여 폴백합니다."""
        from faster_whisper import WhisperModel

        requested_device = _resolve_device(settings.device)
        model_id = _BUILTIN_MODELS.get(model_name, model_name)

        if requested_device == "cuda":
            model, device, compute_type = _load_cuda_with_probe(WhisperModel, model_id)
        else:
            model = WhisperModel(model_id, device="cpu", compute_type=_CPU_COMPUTE)
            device, compute_type = "cpu", _CPU_COMPUTE

        self._model = model
        self._device = device
        self._compute_type = compute_type
        self._model_name = model_name

    def transcribe(
        self,
        audio_path: str,
        language: str | None,
        settings: AppSettings,
    ) -> Generator[dict, None, None]:
        """오디오를 전사합니다. 추론 중 cublas 오류 발생 시 CPU로 재시도합니다."""
        if self._model is None:
            raise RuntimeError("모델이 로드되지 않았습니다.")

        lang = None if language == "auto" else language
        ws = settings.whisper

        transcribe_kwargs = dict(
            language=lang,
            temperature=ws.temperature,
            beam_size=ws.beam_size,
            best_of=ws.best_of,
            no_speech_threshold=ws.no_speech_threshold,
            compression_ratio_threshold=ws.compression_ratio_threshold,
            condition_on_previous_text=ws.condition_on_previous_text,
            word_timestamps=ws.word_timestamps,
            vad_filter=ws.vad_filter,
        )

        try:
            yield from self._do_transcribe(audio_path, transcribe_kwargs)
        except RuntimeError as e:
            if _is_cublas_error(e) and self._device == "cuda":
                # cublas 오류 → CPU로 모델 재로드 후 재시도
                self._reload_on_cpu()
                yield from self._do_transcribe(audio_path, transcribe_kwargs)
            else:
                raise

    def _do_transcribe(self, audio_path: str, kwargs: dict) -> Generator[dict, None, None]:
        segments, _ = self._model.transcribe(audio_path, **kwargs)
        for seg in segments:
            yield {"start": seg.start, "end": seg.end, "text": seg.text.strip()}

    def _reload_on_cpu(self) -> None:
        """현재 모델을 CPU로 재로드합니다."""
        from faster_whisper import WhisperModel
        model_id = _BUILTIN_MODELS.get(self._model_name, self._model_name)
        self._model = WhisperModel(model_id, device="cpu", compute_type=_CPU_COMPUTE)
        self._device = "cpu"
        self._compute_type = _CPU_COMPUTE

    def unload_model(self) -> None:
        self._model = None

    def is_loaded(self) -> bool:
        return self._model is not None


# ── 모듈 레벨 헬퍼 ────────────────────────────────────────────────────────

def _resolve_device(device: str) -> str:
    if device != "auto":
        return device
    try:
        import ctranslate2
        if ctranslate2.get_cuda_device_count() > 0:
            return "cuda"
    except Exception:
        pass
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
    except ImportError:
        pass
    return "cpu"


def _is_cublas_error(e: Exception) -> bool:
    msg = str(e).lower()
    return any(k in msg for k in ("cublas", "cublaslt", "cudnn", "dll", "cannot be loaded"))


def _probe_model(model) -> bool:
    """더미 오디오로 실제 추론을 실행해 cublas DLL 오류를 사전 감지합니다."""
    try:
        dummy = np.zeros(16000, dtype=np.float32)
        segments, _ = model.transcribe(dummy, language="en", beam_size=1, best_of=1,
                                        temperature=0, vad_filter=False)
        list(segments)  # generator를 완전히 소비하여 실제 추론 실행
        return True
    except Exception:
        return False


def _load_cuda_with_probe(WhisperModel, model_id: str):
    """
    CUDA compute type을 순서대로 시도하고, 더미 추론으로 검증합니다.
    모두 실패하면 CPU로 폴백합니다.
    반환값: (model, device, compute_type)
    """
    last_error: str = ""

    for compute_type in _CUDA_COMPUTE_ORDER:
        try:
            model = WhisperModel(model_id, device="cuda", compute_type=compute_type)
            # 로드 성공 → 더미 추론으로 실제 CUDA 동작 검증
            if _probe_model(model):
                return model, "cuda", compute_type
            # 더미 추론 실패 (반환값은 True/False) → 다음 compute type 시도
            last_error = f"CUDA probe failed (compute_type={compute_type})"
        except Exception as e:
            last_error = str(e)
            if not _is_cublas_error(e):
                # 모델 파일 없음 등 DLL 무관 오류는 즉시 재발생
                raise

    # 모든 CUDA 시도 실패 → CPU 폴백
    model = WhisperModel(model_id, device="cpu", compute_type=_CPU_COMPUTE)
    return model, "cpu", _CPU_COMPUTE
