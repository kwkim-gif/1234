from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path


class JobStatus(Enum):
    PENDING = auto()
    PROCESSING = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()


STATUS_LABELS: dict[JobStatus, str] = {
    JobStatus.PENDING: "대기중",
    JobStatus.PROCESSING: "처리중",
    JobStatus.COMPLETED: "완료",
    JobStatus.FAILED: "실패",
    JobStatus.CANCELLED: "취소됨",
}


@dataclass
class Job:
    id: str
    file_path: Path
    status: JobStatus = JobStatus.PENDING
    progress: float = 0.0
    duration: float = 0.0
    error_message: str = ""
    output_path: Path | None = None

    def status_label(self) -> str:
        return STATUS_LABELS.get(self.status, "")
