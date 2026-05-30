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
        """HuggingFace 파이프라인으로 모델을 로드합니다. CUDA 실패 시 CPU로 폴백합니다."""
        import torch
        from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline

        device = _resolve_device(settings.device)

        self._pipeline = _load_pipeline(
            model_name, device, AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline, torch
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

        lang = None if (not language or language == "auto") else language
        generate_kwargs: dict = {"task": "transcribe"}
        if lang:
            generate_kwargs["language"] = lang

        result = self._pipeline(
            audio_path,
            return_timestamps=True,
            chunk_length_s=30,
            stride_length_s=5,
            generate_kwargs=generate_kwargs,
        )

        chunks = result.get("chunks", [])
        if not chunks and result.get("text"):
            yield {"start": 0.0, "end": 0.0, "text": result["text"].strip()}
            return

        for chunk in chunks:
            ts = chunk.get("timestamp", (0.0, 0.0))
            start = ts[0] if ts[0] is not None else 0.0
            end = ts[1] if ts[1] is not None else start + 2.0
            text = chunk["text"].strip()
            if text:
                yield {"start": start, "end": end, "text": text}

    def unload_model(self) -> None:
        self._pipeline = None

    def is_loaded(self) -> bool:
        return self._pipeline is not None


# ── 모듈 레벨 헬퍼 ────────────────────────────────────────────────────────

def _resolve_device(settings_device: str) -> str:
    if settings_device not in ("auto", "cuda"):
        return settings_device
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


def _load_pipeline(model_name, device, AutoModel, AutoProcessor, pipeline_fn, torch):
    """CUDA로 먼저 시도하고, CUDA 관련 오류가 발생하면 CPU로 폴백합니다."""

    def _build(dev: str):
        dtype = torch.float16 if dev == "cuda" else torch.float32
        model = AutoModel.from_pretrained(
            model_name,
            torch_dtype=dtype,
            low_cpu_mem_usage=True,
        )
        model.to(dev)
        processor = AutoProcessor.from_pretrained(model_name)
        return pipeline_fn(
            "automatic-speech-recognition",
            model=model,
            tokenizer=processor.tokenizer,
            feature_extractor=processor.feature_extractor,
            torch_dtype=dtype,
            device=dev,
        )

    try:
        return _build(device)
    except Exception as e:
        err_str = str(e).lower()
        if device == "cuda" and any(
            kw in err_str for kw in ("cublas", "cuda", "dll", "not found", "out of memory")
        ):
            # CUDA 관련 오류 → CPU 폴백
            return _build("cpu")
        raise
