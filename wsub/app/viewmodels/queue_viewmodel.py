from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal

from app.config.constants import SUPPORTED_EXTENSIONS
from app.core.ffmpeg_handler import FFmpegHandler
from app.core.transcription_service import TranscriptionService
from app.models.job import Job, JobStatus
from app.models.settings import AppSettings


class QueueViewModel(QObject):
    """파일 큐 상태를 관리하고 View에 변경을 알립니다."""

    jobs_changed = Signal()
    job_progress_changed = Signal(str, float)
    job_status_changed = Signal(str)
    log_appended = Signal(str)
    error_appended = Signal(str)
    overall_progress_changed = Signal(float, str)
    segment_ready = Signal(dict)

    def __init__(self, service: TranscriptionService, parent=None) -> None:
        super().__init__(parent)
        self._service = service
        self._jobs: list[Job] = []
        self._ffmpeg = FFmpegHandler()

    # ── 큐 조작 ──────────────────────────────────────────────────
    def add_files(self, paths: list[str]) -> None:
        """지원 포맷 파일을 큐에 추가합니다."""
        added = False
        for p in paths:
            path = Path(p)
            if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                self.error_appended.emit(f"지원하지 않는 파일: {path.name}")
                continue
            job = self._service.create_job(path)
            job.duration = self._ffmpeg.get_duration(path)
            self._jobs.append(job)
            added = True
        if added:
            self.jobs_changed.emit()

    def remove_job(self, index: int) -> None:
        if 0 <= index < len(self._jobs):
            self._jobs.pop(index)
            self.jobs_changed.emit()

    def move_up(self, index: int) -> None:
        if index > 0:
            self._jobs[index - 1], self._jobs[index] = self._jobs[index], self._jobs[index - 1]
            self.jobs_changed.emit()

    def move_down(self, index: int) -> None:
        if index < len(self._jobs) - 1:
            self._jobs[index], self._jobs[index + 1] = self._jobs[index + 1], self._jobs[index]
            self.jobs_changed.emit()

    def clear_completed(self) -> None:
        self._jobs = [j for j in self._jobs if j.status != JobStatus.COMPLETED]
        self.jobs_changed.emit()

    # ── 전사 시작 ─────────────────────────────────────────────────
    def start_transcription(self, settings: AppSettings) -> None:
        """미완료 Job들의 전사를 시작합니다."""
        # FAILED/CANCELLED를 PENDING으로 초기화
        for job in self._jobs:
            if job.status in (JobStatus.FAILED, JobStatus.CANCELLED):
                job.status = JobStatus.PENDING
                job.progress = 0.0
                job.error_message = ""

        pending = [j for j in self._jobs if j.status == JobStatus.PENDING]
        if not pending:
            return

        self.jobs_changed.emit()
        self._service.start(
            jobs=pending,
            settings=settings,
            on_progress=self._on_progress,
            on_completed=self._on_completed,
            on_failed=self._on_failed,
            on_log=self._on_log,
            on_segment=self._on_segment,
        )

    def stop_transcription(self) -> None:
        """워커를 중지하고 미완료 파일을 즉시 PENDING으로 리셋합니다.

        완료된 파일은 유지하고, 나머지(처리중/대기중/실패/취소)는
        0%로 초기화하여 다음 시작 시 바로 재처리할 수 있게 합니다.
        """
        self._service.stop()

        # UI 즉시 반영 — 워커 종료를 기다리지 않고 상태 리셋
        reset_statuses = {
            JobStatus.PROCESSING, JobStatus.PENDING,
            JobStatus.FAILED, JobStatus.CANCELLED,
        }
        for job in self._jobs:
            if job.status in reset_statuses:
                job.status = JobStatus.PENDING
                job.progress = 0.0
                job.error_message = ""

        self.jobs_changed.emit()
        self._update_overall_progress()

    # ── 조회 ──────────────────────────────────────────────────────
    def jobs(self) -> list[Job]:
        return list(self._jobs)

    def startable_count(self) -> int:
        """시작 가능한 Job 수 (PENDING + FAILED + CANCELLED)."""
        return sum(
            1 for j in self._jobs
            if j.status in (JobStatus.PENDING, JobStatus.FAILED, JobStatus.CANCELLED)
        )

    def pending_count(self) -> int:
        return sum(1 for j in self._jobs if j.status == JobStatus.PENDING)

    # ── 콜백 ──────────────────────────────────────────────────────
    def _on_progress(self, job_id: str, progress: float) -> None:
        self.job_progress_changed.emit(job_id, progress)
        self._update_overall_progress()

    def _on_completed(self, job_id: str, output_path: str) -> None:
        self.job_status_changed.emit(job_id)
        self.jobs_changed.emit()
        self._update_overall_progress()

    def _on_failed(self, job_id: str, error: str) -> None:
        self.job_status_changed.emit(job_id)
        self.error_appended.emit(f"[실패] {error}")
        self.jobs_changed.emit()

    def _on_log(self, message: str) -> None:
        self.log_appended.emit(message)

    def _on_segment(self, segment: dict) -> None:
        self.segment_ready.emit(segment)

    def _update_overall_progress(self) -> None:
        if not self._jobs:
            return
        total = sum(j.progress for j in self._jobs)
        pct = total / len(self._jobs)
        done = sum(1 for j in self._jobs if j.status == JobStatus.COMPLETED)
        remaining_label = f"{len(self._jobs) - done}개 남음"
        self.overall_progress_changed.emit(pct, remaining_label)
