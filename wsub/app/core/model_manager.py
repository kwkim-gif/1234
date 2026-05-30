from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Callable

from app.config.constants import SUPPORTED_MODELS
from app.models.model_info import ModelInfo, ModelState


class ModelManager:
    """HuggingFace Hub 기반 모델 다운로드, 삭제, 캐시 관리."""

    def __init__(self) -> None:
        self._models: dict[str, ModelInfo] = {
            m["id"]: ModelInfo(id=m["id"], name=m["name"], size_gb=m["size_gb"])
            for m in SUPPORTED_MODELS
        }
        self._refresh_states()

    def list_models(self) -> list[ModelInfo]:
        """지원 모델 목록을 반환합니다."""
        return list(self._models.values())

    def get_model(self, model_id: str) -> ModelInfo | None:
        return self._models.get(model_id)

    def is_downloaded(self, model_id: str) -> bool:
        """모델이 로컬에 다운로드되어 있는지 확인합니다."""
        info = self._models.get(model_id)
        return info is not None and info.state == ModelState.DOWNLOADED

    def download_model(
        self,
        model_id: str,
        progress_callback: Callable[[float], None] | None = None,
    ) -> None:
        """HuggingFace Hub에서 모델을 다운로드합니다."""
        from huggingface_hub import snapshot_download

        info = self._models.get(model_id)
        if not info:
            raise ValueError(f"알 수 없는 모델: {model_id}")

        info.state = ModelState.DOWNLOADING

        def _hf_progress(transferred: int, total: int) -> None:
            if total > 0 and progress_callback:
                progress_callback(transferred / total)

        local_dir = snapshot_download(repo_id=model_id)
        info.local_path = local_dir
        info.state = ModelState.DOWNLOADED
        if progress_callback:
            progress_callback(1.0)

    def delete_model(self, model_id: str) -> None:
        """로컬에 저장된 모델 캐시를 삭제합니다."""
        info = self._models.get(model_id)
        if not info or not info.local_path:
            return
        path = Path(info.local_path)
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)
        info.local_path = ""
        info.state = ModelState.NOT_DOWNLOADED

    def change_cache_dir(self, new_dir: str) -> None:
        """HuggingFace 캐시 디렉토리를 변경합니다."""
        os.environ["HF_HOME"] = new_dir

    def _refresh_states(self) -> None:
        """로컬 캐시를 확인하여 모델 상태를 갱신합니다."""
        try:
            from huggingface_hub import scan_cache_dir
            cache_info = scan_cache_dir()
            cached_ids = {repo.repo_id for repo in cache_info.repos}
            for model_id, info in self._models.items():
                if model_id in cached_ids:
                    info.state = ModelState.DOWNLOADED
        except Exception:
            pass
