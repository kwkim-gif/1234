from __future__ import annotations

from typing import Callable, Generator

from app.engines.base_engine import BaseWhisperEngine
from app.models.settings import AppSettings


class HFWhisperEngine(BaseWhisperEngine):
    """HuggingFace Transformers 기반 Whisper 엔진 (anime-whisper 등 safetensors 포맷)."""

    def __init__(self) -> None:
        self._pipeline = None
        self._model_name: str = ""
        self._log: Callable[[str], None] = lambda msg: None

    def set_logger(self, log_fn: Callable[[str], None]) -> None:
        self._log = log_fn

    def load_model(self, model_name: str, settings: AppSettings) -> None:
        """HuggingFace 파이프라인으로 모델을 로드합니다. CUDA 실패 시 CPU로 폴백합니다."""
        import torch
        from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline

        device = _resolve_device(settings.device)
        self._log(f"[HF 엔진 로드] {model_name} / device={device}")

        try:
            self._pipeline = _load_pipeline(
                model_name, device,
                AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline, torch,
                log=self._log,
            )
        except Exception as e:
            self._log(f"[HF 엔진 로드 실패] {e}")
            raise

        self._model_name = model_name
        self._log(f"[HF 모델 로드 완료] {model_name}")

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

        self._log(f"[HF 전사 시작] {audio_path}")
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
        if self._pipeline is not None:
            try:
                import torch
                model = getattr(self._pipeline, "model", None)
                if model is not None:
                    model.cpu()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                pass
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


def _load_pipeline(model_name, device, AutoModel, AutoProcessor, pipeline_fn, torch, log=None):
    """CUDA로 먼저 시도하고, CUDA 관련 오류가 발생하면 CPU로 폴백합니다."""
    if log is None:
        log = lambda m: None

    def _build(dev: str):
        dtype = torch.float16 if dev == "cuda" else torch.float32
        log(f"[HF] 모델 다운로드/로드 중 (device={dev}, dtype={dtype}) ...")
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
            log(f"[HF] CUDA 로드 실패 → CPU로 폴백: {e}")
            return _build("cpu")
        raise
