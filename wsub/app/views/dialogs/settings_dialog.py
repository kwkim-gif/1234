from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSlider, QSpinBox, QTabWidget, QVBoxLayout, QWidget,
)
from PySide6.QtCore import Qt

from app.config.constants import (
    OUTPUT_FORMATS, SAMPLE_RATES, SUPPORTED_LANGUAGES, SUPPORTED_MODELS,
)
from app.models.settings import AppSettings, AudioSettings, WhisperSettings


class SettingsDialog(QDialog):
    """5개 탭으로 구성된 설정 다이얼로그."""

    def __init__(self, settings: AppSettings, system_info=None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("설정")
        self.resize(540, 480)
        self._settings = settings
        self._system_info = system_info

        layout = QVBoxLayout(self)
        self._tabs = QTabWidget()
        layout.addWidget(self._tabs)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._build_general_tab()
        self._build_advanced_tab()
        self._build_audio_tab()
        self._build_gpu_tab()

    # ── 탭 빌더 ───────────────────────────────────────────────────
    def _build_general_tab(self) -> None:
        w = QWidget()
        form = QFormLayout(w)

        self._cb_format = QComboBox()
        self._cb_format.addItems([f.upper() for f in OUTPUT_FORMATS])
        self._cb_format.setCurrentText(self._settings.output_format.upper())
        form.addRow("출력 형식:", self._cb_format)

        out_row = QHBoxLayout()
        self._le_output_dir = QLineEdit(self._settings.output_dir)
        self._le_output_dir.setPlaceholderText("(원본 파일과 같은 폴더)")
        btn_browse = QPushButton("찾아보기")
        btn_browse.clicked.connect(self._browse_output_dir)
        out_row.addWidget(self._le_output_dir)
        out_row.addWidget(btn_browse)
        form.addRow("출력 폴더:", out_row)

        self._tabs.addTab(w, "General")

    def _build_advanced_tab(self) -> None:
        w = QWidget()
        form = QFormLayout(w)
        ws = self._settings.whisper

        self._sp_temperature = self._double_spin(ws.temperature, 0.0, 1.0, 0.1)
        form.addRow("Temperature:", self._sp_temperature)

        self._sp_beam_size = self._spin(ws.beam_size, 1, 10)
        form.addRow("Beam Size:", self._sp_beam_size)

        self._sp_best_of = self._spin(ws.best_of, 1, 10)
        form.addRow("Best Of:", self._sp_best_of)

        self._sp_no_speech = self._double_spin(ws.no_speech_threshold, 0.0, 1.0, 0.05)
        form.addRow("No Speech Threshold:", self._sp_no_speech)

        self._sp_comp_ratio = self._double_spin(ws.compression_ratio_threshold, 1.0, 5.0, 0.1)
        form.addRow("Compression Ratio:", self._sp_comp_ratio)

        self._chk_condition = QCheckBox()
        self._chk_condition.setChecked(ws.condition_on_previous_text)
        form.addRow("Condition on Previous Text:", self._chk_condition)

        self._chk_word_ts = QCheckBox()
        self._chk_word_ts.setChecked(ws.word_timestamps)
        form.addRow("Word Timestamps:", self._chk_word_ts)

        self._chk_vad = QCheckBox()
        self._chk_vad.setChecked(ws.vad_filter)
        form.addRow("VAD Filter:", self._chk_vad)

        self._tabs.addTab(w, "Advanced")

    def _build_audio_tab(self) -> None:
        w = QWidget()
        form = QFormLayout(w)
        a = self._settings.audio

        self._chk_noise = QCheckBox()
        self._chk_noise.setChecked(a.noise_reduction)
        form.addRow("Noise Reduction:", self._chk_noise)

        self._chk_silence = QCheckBox()
        self._chk_silence.setChecked(a.silence_trimming)
        form.addRow("Silence Trimming:", self._chk_silence)

        self._chk_normalize = QCheckBox()
        self._chk_normalize.setChecked(a.normalize_volume)
        form.addRow("Normalize Volume:", self._chk_normalize)

        self._chk_voice_enh = QCheckBox()
        self._chk_voice_enh.setChecked(a.voice_enhancement)
        form.addRow("Voice Enhancement:", self._chk_voice_enh)

        self._cb_sample_rate = QComboBox()
        for sr in SAMPLE_RATES:
            self._cb_sample_rate.addItem(str(sr))
        self._cb_sample_rate.setCurrentText(str(a.sample_rate))
        form.addRow("Sample Rate (Hz):", self._cb_sample_rate)

        self._tabs.addTab(w, "Audio")

    def _build_gpu_tab(self) -> None:
        w = QWidget()
        vl = QVBoxLayout(w)

        self._cb_device = QComboBox()
        self._cb_device.addItems(["auto", "cuda", "cpu"])
        self._cb_device.setCurrentText(self._settings.device)

        form = QFormLayout()
        form.addRow("장치 선택:", self._cb_device)
        vl.addLayout(form)

        info_box = QGroupBox("감지된 GPU 정보")
        info_layout = QFormLayout(info_box)
        si = self._system_info
        if si:
            info_layout.addRow("GPU:", QLabel(si.gpu_name))
            info_layout.addRow("VRAM:", QLabel(f"{si.gpu_vram_gb} GB"))
            info_layout.addRow("CUDA:", QLabel(si.cuda_version if si.cuda_available else "미감지"))
        else:
            info_layout.addRow(QLabel("시스템 정보를 불러오는 중..."))
        vl.addWidget(info_box)
        vl.addStretch()

        self._tabs.addTab(w, "GPU")

    # ── 결과 수집 ─────────────────────────────────────────────────
    def get_settings(self) -> AppSettings:
        """다이얼로그의 현재 값으로 AppSettings를 반환합니다."""
        whisper = WhisperSettings(
            temperature=self._sp_temperature.value(),
            beam_size=self._sp_beam_size.value(),
            best_of=self._sp_best_of.value(),
            no_speech_threshold=self._sp_no_speech.value(),
            compression_ratio_threshold=self._sp_comp_ratio.value(),
            condition_on_previous_text=self._chk_condition.isChecked(),
            word_timestamps=self._chk_word_ts.isChecked(),
            vad_filter=self._chk_vad.isChecked(),
        )
        audio = AudioSettings(
            noise_reduction=self._chk_noise.isChecked(),
            silence_trimming=self._chk_silence.isChecked(),
            normalize_volume=self._chk_normalize.isChecked(),
            voice_enhancement=self._chk_voice_enh.isChecked(),
            sample_rate=int(self._cb_sample_rate.currentText()),
        )
        return replace(
            self._settings,
            output_format=self._cb_format.currentText().lower(),
            output_dir=self._le_output_dir.text().strip(),
            device=self._cb_device.currentText(),
            whisper=whisper,
            audio=audio,
        )

    # ── 헬퍼 ──────────────────────────────────────────────────────
    def _browse_output_dir(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "출력 폴더 선택")
        if d:
            self._le_output_dir.setText(d)

    @staticmethod
    def _spin(value: int, min_: int, max_: int) -> QSpinBox:
        sb = QSpinBox()
        sb.setRange(min_, max_)
        sb.setValue(value)
        return sb

    @staticmethod
    def _double_spin(value: float, min_: float, max_: float, step: float) -> QDoubleSpinBox:
        sb = QDoubleSpinBox()
        sb.setRange(min_, max_)
        sb.setSingleStep(step)
        sb.setDecimals(2)
        sb.setValue(value)
        return sb
