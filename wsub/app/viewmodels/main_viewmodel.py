from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from app.config.config_manager import load_settings, save_settings
from app.core.model_manager import ModelManager
from app.core.system_checker import SystemInfo, check_system
from app.core.transcription_service import TranscriptionService
from app.models.settings import AppSettings
from app.viewmodels.model_manager_viewmodel import ModelManagerViewModel
from app.viewmodels.queue_viewmodel import QueueViewModel


class MainViewModel(QObject):
    """최상위 ViewModel: 설정, 시스템 정보, 하위 ViewModel 조율."""

    settings_changed = Signal()
    system_info_ready = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._settings: AppSettings = load_settings()
        self._service = TranscriptionService()
        self._model_manager = ModelManager()

        self.queue_vm = QueueViewModel(self._service, self)
        self.model_vm = ModelManagerViewModel(self._model_manager, self)

    # ── 설정 ──────────────────────────────────────────────────────
    def settings(self) -> AppSettings:
        return self._settings

    def apply_settings(self, settings: AppSettings) -> None:
        """설정을 적용하고 파일에 저장합니다."""
        self._settings = settings
        save_settings(settings)
        self.settings_changed.emit()

    # ── 전사 시작/중지 ────────────────────────────────────────────
    def start(self) -> None:
        self.queue_vm.start_transcription(self._settings)

    def stop(self) -> None:
        self.queue_vm.stop_transcription()

    # ── 시스템 검사 ───────────────────────────────────────────────
    def check_system_async(self) -> None:
        """백그라운드에서 시스템 검사를 수행합니다."""
        from PySide6.QtCore import QThread

        class _Worker(QThread):
            done = Signal(object)

            def run(self_inner) -> None:
                info = check_system()
                self_inner.done.emit(info)

        worker = _Worker(self)
        worker.done.connect(self.system_info_ready)
        worker.start()
        self._sys_worker = worker
