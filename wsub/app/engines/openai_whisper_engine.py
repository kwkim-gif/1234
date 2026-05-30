from __future__ import annotations

from typing import Generator

from app.engines.base_engine import BaseWhisperEngine
from app.models.settings import AppSettings


class OpenAIWhisperEngine(BaseWhisperEngine):
    """openai-whisper 기반 전사 엔진."""

    def __init__(self) -> None:
        self._model = None
        self._model_name: str = ""

    def load_model(self, model_name: str, settings: AppSettings) -> None:
        """openai-whisper 모델을 로드합니다."""
        import whisper

        short_name = model_name.split("/")[-1]
        if short_name.startswith("whisper-"):
            short_name = short_name[len("whisper-"):]

        device = self._resolve_device(settings.device)
        self._model = whisper.load_model(short_name, device=device)
        self._model_name = model_name

    def transcribe(
        self,
        audio_path: str,
        language: str | None,
        settings: AppSettings,
    ) -> Generator[dict, None, None]:
        """오디오를 전사하여 세그먼트를 yield합니다."""
        if self._model is None:
            raise RuntimeError("모델이 로드되지 않았습니다.")

        lang = None if language == "auto" else language
        ws = settings.whisper

        result = self._model.transcribe(
            audio_path,
            language=lang,
            temperature=ws.temperature,
            beam_size=ws.beam_size,
            best_of=ws.best_of,
            no_speech_threshold=ws.no_speech_threshold,
            compression_ratio_threshold=ws.compression_ratio_threshold,
            condition_on_previous_text=ws.condition_on_previous_text,
            word_timestamps=ws.word_timestamps,
        )

        for seg in result.get("segments", []):
            yield {"start": seg["start"], "end": seg["end"], "text": seg["text"].strip()}

    def unload_model(self) -> None:
        """모델을 메모리에서 해제합니다."""
        self._model = None

    def is_loaded(self) -> bool:
        return self._model is not None

    @staticmethod
    def _resolve_device(device: str) -> str:
        if device == "auto":
            try:
                import torch
                return "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                return "cpu"
        return device
