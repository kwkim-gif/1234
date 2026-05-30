from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QHBoxLayout, QLabel, QMainWindow,
    QMessageBox, QPushButton, QSizePolicy, QSplitter, QVBoxLayout, QWidget,
)

from app.config.constants import APP_NAME, APP_VERSION, SUPPORTED_LANGUAGES, SUPPORTED_MODELS
from app.core.ffmpeg_handler import FFmpegHandler
from app.models.job import JobStatus
from app.views.dialogs.model_dialog import ModelDialog
from app.views.dialogs.settings_dialog import SettingsDialog
from app.views.widgets.drop_area import DropArea
from app.views.widgets.file_table import FileTable
from app.views.widgets.log_panel import LogPanel
from app.views.widgets.progress_bar import OverallProgressBar
from app.viewmodels.main_viewmodel import MainViewModel


class MainWindow(QMainWindow):
    """W-Sub 메인 윈도우."""

    def __init__(self, vm: MainViewModel) -> None:
        super().__init__()
        self._vm = vm
        self._system_info = None

        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.resize(1000, 700)
        self.setStyleSheet("QMainWindow { background: #121212; } QWidget { color: #ddd; background: #121212; }")

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(6)

        root.addLayout(self._build_toolbar())
        root.addLayout(self._build_model_bar())
        root.addWidget(self._build_drop_area())
        root.addWidget(self._build_file_table())
        root.addWidget(self._build_progress_bar())

        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(self._log_panel)
        splitter.setSizes([150])
        root.addWidget(splitter)

        self._connect_viewmodel()
        self._vm.check_system_async()

    # ── 레이아웃 빌더 ─────────────────────────────────────────────
    def _build_toolbar(self) -> QHBoxLayout:
        layout = QHBoxLayout()

        self._btn_add_files = QPushButton("파일 추가")
        self._btn_add_folder = QPushButton("폴더 추가")
        self._btn_output_dir = QPushButton("출력 폴더")
        self._btn_settings = QPushButton("설정")
        self._btn_models = QPushButton("모델 관리")
        self._btn_start = QPushButton("▶ 시작")
        self._btn_stop = QPushButton("■ 중지")

        self._btn_start.setStyleSheet("QPushButton { background: #2e7d32; color: white; font-weight: bold; padding: 6px 14px; border-radius: 4px; } QPushButton:hover { background: #388e3c; }")
        self._btn_stop.setStyleSheet("QPushButton { background: #c62828; color: white; font-weight: bold; padding: 6px 14px; border-radius: 4px; } QPushButton:hover { background: #d32f2f; }")

        for btn in (self._btn_add_files, self._btn_add_folder, self._btn_output_dir, self._btn_settings, self._btn_models):
            btn.setStyleSheet("QPushButton { background: #333; color: #ddd; padding: 6px 12px; border-radius: 4px; border: 1px solid #555; } QPushButton:hover { background: #444; }")

        layout.addWidget(self._btn_add_files)
        layout.addWidget(self._btn_add_folder)
        layout.addWidget(self._btn_output_dir)
        layout.addWidget(self._btn_settings)
        layout.addWidget(self._btn_models)
        layout.addStretch()
        layout.addWidget(self._btn_start)
        layout.addWidget(self._btn_stop)

        self._btn_add_files.clicked.connect(self._on_add_files)
        self._btn_add_folder.clicked.connect(self._on_add_folder)
        self._btn_output_dir.clicked.connect(self._on_set_output_dir)
        self._btn_settings.clicked.connect(self._on_settings)
        self._btn_models.clicked.connect(self._on_models)
        self._btn_start.clicked.connect(self._on_start)
        self._btn_stop.clicked.connect(self._on_stop)

        return layout

    def _build_model_bar(self) -> QHBoxLayout:
        layout = QHBoxLayout()

        layout.addWidget(QLabel("모델:"))
        self._cb_model = QComboBox()
        for m in SUPPORTED_MODELS:
            self._cb_model.addItem(m["name"], userData=m["id"])
        current_id = self._vm.settings().model_name
        for i in range(self._cb_model.count()):
            if self._cb_model.itemData(i) == current_id:
                self._cb_model.setCurrentIndex(i)
                break
        self._cb_model.setMinimumWidth(200)
        layout.addWidget(self._cb_model)

        layout.addWidget(QLabel("언어:"))
        self._cb_language = QComboBox()
        for lang in SUPPORTED_LANGUAGES:
            self._cb_language.addItem(lang["name"], userData=lang["code"])
        current_lang = self._vm.settings().language
        for i in range(self._cb_language.count()):
            if self._cb_language.itemData(i) == current_lang:
                self._cb_language.setCurrentIndex(i)
                break
        layout.addWidget(self._cb_language)

        layout.addWidget(QLabel("장치:"))
        self._cb_device = QComboBox()
        self._cb_device.addItems(["auto", "cuda", "cpu"])
        self._cb_device.setCurrentText(self._vm.settings().device)
        layout.addWidget(self._cb_device)

        layout.addStretch()
        self._lbl_gpu_info = QLabel("GPU: 감지 중...")
        self._lbl_gpu_info.setStyleSheet("color: #888; font-size: 12px;")
        layout.addWidget(self._lbl_gpu_info)

        self._cb_model.currentIndexChanged.connect(self._sync_settings_from_bar)
        self._cb_language.currentIndexChanged.connect(self._sync_settings_from_bar)
        self._cb_device.currentIndexChanged.connect(self._sync_settings_from_bar)

        return layout

    def _build_drop_area(self) -> DropArea:
        self._drop_area = DropArea()
        self._drop_area.files_dropped.connect(lambda paths: self._vm.queue_vm.add_files(paths))
        return self._drop_area

    def _build_file_table(self) -> FileTable:
        self._file_table = FileTable()
        self._file_table.move_up_requested.connect(self._vm.queue_vm.move_up)
        self._file_table.move_down_requested.connect(self._vm.queue_vm.move_down)
        self._file_table.remove_requested.connect(self._vm.queue_vm.remove_job)
        self._file_table.open_output_requested.connect(self._open_output_file)
        self._file_table.open_folder_requested.connect(self._open_output_folder)
        return self._file_table

    def _build_progress_bar(self) -> OverallProgressBar:
        self._progress_bar = OverallProgressBar()
        self._log_panel = LogPanel()
        return self._progress_bar

    # ── ViewModel 연결 ────────────────────────────────────────────
    def _connect_viewmodel(self) -> None:
        qvm = self._vm.queue_vm
        qvm.jobs_changed.connect(self._refresh_table)
        qvm.job_progress_changed.connect(self._on_job_progress)
        qvm.log_appended.connect(self._log_panel.append_log)
        qvm.error_appended.connect(self._log_panel.append_error)
        qvm.overall_progress_changed.connect(
            lambda p, lbl: self._progress_bar.update_progress(p, lbl)
        )
        self._vm.system_info_ready.connect(self._on_system_info)

    def _refresh_table(self) -> None:
        self._file_table.refresh(self._vm.queue_vm.jobs())

    def _on_job_progress(self, job_id: str, progress: float) -> None:
        self._file_table.update_job_progress(job_id, self._vm.queue_vm.jobs())

    def _on_system_info(self, info) -> None:
        self._system_info = info
        gpu_text = f"GPU: {info.gpu_name}  VRAM: {info.gpu_vram_gb}GB  CUDA: {info.cuda_version or 'N/A'}"
        self._lbl_gpu_info.setText(gpu_text)
        if not info.ffmpeg_available:
            QMessageBox.warning(
                self, "FFmpeg 미설치",
                "FFmpeg가 설치되어 있지 않습니다.\n"
                "https://ffmpeg.org/download.html 에서 설치 후 PATH에 추가하세요.",
            )

    # ── 버튼 핸들러 ───────────────────────────────────────────────
    def _on_add_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "파일 선택", "",
            "미디어 파일 (*.mp4 *.mkv *.avi *.mov *.wmv *.mp3 *.wav *.aac *.flac *.ogg *.m4a *.ts *.webm *.flv *.opus *.wma *.mpeg *.mpg *.asf *.m2ts);;모든 파일 (*)",
        )
        if paths:
            self._vm.queue_vm.add_files(paths)

    def _on_add_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "폴더 선택")
        if folder:
            files = []
            for root, _, fnames in os.walk(folder):
                for fn in fnames:
                    files.append(os.path.join(root, fn))
            self._vm.queue_vm.add_files(files)

    def _on_set_output_dir(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "출력 폴더 선택")
        if folder:
            from dataclasses import replace
            s = replace(self._vm.settings(), output_dir=folder)
            self._vm.apply_settings(s)

    def _on_settings(self) -> None:
        dlg = SettingsDialog(self._vm.settings(), self._system_info, self)
        if dlg.exec():
            new_settings = dlg.get_settings()
            self._vm.apply_settings(new_settings)

    def _on_models(self) -> None:
        dlg = ModelDialog(self._vm.model_vm, self)
        dlg.exec()

    def _on_start(self) -> None:
        if self._vm.queue_vm.pending_count() == 0:
            QMessageBox.information(self, "알림", "처리할 파일이 없습니다.")
            return
        self._sync_settings_from_bar()
        self._vm.start()
        self._log_panel.append_log("작업 시작")

    def _on_stop(self) -> None:
        self._vm.stop()
        self._log_panel.append_log("중지 요청됨")

    def _open_output_file(self, row: int) -> None:
        jobs = self._vm.queue_vm.jobs()
        if row < len(jobs):
            job = jobs[row]
            if job.output_path and job.output_path.exists():
                os.startfile(str(job.output_path))

    def _open_output_folder(self, row: int) -> None:
        jobs = self._vm.queue_vm.jobs()
        if row < len(jobs):
            job = jobs[row]
            folder = job.output_path.parent if job.output_path else job.file_path.parent
            if folder.exists():
                os.startfile(str(folder))

    def _sync_settings_from_bar(self) -> None:
        """모델바 변경 사항을 설정에 즉시 반영합니다."""
        from dataclasses import replace
        s = replace(
            self._vm.settings(),
            model_name=self._cb_model.currentData(),
            language=self._cb_language.currentData(),
            device=self._cb_device.currentText(),
        )
        self._vm.apply_settings(s)
