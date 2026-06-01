from __future__ import annotations

import os
from dataclasses import replace

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QLabel, QMainWindow,
    QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from app.config.constants import APP_NAME, APP_VERSION, SUPPORTED_LANGUAGES, SUPPORTED_MODELS
from app.core.ffmpeg_handler import FFmpegHandler
from app.models.job import JobStatus
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
        self.resize(1100, 740)
        self.setStyleSheet(
            "QMainWindow { background: #121212; } "
            "QWidget { color: #ddd; background: #121212; }"
        )

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(6)

        root.addLayout(self._build_toolbar())
        root.addLayout(self._build_model_bar())
        root.addWidget(self._build_drop_area())
        root.addWidget(self._build_file_table(), stretch=3)
        root.addWidget(self._build_progress_bar())

        self._log_panel = LogPanel()
        root.addWidget(self._log_panel, stretch=2)

        self._connect_viewmodel()
        self._vm.check_system_async()

    # ── 레이아웃 빌더 ─────────────────────────────────────────────
    def _build_toolbar(self) -> QHBoxLayout:
        layout = QHBoxLayout()

        self._btn_add_files  = self._toolbar_btn("파일 추가")
        self._btn_add_folder = self._toolbar_btn("폴더 추가")
        self._btn_output_dir = self._toolbar_btn("출력 폴더")
        self._btn_settings   = self._toolbar_btn("설정")
        self._btn_start      = self._action_btn("▶ 시작", "#2e7d32", "#388e3c")
        self._btn_stop       = self._action_btn("■ 중지",  "#c62828", "#d32f2f")

        for btn in (self._btn_add_files, self._btn_add_folder, self._btn_output_dir,
                    self._btn_settings):
            layout.addWidget(btn)
        layout.addStretch()
        layout.addWidget(self._btn_start)
        layout.addWidget(self._btn_stop)

        self._btn_add_files.clicked.connect(self._on_add_files)
        self._btn_add_folder.clicked.connect(self._on_add_folder)
        self._btn_output_dir.clicked.connect(self._on_set_output_dir)
        self._btn_settings.clicked.connect(self._on_settings)
        self._btn_start.clicked.connect(self._on_start)
        self._btn_stop.clicked.connect(self._on_stop)

        return layout

    def _build_model_bar(self) -> QVBoxLayout:
        vbox = QVBoxLayout()
        vbox.setSpacing(4)
        s = self._vm.settings()

        # ── 1행: 모델 / 언어 / 반복억제 / 노이즈제거 / 중복제거 / GPU 정보 ──
        row1 = QHBoxLayout()

        row1.addWidget(QLabel("모델:"))
        self._cb_model = QComboBox()
        for m in SUPPORTED_MODELS:
            self._cb_model.addItem(m["name"], userData=m["id"])
        for i in range(self._cb_model.count()):
            if self._cb_model.itemData(i) == s.model_name:
                self._cb_model.setCurrentIndex(i)
                break
        self._cb_model.setMinimumWidth(180)
        row1.addWidget(self._cb_model)

        row1.addWidget(QLabel("언어:"))
        self._cb_language = QComboBox()
        for lang in SUPPORTED_LANGUAGES:
            self._cb_language.addItem(lang["name"], userData=lang["code"])
        for i in range(self._cb_language.count()):
            if self._cb_language.itemData(i) == s.language:
                self._cb_language.setCurrentIndex(i)
                break
        self._cb_language.setMinimumWidth(140)
        row1.addWidget(self._cb_language)

        row1.addWidget(QLabel("반복 억제:"))
        self._cb_hallucination = QComboBox()
        self._cb_hallucination.addItem("끔",    userData="off")
        self._cb_hallucination.addItem("약하게", userData="weak")
        self._cb_hallucination.addItem("보통",   userData="medium")
        self._cb_hallucination.addItem("강하게", userData="strong")
        for i in range(self._cb_hallucination.count()):
            if self._cb_hallucination.itemData(i) == s.hallucination_level:
                self._cb_hallucination.setCurrentIndex(i)
                break
        self._cb_hallucination.setMinimumWidth(90)
        self._cb_hallucination.setToolTip(
            "무음 구간에서 같은 문장이 반복되는 할루시네이션을 억제합니다.\n"
            "강하게 설정할수록 반복을 더 적극적으로 제거합니다."
        )
        row1.addWidget(self._cb_hallucination)

        row1.addWidget(QLabel("노이즈 제거:"))
        self._cb_noise = QComboBox()
        self._cb_noise.addItem("OFF", userData=False)
        self._cb_noise.addItem("ON",  userData=True)
        self._cb_noise.setCurrentIndex(1 if s.audio.noise_reduction else 0)
        self._cb_noise.setMinimumWidth(60)
        row1.addWidget(self._cb_noise)

        row1.addWidget(QLabel("중복 제거:"))
        self._cb_dedup = QComboBox()
        self._cb_dedup.addItem("ON",  userData=True)
        self._cb_dedup.addItem("OFF", userData=False)
        self._cb_dedup.setCurrentIndex(0 if s.dedup_segments else 1)
        self._cb_dedup.setMinimumWidth(60)
        row1.addWidget(self._cb_dedup)

        row1.addStretch()

        self._lbl_gpu_info = QLabel("GPU: 감지 중...")
        self._lbl_gpu_info.setStyleSheet("color: #888; font-size: 12px;")
        row1.addWidget(self._lbl_gpu_info)

        vbox.addLayout(row1)

        # ── 2행: VAD 필터 / 음성 강조 필터 체크박스 ──────────────────
        row2 = QHBoxLayout()

        self._chk_vad = QCheckBox("VAD 필터 사용")
        self._chk_vad.setChecked(s.whisper.vad_filter)
        self._chk_vad.setToolTip(
            "음성 활동 감지(VAD) 필터를 활성화합니다.\n"
            "무음 구간을 건너뛰어 전사 속도와 정확도를 높입니다."
        )
        row2.addWidget(self._chk_vad)

        self._chk_voice_enh = QCheckBox("음성 강조 필터 적용")
        self._chk_voice_enh.setChecked(s.audio.voice_enhancement)
        self._chk_voice_enh.setToolTip(
            "FFmpeg 음성 강조 필터(highpass/lowpass/equalizer)를 적용합니다.\n"
            "배경 소음이 많은 경우 전사 정확도를 높일 수 있습니다."
        )
        row2.addWidget(self._chk_voice_enh)

        row2.addStretch()
        vbox.addLayout(row2)

        # 드롭다운·체크박스 변경 시 즉시 설정 반영
        for cb in (self._cb_model, self._cb_language, self._cb_hallucination,
                   self._cb_noise, self._cb_dedup):
            cb.currentIndexChanged.connect(self._sync_settings_from_bar)
        for chk in (self._chk_vad, self._chk_voice_enh):
            chk.stateChanged.connect(self._sync_settings_from_bar)

        return vbox

    def _build_drop_area(self) -> DropArea:
        self._drop_area = DropArea()
        self._drop_area.files_dropped.connect(
            lambda paths: self._vm.queue_vm.add_files(paths)
        )
        return self._drop_area

    def _build_file_table(self) -> FileTable:
        self._file_table = FileTable()
        self._file_table.move_up_requested.connect(self._vm.queue_vm.move_up)
        self._file_table.move_down_requested.connect(self._vm.queue_vm.move_down)
        self._file_table.remove_requested.connect(self._vm.queue_vm.remove_job)
        self._file_table.remove_multiple_requested.connect(self._vm.queue_vm.remove_jobs)
        self._file_table.clear_completed_requested.connect(self._vm.queue_vm.clear_completed)
        self._file_table.open_output_requested.connect(self._open_output_file)
        self._file_table.open_folder_requested.connect(self._open_output_folder)
        return self._file_table

    def _build_progress_bar(self) -> OverallProgressBar:
        self._progress_bar = OverallProgressBar()
        return self._progress_bar

    # ── ViewModel 연결 ────────────────────────────────────────────
    def _connect_viewmodel(self) -> None:
        qvm = self._vm.queue_vm
        qvm.jobs_changed.connect(self._refresh_table)
        qvm.job_progress_changed.connect(self._on_job_progress)
        qvm.log_appended.connect(self._log_panel.append_log)
        qvm.error_appended.connect(self._log_panel.append_error)
        qvm.segment_ready.connect(self._log_panel.append_segment)
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
        gpu_text = (
            f"GPU: {info.gpu_name}  "
            f"VRAM: {info.gpu_vram_gb}GB  "
            f"CUDA: {info.cuda_version if info.cuda_available else 'N/A'}"
        )
        self._lbl_gpu_info.setText(gpu_text)
        color = "#4caf50" if info.cuda_available else "#f44336"
        self._lbl_gpu_info.setStyleSheet(f"color: {color}; font-size: 12px;")

        if not info.ffmpeg_available:
            QMessageBox.warning(
                self, "FFmpeg 미설치",
                "FFmpeg가 설치되어 있지 않습니다.\n"
                "https://ffmpeg.org/download.html 에서 설치 후 PATH에 추가하세요.\n\n"
                "Windows: winget install ffmpeg",
            )

    # ── 버튼 핸들러 ───────────────────────────────────────────────
    def _on_add_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "파일 선택", "",
            "미디어 파일 (*.mp4 *.mkv *.avi *.mov *.wmv *.mp3 *.wav "
            "*.aac *.flac *.ogg *.m4a *.ts *.webm *.flv *.opus *.wma "
            "*.mpeg *.mpg *.asf *.m2ts);;모든 파일 (*)",
        )
        if paths:
            self._vm.queue_vm.add_files(paths)

    def _on_add_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "폴더 선택")
        if folder:
            files: list[str] = []
            for root, _, fnames in os.walk(folder):
                for fn in fnames:
                    files.append(os.path.join(root, fn))
            self._vm.queue_vm.add_files(files)

    def _on_set_output_dir(self) -> None:
        current = self._vm.settings().output_dir
        if current:
            msg = QMessageBox(self)
            msg.setWindowTitle("출력 폴더 설정")
            msg.setText(f"현재 출력 폴더:\n{current}")
            btn_change = msg.addButton("폴더 변경", QMessageBox.AcceptRole)
            btn_reset  = msg.addButton("원본파일 위치로 초기화", QMessageBox.ResetRole)
            msg.addButton("취소", QMessageBox.RejectRole)
            msg.exec()
            clicked = msg.clickedButton()
            if clicked == btn_reset:
                self._vm.apply_settings(replace(self._vm.settings(), output_dir=""))
                return
            elif clicked != btn_change:
                return
        folder = QFileDialog.getExistingDirectory(self, "출력 폴더 선택")
        if folder:
            self._vm.apply_settings(replace(self._vm.settings(), output_dir=folder))

    def _on_settings(self) -> None:
        dlg = SettingsDialog(self._vm.settings(), self._system_info, self)
        if dlg.exec():
            self._vm.apply_settings(dlg.get_settings())
            self._sync_bar_from_settings()

    def _on_start(self) -> None:
        count = self._vm.queue_vm.startable_count()
        self._log_panel.append_log(f"[시작] 대기 파일 {count}개 확인됨")
        if count == 0:
            QMessageBox.information(self, "알림", "처리할 파일이 없습니다.")
            return
        self._sync_settings_from_bar()
        self._log_panel.clear_live()
        self._vm.start()
        self._log_panel.append_log("[시작] 워커 시작 요청 완료")

    def _on_stop(self) -> None:
        self._vm.stop()
        self._log_panel.append_log("중지 요청 — 완료된 파일 제외한 나머지를 대기 상태로 초기화합니다.")

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

    # ── 설정 동기화 ───────────────────────────────────────────────
    def _sync_settings_from_bar(self) -> None:
        """모델바 드롭다운/체크박스 값을 settings에 반영합니다."""
        current = self._vm.settings()
        new_whisper = replace(
            current.whisper,
            vad_filter=self._chk_vad.isChecked(),
        )
        new_audio = replace(
            current.audio,
            noise_reduction=bool(self._cb_noise.currentData()),
            voice_enhancement=self._chk_voice_enh.isChecked(),
        )
        new_settings = replace(
            current,
            model_name=self._cb_model.currentData(),
            language=self._cb_language.currentData(),
            hallucination_level=self._cb_hallucination.currentData(),
            dedup_segments=bool(self._cb_dedup.currentData()),
            whisper=new_whisper,
            audio=new_audio,
        )
        self._vm.apply_settings(new_settings)

    def _sync_bar_from_settings(self) -> None:
        """settings 값을 모델바 드롭다운/체크박스에 반영합니다."""
        s = self._vm.settings()
        for i in range(self._cb_model.count()):
            if self._cb_model.itemData(i) == s.model_name:
                self._cb_model.setCurrentIndex(i)
                break
        for i in range(self._cb_language.count()):
            if self._cb_language.itemData(i) == s.language:
                self._cb_language.setCurrentIndex(i)
                break
        for i in range(self._cb_hallucination.count()):
            if self._cb_hallucination.itemData(i) == s.hallucination_level:
                self._cb_hallucination.setCurrentIndex(i)
                break
        self._cb_noise.setCurrentIndex(1 if s.audio.noise_reduction else 0)
        self._chk_vad.setChecked(s.whisper.vad_filter)
        self._chk_voice_enh.setChecked(s.audio.voice_enhancement)

    # ── 헬퍼 ──────────────────────────────────────────────────────
    @staticmethod
    def _toolbar_btn(text: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setStyleSheet(
            "QPushButton { background: #333; color: #ddd; padding: 6px 12px; "
            "border-radius: 4px; border: 1px solid #555; } "
            "QPushButton:hover { background: #444; }"
        )
        return btn

    @staticmethod
    def _action_btn(text: str, bg: str, hover: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setStyleSheet(
            f"QPushButton {{ background: {bg}; color: white; font-weight: bold; "
            f"padding: 6px 14px; border-radius: 4px; }} "
            f"QPushButton:hover {{ background: {hover}; }}"
        )
        return btn
