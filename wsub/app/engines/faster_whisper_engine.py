from __future__ import annotations

import os
import traceback
from typing import Generator

from app.engines.base_engine import BaseWhisperEngine
from app.models.settings import AppSettings

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

# ctranslate2 compute type 우선순위: CUDA 사용 가능 여부와 DLL 상태에 따라 순차 시도
_CUDA_COMPUTE_FALLBACK = ["float16", "int8_float16", "int8"]
_CPU_COMPUTE_TYPE = "int8"

# faster-whisper 내장 모델 ID 매핑
_BUILTIN_MODELS: dict[str, str] = {
    "openai/whisper-tiny":           "tiny",
    "openai/whisper-base":           "base",
    "openai/whisper-small":          "small",
    "openai/whisper-medium":         "medium",
    "openai/whisper-large-v1":       "large-v1",
    "openai/whisper-large-v2":       "large-v2",
    "openai/whisper-large-v3":       "large-v3",
    "openai/whisper-large-v3-turbo": "large-v3-turbo",
}


class FasterWhisperEngine(BaseWhisperEngine):
    """faster-whisper 기반 전사 엔진."""

    def __init__(self) -> None:
        self._model = None
        self._model_name: str = ""
        self._actual_device: str = "cpu"

    def load_model(self, model_name: str, settings: AppSettings) -> None:
        """faster-whisper 모델을 로드합니다. CUDA DLL 오류 시 자동으로 CPU/int8로 폴백합니다."""
        from faster_whisper import WhisperModel

        device = _resolve_device(settings.device)
        model_id = _BUILTIN_MODELS.get(model_name, model_name)

        if device == "cuda":
            self._model = _load_with_cuda_fallback(WhisperModel, model_id)
        else:
            self._model = WhisperModel(model_id, device="cpu", compute_type=_CPU_COMPUTE_TYPE)

        self._model_name = model_name
        self._actual_device = device

    def transcribe(
        self,
        audio_path: str,
        language: str | None,
        settings: AppSettings,
    ) -> Generator[dict, None, None]:
        """오디오를 전사하여 세그먼트를 실시간으로 yield합니다."""
        if self._model is None:
            raise RuntimeError("모델이 로드되지 않았습니다.")

        lang = None if language == "auto" else language
        ws = settings.whisper

        segments, _ = self._model.transcribe(
            audio_path,
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

        for seg in segments:
            yield {"start": seg.start, "end": seg.end, "text": seg.text.strip()}

    def unload_model(self) -> None:
        self._model = None

    def is_loaded(self) -> bool:
        return self._model is not None


# ── 모듈 레벨 헬퍼 ────────────────────────────────────────────────────────

def _resolve_device(device: str) -> str:
    """사용 가능한 장치를 결정합니다. ctranslate2 기준으로 CUDA를 우선 감지합니다."""
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


def _load_with_cuda_fallback(WhisperModel, model_id: str):
    """CUDA compute type을 순차적으로 시도하고, 모두 실패하면 CPU로 폴백합니다."""
    last_error: Exception | None = None

    for compute_type in _CUDA_COMPUTE_FALLBACK:
        try:
            model = WhisperModel(model_id, device="cuda", compute_type=compute_type)
            return model
        except Exception as e:
            err_str = str(e).lower()
            # DLL / 라이브러리 오류면 다음 compute type 시도
            if any(kw in err_str for kw in ("cublas", "cudnn", "dll", "cannot be loaded",
                                              "not found", "cublaslt")):
                last_error = e
                continue
            # 그 외 오류(모델 파일 없음 등)는 즉시 재발생
            raise

    # 모든 CUDA compute type 실패 → CPU 폴백
    try:
        model = WhisperModel(model_id, device="cpu", compute_type=_CPU_COMPUTE_TYPE)
        return model
    except Exception as cpu_err:
        # CPU도 실패하면 원래 CUDA 오류를 포함해 발생
        raise RuntimeError(
            f"CUDA 로드 실패 ({last_error})\n"
            f"CPU 폴백도 실패: {cpu_err}\n\n"
            "해결 방법: CUDA 12.x 재설치 또는 장치를 CPU로 변경하세요."
        ) from cpu_err
