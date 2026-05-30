from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QHBoxLayout, QHeaderView, QLabel,
    QMessageBox, QProgressBar, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout,
)

from app.models.model_info import ModelInfo, ModelState
from app.viewmodels.model_manager_viewmodel import ModelManagerViewModel


class ModelDialog(QDialog):
    """모델 다운로드/삭제/업데이트 관리 다이얼로그."""

    def __init__(self, vm: ModelManagerViewModel, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("모델 관리")
        self.resize(640, 400)
        self._vm = vm

        layout = QVBoxLayout(self)

        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(["모델명", "크기", "상태", "진행률", "작업"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self._table)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        vm.models_changed.connect(self._refresh)
        vm.download_progress.connect(self._on_download_progress)
        vm.download_finished.connect(lambda _: self._refresh())
        vm.download_failed.connect(self._on_download_failed)

        self._refresh()

    def _refresh(self) -> None:
        models = self._vm.models()
        self._table.setRowCount(len(models))
        for row, info in enumerate(models):
            self._set_row(row, info)

    def _set_row(self, row: int, info: ModelInfo) -> None:
        def cell(text: str, align=Qt.AlignCenter) -> QTableWidgetItem:
            item = QTableWidgetItem(text)
            item.setTextAlignment(align)
            return item

        state_labels = {
            ModelState.NOT_DOWNLOADED: "미다운로드",
            ModelState.DOWNLOADING:    "다운로드중",
            ModelState.DOWNLOADED:     "다운로드됨",
            ModelState.UPDATE_AVAILABLE: "업데이트 가능",
        }

        self._table.setItem(row, 0, cell(info.name, Qt.AlignLeft | Qt.AlignVCenter))
        self._table.setItem(row, 1, cell(f"{info.size_gb:.2f} GB"))
        self._table.setItem(row, 2, cell(state_labels.get(info.state, "")))

        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(int(info.download_progress * 100))
        self._table.setCellWidget(row, 3, bar)

        btn_widget = QWidget()
        btn_layout = QHBoxLayout(btn_widget)
        btn_layout.setContentsMargins(4, 2, 4, 2)
        btn_layout.setSpacing(4)

        if info.state in (ModelState.NOT_DOWNLOADED, ModelState.UPDATE_AVAILABLE):
            btn = QPushButton("다운로드")
            btn.clicked.connect(lambda _, mid=info.id: self._vm.download(mid))
            btn_layout.addWidget(btn)
        elif info.state == ModelState.DOWNLOADED:
            btn_del = QPushButton("삭제")
            btn_del.clicked.connect(lambda _, mid=info.id: self._confirm_delete(mid))
            btn_layout.addWidget(btn_del)

        self._table.setCellWidget(row, 4, btn_widget)

    def _on_download_progress(self, model_id: str, progress: float) -> None:
        models = self._vm.models()
        for row, info in enumerate(models):
            if info.id == model_id:
                bar = self._table.cellWidget(row, 3)
                if isinstance(bar, QProgressBar):
                    bar.setValue(int(progress * 100))
                break

    def _on_download_failed(self, model_id: str, error: str) -> None:
        QMessageBox.critical(self, "다운로드 실패", f"모델 다운로드 실패:\n{error}")
        self._refresh()

    def _confirm_delete(self, model_id: str) -> None:
        reply = QMessageBox.question(
            self, "모델 삭제",
            "선택한 모델을 로컬에서 삭제하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._vm.delete(model_id)
