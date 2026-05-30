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
        """미완료 파일 전사를 시작합니다.

        FAILED/CANCELLED 상태의 Job은 새 Job 객체로 교체하여
        구 워커가 상태를 덮어쓰는 race condition을 방지합니다.
        """
        # 실패·취소 job을 새 객체로 교체 (구 워커의 상태 덮어쓰기 차단)
        for i, job in enumerate(self._jobs):
            if job.status in (JobStatus.FAILED, JobStatus.CANCELLED):
                new_job = self._service.create_job(job.file_path)
                new_job.duration = job.duration
                self._jobs[i] = new_job

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
        """워커를 중지하고, 완료되지 않은 파일을 즉시 PENDING(새 객체)으로 교체합니다.

        - 워커 Signal 단절 → 구 워커의 상태 덮어쓰기 차단
        - 완료된 Job은 유지, 나머지는 새 Job 객체로 교체하여 깨끗한 재시작 보장
        """
        self._service.stop()  # 내부적으로 disconnect + request_stop

        # 미완료 job을 새 객체로 교체
        reset_statuses = {
            JobStatus.PROCESSING, JobStatus.PENDING,
            JobStatus.FAILED, JobStatus.CANCELLED,
        }
        for i, job in enumerate(self._jobs):
            if job.status in reset_statuses:
                new_job = self._service.create_job(job.file_path)
                new_job.duration = job.duration
                self._jobs[i] = new_job

        self.jobs_changed.emit()
        self._update_overall_progress()

    # ── 조회 ──────────────────────────────────────────────────────
    def jobs(self) -> list[Job]:
        return list(self._jobs)

    def startable_count(self) -> int:
        """시작 가능한 Job 수."""
        return sum(
            1 for j in self._jobs
            if j.status in (JobStatus.PENDING, JobStatus.FAILED, JobStatus.CANCELLED)
        )

    def pending_count(self) -> int:
        return sum(1 for j in self._jobs if j.status == JobStatus.PENDING)

    # ── 콜백 ──────────────────────────────────────────────────────
    def _on_progress(self, job_id: str, progress: float) -> None:
        # 현재 job 목록에 없는 job_id면(구 워커 신호) 무시
        if not any(j.id == job_id for j in self._jobs):
            return
        self.job_progress_changed.emit(job_id, progress)
        self._update_overall_progress()

    def _on_completed(self, job_id: str, output_path: str) -> None:
        if not any(j.id == job_id for j in self._jobs):
            return
        self.job_status_changed.emit(job_id)
        self.jobs_changed.emit()
        self._update_overall_progress()

    def _on_failed(self, job_id: str, error: str) -> None:
        if not any(j.id == job_id for j in self._jobs):
            return
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
