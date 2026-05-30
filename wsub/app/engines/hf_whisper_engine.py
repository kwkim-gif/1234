from __future__ import annotations

from typing import Generator

from app.engines.base_engine import BaseWhisperEngine
from app.models.settings import AppSettings


class HFWhisperEngine(BaseWhisperEngine):
    """HuggingFace Transformers 기반 Whisper 엔진 (kotoba-whisper, anime-whisper 등)."""

    def __init__(self) -> None:
        self._pipeline = None
        self._model_name: str = ""

    def load_model(self, model_name: str, settings: AppSettings) -> None:
        """HuggingFace 파이프라인으로 모델을 로드합니다."""
        import torch
        from transformers import pipeline

        device = 0 if (settings.device in ("auto", "cuda") and torch.cuda.is_available()) else -1

        self._pipeline = pipeline(
            "automatic-speech-recognition",
            model=model_name,
            device=device,
            torch_dtype=torch.float16 if device >= 0 else torch.float32,
        )
        self._model_name = model_name

    def transcribe(
        self,
        audio_path: str,
        language: str | None,
        settings: AppSettings,
    ) -> Generator[dict, None, None]:
        """오디오를 전사하여 세그먼트를 yield합니다."""
        if self._pipeline is None:
            raise RuntimeError("모델이 로드되지 않았습니다.")

        lang = None if language == "auto" else language
        generate_kwargs: dict = {}
        if lang:
            generate_kwargs["language"] = lang

        result = self._pipeline(
            audio_path,
            return_timestamps=True,
            generate_kwargs=generate_kwargs,
        )

        chunks = result.get("chunks", [])
        for i, chunk in enumerate(chunks):
            ts = chunk.get("timestamp", (0.0, 0.0))
            start = ts[0] if ts[0] is not None else 0.0
            end = ts[1] if ts[1] is not None else start + 2.0
            yield {"start": start, "end": end, "text": chunk["text"].strip()}

    def unload_model(self) -> None:
        """모델을 메모리에서 해제합니다."""
        self._pipeline = None

    def is_loaded(self) -> bool:
        return self._pipeline is not None
