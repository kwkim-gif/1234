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
        from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline

        device = self._resolve_device(settings.device)
        dtype = torch.float16 if device == "cuda" else torch.float32

        # 모델과 프로세서를 명시적으로 로드하여 안정성 향상
        model = AutoModelForSpeechSeq2Seq.from_pretrained(
            model_name,
            torch_dtype=dtype,
            low_cpu_mem_usage=True,
            use_safetensors=True,
        )
        model.to(device)
        processor = AutoProcessor.from_pretrained(model_name)

        self._pipeline = pipeline(
            "automatic-speech-recognition",
            model=model,
            tokenizer=processor.tokenizer,
            feature_extractor=processor.feature_extractor,
            torch_dtype=dtype,
            device=device,
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

        # 긴 오디오 처리를 위해 chunk 단위로 분할
        result = self._pipeline(
            audio_path,
            return_timestamps=True,
            chunk_length_s=30,
            stride_length_s=5,
            generate_kwargs=generate_kwargs,
        )

        chunks = result.get("chunks", [])
        if not chunks and result.get("text"):
            # 청크가 없으면 전체 텍스트를 단일 세그먼트로 반환
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
        """모델을 메모리에서 해제합니다."""
        self._pipeline = None

    def is_loaded(self) -> bool:
        return self._pipeline is not None

    @staticmethod
    def _resolve_device(settings_device: str) -> str:
        if settings_device not in ("auto", "cuda"):
            return settings_device
        try:
            import torch
            return "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            return "cpu"
