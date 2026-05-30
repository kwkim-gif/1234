from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QLabel


class DropArea(QLabel):
    """파일 드래그앤드롭을 받는 영역."""

    files_dropped = Signal(list)  # list[str]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setText("📂  파일 또는 폴더를 여기에 드롭하세요\n(또는 위 버튼으로 파일 추가)")
        self.setAcceptDrops(True)
        self.setMinimumHeight(100)
        self.setStyleSheet("""
            QLabel {
                border: 2px dashed #888;
                border-radius: 8px;
                color: #aaa;
                font-size: 14px;
                background: #1e1e1e;
                padding: 20px;
            }
            QLabel:hover {
                border-color: #4a9eff;
                color: #4a9eff;
            }
        """)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet(self.styleSheet().replace("#888", "#4a9eff"))

    def dragLeaveEvent(self, event) -> None:
        self.setStyleSheet(self.styleSheet().replace("#4a9eff", "#888"))

    def dropEvent(self, event: QDropEvent) -> None:
        self.setStyleSheet(self.styleSheet().replace("#4a9eff", "#888"))
        paths: list[str] = []
        for url in event.mimeData().urls():
            local = url.toLocalFile()
            import os
            if os.path.isdir(local):
                for root, _, files in os.walk(local):
                    for f in files:
                        paths.append(os.path.join(root, f))
            else:
                paths.append(local)
        if paths:
            self.files_dropped.emit(paths)
