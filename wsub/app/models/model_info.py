from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto


class ModelState(Enum):
    NOT_DOWNLOADED = auto()
    DOWNLOADING = auto()
    DOWNLOADED = auto()
    UPDATE_AVAILABLE = auto()


@dataclass
class ModelInfo:
    id: str
    name: str
    size_gb: float
    state: ModelState = ModelState.NOT_DOWNLOADED
    download_progress: float = 0.0
    local_path: str = ""
