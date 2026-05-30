from __future__ import annotations

import time
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
    """백그라운드 전사 워커. 모든 예외를 캐치하여 Signal로 보고합니다."""

    progress_updated = Signal(str, float)
    job_completed = Signal(str, str)
    job_failed = Signal(str, str)
    log_message = Signal(str)
    segment_ready = Signal(dict)
    worker_finished = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._queue: deque[Job] = deque()
        self._settings: AppSettings = AppSettings()
        self._engine: BaseWhisperEngine | None = None
        self._ffmpeg = FFmpegHandler()
        self._stop_requested = False
        # 이 워커가 처리하는 job들의 ID 집합 (다른 워커의 시그널과 구분)
        self._owned_job_ids: set[str] = set()

    def enqueue(self, job: Job) -> None:
        self._queue.append(job)
        self._owned_job_ids.add(job.id)

    def set_settings(self, settings: AppSettings) -> None:
        self._settings = settings

    def request_stop(self) -> None:
        self._stop_requested = True

    def run(self) -> None:
        try:
            self._run_inner()
        except BaseException as e:
            tb = traceback.format_exc()
            self.log_message.emit(f"[워커 비정상 종료] {e}\n{tb}")
            while self._queue:
                job = self._queue.popleft()
                if job.id in self._owned_job_ids:
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

        # 모델 로드 중 중지 요청이 들어온 경우 즉시 종료
        if self._stop_requested:
            return

        while self._queue and not self._stop_requested:
            job = self._queue.popleft()
            # 중지 후 재시작으로 job이 새 워커로 넘어간 경우 스킵
            if job.id not in self._owned_job_ids:
                continue
            if job.status == JobStatus.CANCELLED:
                continue
            self._process_job(job)

        if self._engine:
            self._engine.unload_model()
            self._engine = None

    def _load_engine(self) -> None:
        s = self._settings
        self.log_message.emit(f"[엔진 로드] {s.engine} / {s.model_name}")
        self._engine = create_engine(s.engine, s.model_name)
        if hasattr(self._engine, "set_logger"):
            self._engine.set_logger(self.log_message.emit)
        try:
            self._engine.load_model(s.model_name, s)
            self.log_message.emit(f"[모델 로드 완료] {s.model_name}")
        except Exception as e:
            tb = traceback.format_exc()
            self.log_message.emit(f"[모델 로드 실패] {e}\n{tb}")
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
            last_emit = 0.0

            for seg in self._engine.transcribe(
                str(tmp_audio), self._settings.language, self._settings
            ):
                if self._stop_requested or job.id not in self._owned_job_ids:
                    job.status = JobStatus.CANCELLED
                    self.log_message.emit(f"[취소됨] {job.file_path.name}")
                    return

                segments.append(seg)
                self.segment_ready.emit(seg)
                progress = min(seg["end"] / total_duration, 1.0)
                job.progress = progress
                # GUI 이벤트 루프 포화를 막기 위해 진행률 신호를 throttle (최대 ~5회/초)
                now = time.monotonic()
                if progress >= 1.0 or now - last_emit >= 0.2:
                    self.progress_updated.emit(job.id, progress)
                    last_emit = now

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
        """이전 워커를 완전히 종료시킨 뒤 새 워커를 시작합니다."""
        self._teardown_worker()

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
        self._teardown_worker()

    def is_running(self) -> bool:
        return bool(self._worker and self._worker.isRunning())

    def reset(self) -> None:
        """완료 후 서비스를 초기 상태로 되돌립니다. 워커가 살아있으면 먼저 종료합니다."""
        self._teardown_worker()
        self._worker = None
        self._jobs.clear()

    def _teardown_worker(self) -> None:
        """이전 워커의 신호를 끊고 스레드가 완전히 종료될 때까지 대기합니다.

        QThread를 wait()로 확실히 종료시키지 않으면, 새 워커 시작 시
        이전 스레드의 CUDA/모델 상태가 남아 두 번째 실행이 멈추는 문제가 발생합니다.
        """
        if not self._worker:
            return
        try:
            self._worker.disconnect()
        except RuntimeError:
            pass
        self._worker.request_stop()
        if self._worker.isRunning():
            # 최대 10초 대기 (모델 언로드/추론 종료 시간 확보)
            if not self._worker.wait(10000):
                self._worker.terminate()
                self._worker.wait(2000)
        self._worker = None

    def get_job(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)
