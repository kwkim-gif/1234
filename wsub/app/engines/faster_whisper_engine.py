from __future__ import annotations

import os
from typing import Generator

from app.engines.base_engine import BaseWhisperEngine
from app.models.settings import AppSettings

# Windows 심볼릭 링크 권한 오류(WinError 1314) 방지
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")


class FasterWhisperEngine(BaseWhisperEngine):
    """faster-whisper 기반 전사 엔진."""

    # faster-whisper 내장 모델명 매핑 (HuggingFace ID → 내장 모델 식별자)
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

    def __init__(self) -> None:
        self._model = None
        self._model_name: str = ""

    def load_model(self, model_name: str, settings: AppSettings) -> None:
        """faster-whisper 모델을 로드합니다."""
        from faster_whisper import WhisperModel

        device = self._resolve_device(settings.device)
        # RTX 5000 시리즈는 float16, 구형 GPU나 CPU는 int8
        compute_type = "float16" if device == "cuda" else "int8"

        # 내장 모델이면 짧은 이름으로, 그 외(HF Hub 모델)는 전체 ID 사용
        model_id = self._BUILTIN_MODELS.get(model_name, model_name)

        try:
            self._model = WhisperModel(
                model_id,
                device=device,
                compute_type=compute_type,
                # Windows symlink 권한 오류 방지: 심볼릭 링크 대신 파일 복사 사용
                local_files_only=False,
            )
        except Exception as e:
            # CUDA 초기화 실패 시 CPU로 폴백
            if device == "cuda":
                self._model = WhisperModel(model_id, device="cpu", compute_type="int8")
            else:
                raise
        self._model_name = model_name

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
        """모델을 메모리에서 해제합니다."""
        self._model = None

    def is_loaded(self) -> bool:
        return self._model is not None

    @staticmethod
    def _resolve_device(device: str) -> str:
        """사용 가능한 장치를 결정합니다. ctranslate2 기준으로 CUDA 감지."""
        if device != "auto":
            return device
        # ctranslate2(faster-whisper 백엔드)로 CUDA 직접 감지 — torch 불필요
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
