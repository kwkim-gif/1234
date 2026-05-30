from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget,
)


class LogPanel(QWidget):
    """진행 로그, 에러 로그, 실시간 전사 텍스트를 나란히 표시하는 패널."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._log_pane = self._make_pane("진행 로그", "#1e1e1e", "#ddd")
        self._err_pane = self._make_pane("에러 로그", "#1e0000", "#f88")
        self._live_pane = self._make_pane("실시간 전사", "#0d1a0d", "#a8e6a3")

        layout.addWidget(self._log_pane)
        layout.addWidget(self._err_pane)
        layout.addWidget(self._live_pane)

        self._log_text: QPlainTextEdit = self._log_pane.findChild(QPlainTextEdit)
        self._err_text: QPlainTextEdit = self._err_pane.findChild(QPlainTextEdit)
        self._live_text: QPlainTextEdit = self._live_pane.findChild(QPlainTextEdit)

    def append_log(self, message: str) -> None:
        """타임스탬프와 함께 진행 로그에 메시지를 추가합니다."""
        ts = datetime.now().strftime("%H:%M:%S")
        self._log_text.appendPlainText(f"[{ts}] {message}")

    def append_error(self, message: str) -> None:
        """타임스탬프와 함께 에러 로그에 메시지를 추가합니다."""
        ts = datetime.now().strftime("%H:%M:%S")
        self._err_text.appendPlainText(f"[{ts}] {message}")

    def append_segment(self, segment: dict) -> None:
        """실시간 전사 세그먼트를 전사 패널에 추가합니다."""
        start = segment.get("start", 0.0)
        end = segment.get("end", 0.0)
        text = segment.get("text", "").strip()
        if not text:
            return
        ts = f"{_fmt_ts(start)} → {_fmt_ts(end)}"
        self._live_text.appendPlainText(f"[{ts}] {text}")

    def clear_live(self) -> None:
        """실시간 전사 패널을 초기화합니다."""
        self._live_text.clear()

    def clear_logs(self) -> None:
        self._log_text.clear()
        self._err_text.clear()

    @staticmethod
    def _make_pane(title: str, bg: str, fg: str) -> QWidget:
        pane = QWidget()
        vl = QVBoxLayout(pane)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(2)

        header = QHBoxLayout()
        lbl = QLabel(title)
        lbl.setStyleSheet(f"color: {fg}; font-weight: bold;")
        btn_clear = QPushButton("지우기")
        btn_clear.setFixedWidth(55)
        header.addWidget(lbl)
        header.addStretch()
        header.addWidget(btn_clear)
        vl.addLayout(header)

        text = QPlainTextEdit()
        text.setReadOnly(True)
        text.setMaximumBlockCount(3000)
        text.setStyleSheet(
            f"background: {bg}; color: {fg}; "
            f"font-family: Consolas, 'Malgun Gothic', monospace; font-size: 12px;"
        )
        vl.addWidget(text)

        btn_clear.clicked.connect(text.clear)
        return pane


def _fmt_ts(seconds: float) -> str:
    """초를 MM:SS 형식으로 변환합니다."""
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m:02d}:{s:02d}"
