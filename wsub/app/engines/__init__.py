from .base_engine import BaseWhisperEngine
from .faster_whisper_engine import FasterWhisperEngine
from .openai_whisper_engine import OpenAIWhisperEngine
from .hf_whisper_engine import HFWhisperEngine

# transformers 파이프라인이 필요한 모델 (CTranslate2 포맷 미지원)
HF_ONLY_MODEL_IDS: set[str] = set()


def create_engine(engine_name: str, model_id: str) -> BaseWhisperEngine:
    """엔진 이름과 모델 ID에 따라 적절한 엔진 인스턴스를 반환합니다."""
    if model_id in HF_ONLY_MODEL_IDS:
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
