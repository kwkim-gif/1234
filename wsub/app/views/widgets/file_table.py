from __future__ import annotations

import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QAction, QHeaderView, QMenu, QTableWidget,
    QTableWidgetItem,
)

from app.models.job import Job, JobStatus


_STATUS_COLORS: dict[JobStatus, str] = {
    JobStatus.PENDING:    "#888888",
    JobStatus.PROCESSING: "#4a9eff",
    JobStatus.COMPLETED:  "#4caf50",
    JobStatus.FAILED:     "#f44336",
    JobStatus.CANCELLED:  "#ff9800",
}

_COLUMNS = ["#", "파일명", "경로", "길이", "상태", "진행률"]


class FileTable(QTableWidget):
    """파일 큐를 표시하고 컨텍스트 메뉴를 제공하는 테이블."""

    move_up_requested = Signal(int)
    move_down_requested = Signal(int)
    remove_requested = Signal(int)
    open_output_requested = Signal(int)
    open_folder_requested = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(0, len(_COLUMNS), parent)
        self.setHorizontalHeaderLabels(_COLUMNS)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self.verticalHeader().setVisible(False)
        hh = self.horizontalHeader()
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        self.setColumnWidth(0, 40)
        self.setColumnWidth(3, 60)
        self.setColumnWidth(4, 70)
        self.setColumnWidth(5, 70)
        self.setStyleSheet("QTableWidget { background: #1e1e1e; color: #ddd; gridline-color: #333; }")

    def refresh(self, jobs: list[Job]) -> None:
        """Job 목록으로 테이블을 갱신합니다."""
        self.setRowCount(len(jobs))
        for row, job in enumerate(jobs):
            self._set_row(row, job)

    def update_job_progress(self, job_id: str, jobs: list[Job]) -> None:
        """특정 Job의 진행률 셀만 갱신합니다."""
        for row, job in enumerate(jobs):
            if job.id == job_id:
                self._set_progress_cell(row, job)
                self._set_status_cell(row, job)
                break

    def _set_row(self, row: int, job: Job) -> None:
        def cell(text: str) -> QTableWidgetItem:
            item = QTableWidgetItem(text)
            item.setTextAlignment(Qt.AlignCenter)
            return item

        dur = job.duration
        dur_str = f"{int(dur//60):02d}:{int(dur%60):02d}" if dur > 0 else "--:--"

        self.setItem(row, 0, cell(str(row + 1)))
        self.setItem(row, 1, cell(job.file_path.name))
        self.setItem(row, 2, cell(str(job.file_path.parent)))
        self.setItem(row, 3, cell(dur_str))
        self._set_status_cell(row, job)
        self._set_progress_cell(row, job)

    def _set_status_cell(self, row: int, job: Job) -> None:
        item = QTableWidgetItem(job.status_label())
        item.setTextAlignment(Qt.AlignCenter)
        color = _STATUS_COLORS.get(job.status, "#888")
        item.setForeground(QColor(color))
        self.setItem(row, 4, item)

    def _set_progress_cell(self, row: int, job: Job) -> None:
        pct = int(job.progress * 100)
        item = QTableWidgetItem(f"{pct}%")
        item.setTextAlignment(Qt.AlignCenter)
        self.setItem(row, 5, item)

    def _show_context_menu(self, pos) -> None:
        row = self.rowAt(pos.y())
        if row < 0:
            return

        menu = QMenu(self)
        act_up = menu.addAction("위로 이동")
        act_down = menu.addAction("아래로 이동")
        menu.addSeparator()
        act_remove = menu.addAction("제거")
        menu.addSeparator()
        act_open_file = menu.addAction("출력 파일 열기")
        act_open_folder = menu.addAction("출력 폴더 열기")

        # 완료된 항목만 출력 파일 열기 활성화
        # (활성화 여부는 외부에서 Job 상태로 판단)
        action = menu.exec(self.viewport().mapToGlobal(pos))
        if action == act_up:
            self.move_up_requested.emit(row)
        elif action == act_down:
            self.move_down_requested.emit(row)
        elif action == act_remove:
            self.remove_requested.emit(row)
        elif action == act_open_file:
            self.open_output_requested.emit(row)
        elif action == act_open_folder:
            self.open_folder_requested.emit(row)
