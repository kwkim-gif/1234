from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

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
        self._active_settings: AppSettings | None = None  # 실행 중 설정 (자동 연속 처리용)

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

    def remove_jobs(self, indices: list[int]) -> None:
        """여러 인덱스를 한 번에 삭제합니다 (역순으로 삭제해 인덱스 오류 방지)."""
        for i in sorted(set(indices), reverse=True):
            if 0 <= i < len(self._jobs):
                self._jobs.pop(i)
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
        """미완료 파일 전사를 시작합니다."""
        # 실패·취소 job을 새 객체로 교체 (구 워커의 상태 덮어쓰기 차단)
        for i, job in enumerate(self._jobs):
            if job.status in (JobStatus.FAILED, JobStatus.CANCELLED):
                new_job = self._service.create_job(job.file_path)
                new_job.duration = job.duration
                self._jobs[i] = new_job

        pending = [j for j in self._jobs if j.status == JobStatus.PENDING]
        self.log_appended.emit(
            f"[큐] 전체 {len(self._jobs)}개, PENDING {len(pending)}개"
        )
        if not pending:
            self.log_appended.emit("[큐] 처리할 파일 없음 — 시작 취소")
            return

        self._active_settings = settings
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
        """워커를 중지하고, 완료되지 않은 파일을 PENDING(새 객체)으로 교체합니다."""
        self._active_settings = None
        self._service.stop()

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
        """시작 가능한 Job 수 (PENDING / FAILED / CANCELLED)."""
        return sum(
            1 for j in self._jobs
            if j.status in (JobStatus.PENDING, JobStatus.FAILED, JobStatus.CANCELLED)
        )

    def pending_count(self) -> int:
        return sum(1 for j in self._jobs if j.status == JobStatus.PENDING)

    # ── 콜백 ──────────────────────────────────────────────────────
    def _on_progress(self, job_id: str, progress: float) -> None:
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

        # 워커가 현재 배치를 다 소진했을 때 새로 추가된 PENDING 파일이 있으면 연속 처리
        # (워커 실행 중에 추가된 파일은 해당 워커의 큐에 없으므로 여기서 재시작)
        if not self._service.is_running() and self._active_settings is not None:
            new_pending = [j for j in self._jobs if j.status == JobStatus.PENDING]
            if new_pending:
                self.log_appended.emit(f"[자동 연속] 새로 추가된 파일 {len(new_pending)}개 처리를 시작합니다.")
                self._service.start(
                    jobs=new_pending,
                    settings=self._active_settings,
                    on_progress=self._on_progress,
                    on_completed=self._on_completed,
                    on_failed=self._on_failed,
                    on_log=self._on_log,
                    on_segment=self._on_segment,
                )
                return

        # 모든 job이 완료되면 3초 후 자동 초기화
        # self를 context로 전달해 항상 main thread에서 실행되도록 보장
        if all(j.status == JobStatus.COMPLETED for j in self._jobs):
            self._active_settings = None
            self.log_appended.emit("[완료] 모든 작업이 완료되었습니다. 3초 후 목록을 초기화합니다.")
            QTimer.singleShot(3000, self, self._reset_after_all_completed)

    def _reset_after_all_completed(self) -> None:
        """모든 작업 완료 후 큐를 초기화합니다."""
        # 도중에 새 파일이 추가된 경우(PENDING 있음) 초기화하지 않음
        if any(j.status != JobStatus.COMPLETED for j in self._jobs):
            return
        self._jobs.clear()
        # service.reset()은 모델 언로드 중인 워커를 wait()해 UI를 블로킹할 수 있으므로
        # 여기서는 호출하지 않는다. 다음 start()의 _teardown_worker()에서 정리된다.
        self.jobs_changed.emit()
        self.overall_progress_changed.emit(0.0, "")
        self.log_appended.emit("[초기화] 목록이 초기화되었습니다. 새 파일을 추가하세요.")

    def _on_failed(self, job_id: str, error: str) -> None:
        if not any(j.id == job_id for j in self._jobs):
            return
        self.job_status_changed.emit(job_id)
        self.error_appended.emit(f"[실패] {error}")
        self.jobs_changed.emit()

        # 워커 종료 후 새로 추가된 PENDING 파일이 있으면 연속 처리
        if not self._service.is_running() and self._active_settings is not None:
            new_pending = [j for j in self._jobs if j.status == JobStatus.PENDING]
            if new_pending:
                self.log_appended.emit(f"[자동 연속] 새로 추가된 파일 {len(new_pending)}개 처리를 시작합니다.")
                self._service.start(
                    jobs=new_pending,
                    settings=self._active_settings,
                    on_progress=self._on_progress,
                    on_completed=self._on_completed,
                    on_failed=self._on_failed,
                    on_log=self._on_log,
                    on_segment=self._on_segment,
                )

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
