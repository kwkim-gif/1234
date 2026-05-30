from __future__ import annotations

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
    log_message = Signal(str)               # 로그 메시지
    segment_ready = Signal(dict)            # 실시간 세그먼트

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._queue: deque[Job] = deque()
        self._settings: AppSettings = AppSettings()
        self._engine: BaseWhisperEngine | None = None
        self._ffmpeg = FFmpegHandler()
        self._running = False
        self._stop_requested = False

    # ── 외부 인터페이스 ───────────────────────────────────────────
    def enqueue(self, job: Job) -> None:
        self._queue.append(job)

    def set_settings(self, settings: AppSettings) -> None:
        self._settings = settings

    def request_stop(self) -> None:
        self._stop_requested = True

    # ── 실행 루프 ─────────────────────────────────────────────────
    def run(self) -> None:
        self._running = True
        self._stop_requested = False

        self._load_engine()

        while self._queue and not self._stop_requested:
            job = self._queue.popleft()
            self._process_job(job)

        if self._engine:
            self._engine.unload_model()
        self._running = False

    def _load_engine(self) -> None:
        s = self._settings
        self.log_message.emit(f"[엔진 로드] {s.engine} / {s.model_name}")
        self._engine = create_engine(s.engine, s.model_name)
        try:
            self._engine.load_model(s.model_name, s)
            self.log_message.emit(f"[모델 로드 완료] {s.model_name}")
        except Exception as e:
            self.log_message.emit(f"[모델 로드 실패] {e}")
            self._engine = None

    def _process_job(self, job: Job) -> None:
        if self._engine is None:
            job.status = JobStatus.FAILED
            job.error_message = "엔진 초기화 실패"
            self.job_failed.emit(job.id, job.error_message)
            return

        job.status = JobStatus.PROCESSING
        self.log_message.emit(f"[처리 시작] {job.file_path.name}")
        tmp_audio: Path | None = None

        try:
            # 오디오 추출
            self.log_message.emit(f"[FFmpeg] 오디오 추출 중...")
            tmp_audio = self._ffmpeg.extract_audio(job.file_path, self._settings.audio)

            # 전사
            self.log_message.emit(f"[전사 중] {job.file_path.name}")
            segments: list[dict] = []
            total_duration = self._ffmpeg.get_duration(job.file_path) or 1.0

            for seg in self._engine.transcribe(str(tmp_audio), self._settings.language, self._settings):
                if self._stop_requested:
                    job.status = JobStatus.CANCELLED
                    self.log_message.emit(f"[취소됨] {job.file_path.name}")
                    return

                segments.append(seg)
                self.segment_ready.emit(seg)
                progress = min(seg["end"] / total_duration, 1.0)
                job.progress = progress
                self.progress_updated.emit(job.id, progress)

            # 중복 제거 및 저장
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
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            self.job_failed.emit(job.id, str(e))
            self.log_message.emit(f"[실패] {job.file_path.name}: {e}")

        finally:
            if tmp_audio and tmp_audio.exists():
                tmp_audio.unlink(missing_ok=True)


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
        """전사 작업을 시작하고 워커를 반환합니다."""
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
        if self._worker:
            self._worker.request_stop()

    def get_job(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)
