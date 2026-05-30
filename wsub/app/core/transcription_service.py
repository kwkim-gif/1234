from __future__ import annotations

import traceback
import uuid
from collections import deque
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QThread, Signal

from app.core.ffmpeg_handler import FFmpegHandler
from app.core.subtitle_writer import (
    build_output_path, remove_duplicate_segments, write_srt, write_txt,
)
from app.engines import create_engine, BaseWhisperEngine
from app.models.job import Job, JobStatus
from app.models.settings import AppSettings


class TranscriptionWorker(QThread):
    """백그라운드에서 전사 큐를 처리하는 워커 스레드."""

    progress_updated = Signal(str, float)   # job_id, 0.0~1.0
    job_completed = Signal(str, str)        # job_id, output_path
    job_failed = Signal(str, str)           # job_id, error_message
    log_message = Signal(str)
    segment_ready = Signal(dict)
    worker_finished = Signal()              # 스레드 종료 알림

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._queue: deque[Job] = deque()
        self._settings: AppSettings = AppSettings()
        self._engine: BaseWhisperEngine | None = None
        self._ffmpeg = FFmpegHandler()
        self._stop_requested = False

    def enqueue(self, job: Job) -> None:
        self._queue.append(job)

    def set_settings(self, settings: AppSettings) -> None:
        self._settings = settings

    def request_stop(self) -> None:
        self._stop_requested = True

    # ── 실행 루프 ─────────────────────────────────────────────────
    def run(self) -> None:
        """전사 큐를 처리합니다. 모든 예외를 잡아 Signal로 보고합니다."""
        try:
            self._run_inner()
        except BaseException as e:
            # C++ 레벨 예외 포함 모든 예외를 캐치하여 로그로 전달
            tb = traceback.format_exc()
            self.log_message.emit(f"[워커 비정상 종료] {e}\n{tb}")
            # 남은 큐의 job들을 모두 실패 처리
            while self._queue:
                job = self._queue.popleft()
                job.status = JobStatus.FAILED
                job.error_message = f"워커 오류: {e}"
                self.job_failed.emit(job.id, job.error_message)
        finally:
            if self._engine:
                try:
                    self._engine.unload_model()
                except Exception:
                    pass
            self.worker_finished.emit()

    def _run_inner(self) -> None:
        self._stop_requested = False
        self._load_engine()

        while self._queue and not self._stop_requested:
            job = self._queue.popleft()
            if job.status == JobStatus.CANCELLED:
                # 큐에 남아있는 동안 취소된 경우 건너뜀
                continue
            self._process_job(job)

    def _load_engine(self) -> None:
        s = self._settings
        self.log_message.emit(f"[엔진 로드] {s.engine} / {s.model_name}")
        self._engine = create_engine(s.engine, s.model_name)
        try:
            self._engine.load_model(s.model_name, s)
            self.log_message.emit(f"[모델 로드 완료] {s.model_name}")
        except Exception as e:
            tb = traceback.format_exc()
            self.log_message.emit(f"[모델 로드 실패] {e}")
            self.log_message.emit(f"[상세 오류]\n{tb}")
            self._engine = None

    def _process_job(self, job: Job) -> None:
        if self._engine is None:
            job.status = JobStatus.FAILED
            job.error_message = "엔진 초기화 실패 — 에러 로그를 확인하세요."
            self.job_failed.emit(job.id, job.error_message)
            return

        job.status = JobStatus.PROCESSING
        self.log_message.emit(f"[처리 시작] {job.file_path.name}")
        tmp_audio: Path | None = None

        try:
            self.log_message.emit("[FFmpeg] 오디오 추출 중...")
            tmp_audio = self._ffmpeg.extract_audio(job.file_path, self._settings.audio)

            self.log_message.emit(f"[전사 중] {job.file_path.name}")
            segments: list[dict] = []
            total_duration = self._ffmpeg.get_duration(job.file_path) or 1.0

            for seg in self._engine.transcribe(
                str(tmp_audio), self._settings.language, self._settings
            ):
                if self._stop_requested:
                    job.status = JobStatus.CANCELLED
                    self.log_message.emit(f"[취소됨] {job.file_path.name}")
                    return

                segments.append(seg)
                self.segment_ready.emit(seg)
                progress = min(seg["end"] / total_duration, 1.0)
                job.progress = progress
                self.progress_updated.emit(job.id, progress)

            if getattr(self._settings, "dedup_segments", True):
                segments = remove_duplicate_segments(segments)

            output_path = build_output_path(
                job.file_path, self._settings.output_dir,
                self._settings.language, self._settings.output_format,
            )
            if self._settings.output_format == "srt":
                write_srt(segments, output_path)
            else:
                write_txt(segments, output_path)

            job.status = JobStatus.COMPLETED
            job.output_path = output_path
            job.progress = 1.0
            self.progress_updated.emit(job.id, 1.0)
            self.job_completed.emit(job.id, str(output_path))
            self.log_message.emit(f"[완료] {output_path.name}")

        except Exception as e:
            tb = traceback.format_exc()
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            self.job_failed.emit(job.id, str(e))
            self.log_message.emit(f"[실패] {job.file_path.name}: {e}\n{tb}")

        finally:
            if tmp_audio and tmp_audio.exists():
                try:
                    tmp_audio.unlink(missing_ok=True)
                except Exception:
                    pass


class TranscriptionService:
    """Job 생성 및 워커 라이프사이클 관리."""

    def __init__(self) -> None:
        self._worker: TranscriptionWorker | None = None
        self._jobs: dict[str, Job] = {}

    def create_job(self, file_path: Path) -> Job:
        """새 Job을 생성합니다."""
        job = Job(id=str(uuid.uuid4()), file_path=file_path)
        self._jobs[job.id] = job
        return job

    def start(
        self,
        jobs: list[Job],
        settings: AppSettings,
        on_progress: Callable[[str, float], None],
        on_completed: Callable[[str, str], None],
        on_failed: Callable[[str, str], None],
        on_log: Callable[[str], None],
        on_segment: Callable[[dict], None],
    ) -> TranscriptionWorker:
        """이전 워커를 정리한 뒤 새 워커를 시작합니다."""
        # 이전 워커가 살아있으면 신호를 끊고 종료 대기 (최대 2초)
        if self._worker and self._worker.isRunning():
            self._worker.request_stop()
            self._worker.disconnect()
            self._worker.wait(2000)

        worker = TranscriptionWorker()
        worker.set_settings(settings)
        for job in jobs:
            worker.enqueue(job)

        worker.progress_updated.connect(on_progress)
        worker.job_completed.connect(on_completed)
        worker.job_failed.connect(on_failed)
        worker.log_message.connect(on_log)
        worker.segment_ready.connect(on_segment)

        self._worker = worker
        worker.start()
        return worker

    def stop(self) -> None:
        """실행 중인 워커에 중지를 요청합니다."""
        if self._worker and self._worker.isRunning():
            self._worker.request_stop()

    def is_running(self) -> bool:
        return bool(self._worker and self._worker.isRunning())

    def get_job(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)
