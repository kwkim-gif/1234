from .base_engine import BaseWhisperEngine
from .faster_whisper_engine import FasterWhisperEngine
from .openai_whisper_engine import OpenAIWhisperEngine
from .hf_whisper_engine import HFWhisperEngine

HF_MODEL_IDS = {"kotoba-tech/kotoba-whisper-v2.0", "litagin/anime-whisper"}


def create_engine(engine_name: str, model_id: str) -> BaseWhisperEngine:
    """엔진 이름과 모델 ID에 따라 적절한 엔진 인스턴스를 반환합니다."""
    if model_id in HF_MODEL_IDS:
        return HFWhisperEngine()
    if engine_name == "faster-whisper":
        return FasterWhisperEngine()
    if engine_name == "openai-whisper":
        return OpenAIWhisperEngine()
    return FasterWhisperEngine()


__all__ = [
    "BaseWhisperEngine", "FasterWhisperEngine",
    "OpenAIWhisperEngine", "HFWhisperEngine",
    "create_engine",
]
