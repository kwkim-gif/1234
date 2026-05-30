from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget


class OverallProgressBar(QWidget):
    """전체 진행률 및 남은 시간을 표시하는 복합 위젯."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)

        lbl_title = QLabel("전체 진행률:")
        lbl_title.setFixedWidth(80)

        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setTextVisible(True)
        self._bar.setStyleSheet("""
            QProgressBar { border: 1px solid #444; border-radius: 4px; background: #222; height: 18px; }
            QProgressBar::chunk { background: #4a9eff; border-radius: 3px; }
        """)

        self._lbl_remain = QLabel("대기 중")
        self._lbl_remain.setFixedWidth(120)
        self._lbl_remain.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        layout.addWidget(lbl_title)
        layout.addWidget(self._bar)
        layout.addWidget(self._lbl_remain)

    def update_progress(self, progress: float, remaining_label: str) -> None:
        """진행률(0.0~1.0)과 남은 시간 레이블을 갱신합니다."""
        self._bar.setValue(int(progress * 100))
        self._lbl_remain.setText(remaining_label)

    def reset(self) -> None:
        self._bar.setValue(0)
        self._lbl_remain.setText("대기 중")
