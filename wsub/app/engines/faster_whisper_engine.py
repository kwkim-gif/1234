from __future__ import annotations

import os
import traceback
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
        self._log = lambda msg: None  # 워커가 주입하는 로그 콜백

    def set_logger(self, log_fn) -> None:
        self._log = log_fn

    def load_model(self, model_name: str, settings: AppSettings) -> None:
        from app.core.cuda_setup import register_cuda_dll_dirs
        register_cuda_dll_dirs(log=self._log)  # cublas/cudnn DLL 등록+preload (faster_whisper import 전)
        from faster_whisper import WhisperModel

        requested_device = _resolve_device(settings.device)
        model_id = _BUILTIN_MODELS.get(model_name, model_name)
        self._log(f"[장치] 요청={settings.device} → 해석={requested_device}")

        if requested_device == "cuda":
            model, device, compute_type = _load_cuda_with_fallback(
                WhisperModel, model_id, self._log
            )
        else:
            model = WhisperModel(model_id, device="cpu", compute_type=_CPU_COMPUTE)
            device, compute_type = "cpu", _CPU_COMPUTE

        self._model = model
        self._device = device
        self._compute_type = compute_type
        self._model_name = model_name

        if device == "cuda":
            self._log(f"[GPU] ✅ CUDA 사용 중 (compute_type={compute_type})")
        else:
            self._log("[GPU] ⚠️ CPU로 동작 중 — GPU 가속이 적용되지 않았습니다.")

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

        # 할루시네이션 억제 프리셋 적용 (모델바 드롭다운에서 선택)
        hall = _hallucination_params(getattr(settings, "hallucination_level", "medium"))

        transcribe_kwargs = dict(
            language=lang,
            temperature=ws.temperature,
            beam_size=ws.beam_size,
            best_of=ws.best_of,
            no_speech_threshold=ws.no_speech_threshold,
            compression_ratio_threshold=ws.compression_ratio_threshold,
            condition_on_previous_text=hall.get(
                "condition_on_previous_text", ws.condition_on_previous_text
            ),
            word_timestamps=ws.word_timestamps,
            vad_filter=hall.get("vad_filter", ws.vad_filter),
            repetition_penalty=hall["repetition_penalty"],
            no_repeat_ngram_size=hall["no_repeat_ngram_size"],
        )
        if hall["hallucination_silence_threshold"] > 0:
            transcribe_kwargs["hallucination_silence_threshold"] = (
                hall["hallucination_silence_threshold"]
            )

        try:
            yield from self._do_transcribe(audio_path, transcribe_kwargs)
        except RuntimeError as e:
            if _is_cublas_error(e) and self._device == "cuda":
                # cublas 오류 → CPU로 모델 재로드 후 재시도
                self._log(f"[GPU] 전사 중 cublas 오류 → CPU로 전환: {e}")
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

def _hallucination_params(level: str) -> dict:
    """할루시네이션 억제 레벨을 faster-whisper 파라미터로 변환합니다.

    무음 구간에서 동일 문장이 반복되는 현상을 repetition_penalty와
    no_repeat_ngram_size, hallucination_silence_threshold로 억제합니다.
    """
    presets = {
        "off": {
            "repetition_penalty": 1.0,
            "no_repeat_ngram_size": 0,
            "hallucination_silence_threshold": 0.0,
        },
        "weak": {
            "repetition_penalty": 1.1,
            "no_repeat_ngram_size": 3,
            "hallucination_silence_threshold": 0.0,
        },
        "medium": {
            "repetition_penalty": 1.2,
            "no_repeat_ngram_size": 2,
            "hallucination_silence_threshold": 2.0,
            "condition_on_previous_text": False,
            "vad_filter": True,
        },
        "strong": {
            "repetition_penalty": 1.3,
            "no_repeat_ngram_size": 2,
            "hallucination_silence_threshold": 1.0,
            "condition_on_previous_text": False,
            "vad_filter": True,
        },
    }
    return presets.get(level, presets["medium"])


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


def _load_cuda_with_fallback(WhisperModel, model_id: str, log=lambda m: None):
    """
    CUDA compute type을 순서대로 시도합니다.
    모두 실패하면 CPU로 폴백합니다.
    cublas 오류는 전사 시점에 별도로 처리됩니다.
    반환값: (model, device, compute_type)
    """
    for compute_type in _CUDA_COMPUTE_ORDER:
        try:
            model = WhisperModel(model_id, device="cuda", compute_type=compute_type)
            return model, "cuda", compute_type
        except Exception as e:
            log(f"[GPU] CUDA 로드 실패 (compute_type={compute_type}): {e}")
            if not _is_cublas_error(e):
                raise

    # 모든 CUDA 시도 실패 → CPU 폴백
    log("[GPU] 모든 CUDA compute_type 실패 → CPU로 폴백합니다. "
        "reinstall_cuda_run.bat 으로 CUDA 12 라이브러리를 재설치하세요.")
    model = WhisperModel(model_id, device="cpu", compute_type=_CPU_COMPUTE)
    return model, "cpu", _CPU_COMPUTE
