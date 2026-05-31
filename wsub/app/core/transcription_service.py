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

    # 기능 시그널 이름 목록 (worker_finished 제외)
    _FUNC_SIGNALS = ("progress_updated", "job_completed", "job_failed",
                     "log_message", "segment_ready")

    def __init__(self) -> None:
        self._worker: TranscriptionWorker | None = None
        self._jobs: dict[str, Job] = {}
        # 중지 후 자연 종료를 기다리는 이전 워커들 (main thread block 방지)
        self._retiring: list[TranscriptionWorker] = []

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
        """이전 워커의 기능 시그널만 끊고 새 워커를 즉시 시작합니다."""
        self._disconnect_and_retire()

        worker = TranscriptionWorker()
        worker.set_settings(settings)
        for job in jobs:
            worker.enqueue(job)

        worker.progress_updated.connect(on_progress)
        worker.job_completed.connect(on_completed)
        worker.job_failed.connect(on_failed)
        worker.log_message.connect(on_log)
        worker.segment_ready.connect(on_segment)

        # 워커가 자연 종료되면 레퍼런스를 자동 정리 (main thread block 없음)
        # worker_finished는 disconnect_and_retire에서 끊지 않으므로 유지된다.
        _svc = self
        _w = worker
        def _auto_clear():
            if _svc._worker is _w:
                _svc._worker = None
            _svc._retiring = [r for r in _svc._retiring if r is not _w and r.isRunning()]
        worker.worker_finished.connect(_auto_clear)

        self._worker = worker
        worker.start()
        return worker

    def stop(self) -> None:
        """기능 시그널만 끊고 중지 요청 후 즉시 반환합니다."""
        if not self._worker:
            return
        self._disconnect_func_signals(self._worker)
        self._worker.request_stop()
        # self._worker는 유지 — worker_finished 콜백이 종료 시 자동으로 None 처리

    def is_running(self) -> bool:
        return bool(self._worker and self._worker.isRunning())

    def reset(self) -> None:
        """서비스를 초기 상태로 되돌립니다."""
        self._disconnect_and_retire()
        self._worker = None
        self._jobs.clear()

    # ── 내부 헬퍼 ────────────────────────────────────────────────────

    def _disconnect_func_signals(self, worker: TranscriptionWorker) -> None:
        """progress/completed/failed/log/segment 시그널만 끊습니다.
        worker_finished는 유지해 자동 cleanup 콜백이 동작하게 합니다.
        """
        for sig_name in self._FUNC_SIGNALS:
            try:
                getattr(worker, sig_name).disconnect()
            except RuntimeError:
                pass

    def _disconnect_and_retire(self) -> None:
        """현재 워커의 기능 시그널을 끊고, 실행 중이면 retire 목록에 보관합니다."""
        if self._worker:
            self._disconnect_func_signals(self._worker)
            self._worker.request_stop()
            if self._worker.isRunning():
                self._retiring.append(self._worker)
            self._worker = None

        # 이미 종료된 retire 워커 정리
        self._retiring = [w for w in self._retiring if w.isRunning()]

    def get_job(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)
