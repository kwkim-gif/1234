from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generator

from app.models.settings import AppSettings


class BaseWhisperEngine(ABC):
    """모든 Whisper 엔진이 구현해야 할 추상 인터페이스."""

    @abstractmethod
    def load_model(self, model_name: str, settings: AppSettings) -> None:
        """모델을 메모리에 로드합니다."""
        ...

    @abstractmethod
    def transcribe(
        self,
        audio_path: str,
        language: str | None,
        settings: AppSettings,
    ) -> Generator[dict, None, None]:
        """오디오를 전사하여 세그먼트를 실시간으로 yield합니다.

        Yields:
            dict with keys: start (float), end (float), text (str)
        """
        ...

    @abstractmethod
    def unload_model(self) -> None:
        """모델을 메모리에서 해제합니다."""
        ...

    def is_loaded(self) -> bool:
        """모델이 로드되어 있는지 확인합니다."""
        return False
