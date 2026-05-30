from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal

from app.core.model_manager import ModelManager
from app.models.model_info import ModelInfo, ModelState


class _DownloadWorker(QThread):
    progress = Signal(float)
    finished = Signal(str)
    failed = Signal(str, str)

    def __init__(self, manager: ModelManager, model_id: str, parent=None) -> None:
        super().__init__(parent)
        self._manager = manager
        self._model_id = model_id

    def run(self) -> None:
        try:
            self._manager.download_model(self._model_id, lambda p: self.progress.emit(p))
            self.finished.emit(self._model_id)
        except Exception as e:
            self.failed.emit(self._model_id, str(e))


class ModelManagerViewModel(QObject):
    """모델 목록, 다운로드, 삭제 상태를 관리합니다."""

    models_changed = Signal()
    download_progress = Signal(str, float)
    download_finished = Signal(str)
    download_failed = Signal(str, str)

    def __init__(self, manager: ModelManager, parent=None) -> None:
        super().__init__(parent)
        self._manager = manager
        self._workers: dict[str, _DownloadWorker] = {}

    def models(self) -> list[ModelInfo]:
        return self._manager.list_models()

    def download(self, model_id: str) -> None:
        """모델 다운로드를 시작합니다."""
        if model_id in self._workers:
            return
        worker = _DownloadWorker(self._manager, model_id, self)
        worker.progress.connect(lambda p: self.download_progress.emit(model_id, p))
        worker.finished.connect(self._on_finished)
        worker.failed.connect(self._on_failed)
        self._workers[model_id] = worker
        worker.start()

    def delete(self, model_id: str) -> None:
        """로컬 모델 캐시를 삭제합니다."""
        self._manager.delete_model(model_id)
        self.models_changed.emit()

    def _on_finished(self, model_id: str) -> None:
        self._workers.pop(model_id, None)
        self.download_finished.emit(model_id)
        self.models_changed.emit()

    def _on_failed(self, model_id: str, error: str) -> None:
        self._workers.pop(model_id, None)
        self.download_failed.emit(model_id, error)
