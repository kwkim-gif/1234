from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget,
)


class LogPanel(QWidget):
    """진행 로그와 에러 로그를 나란히 표시하는 패널."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._log = self._make_pane("진행 로그", "#1e1e1e", "#ddd")
        self._err = self._make_pane("에러 로그", "#1e0000", "#f88")

        layout.addWidget(self._log)
        layout.addWidget(self._err)

    def append_log(self, message: str) -> None:
        """타임스탬프와 함께 진행 로그에 메시지를 추가합니다."""
        ts = datetime.now().strftime("%H:%M:%S")
        self._log.findChild(QPlainTextEdit).appendPlainText(f"[{ts}] {message}")

    def append_error(self, message: str) -> None:
        """타임스탬프와 함께 에러 로그에 메시지를 추가합니다."""
        ts = datetime.now().strftime("%H:%M:%S")
        self._err.findChild(QPlainTextEdit).appendPlainText(f"[{ts}] {message}")

    def clear_logs(self) -> None:
        self._log.findChild(QPlainTextEdit).clear()
        self._err.findChild(QPlainTextEdit).clear()

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
        text.setMaximumBlockCount(2000)
        text.setStyleSheet(f"background: {bg}; color: {fg}; font-family: Consolas, monospace; font-size: 12px;")
        vl.addWidget(text)

        btn_clear.clicked.connect(text.clear)
        return pane
