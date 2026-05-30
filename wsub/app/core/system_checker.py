from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass


@dataclass
class SystemInfo:
    python_version: str
    python_ok: bool
    ffmpeg_available: bool
    ffmpeg_version: str
    cuda_available: bool
    cuda_version: str
    gpu_name: str
    gpu_vram_gb: float
    hf_cache_dir: str
    disk_free_gb: float
    internet_available: bool


def check_system() -> SystemInfo:
    """시스템 환경을 전반적으로 검사하여 SystemInfo를 반환합니다."""
    return SystemInfo(
        python_version=_python_version(),
        python_ok=sys.version_info >= (3, 11),
        ffmpeg_available=_check_ffmpeg()[0],
        ffmpeg_version=_check_ffmpeg()[1],
        cuda_available=_check_cuda()[0],
        cuda_version=_check_cuda()[1],
        gpu_name=_gpu_name(),
        gpu_vram_gb=_gpu_vram(),
        hf_cache_dir=_hf_cache_dir(),
        disk_free_gb=_disk_free_gb(),
        internet_available=_check_internet(),
    )


def _python_version() -> str:
    v = sys.version_info
    return f"{v.major}.{v.minor}.{v.micro}"


def _check_ffmpeg() -> tuple[bool, str]:
    path = shutil.which("ffmpeg")
    if not path:
        return False, ""
    try:
        import subprocess
        result = subprocess.run(
            ["ffmpeg", "-version"], capture_output=True, text=True, timeout=5
        )
        first_line = result.stdout.splitlines()[0] if result.stdout else ""
        version = first_line.split("version")[1].strip().split(" ")[0] if "version" in first_line else "unknown"
        return True, version
    except Exception:
        return True, "unknown"


def _check_cuda() -> tuple[bool, str]:
    try:
        import torch
        if torch.cuda.is_available():
            return True, torch.version.cuda or "unknown"
        return False, ""
    except ImportError:
        return False, ""


def _gpu_name() -> str:
    try:
        import torch
        if torch.cuda.is_available():
            return torch.cuda.get_device_name(0)
    except Exception:
        pass
    return "N/A"


def _gpu_vram() -> float:
    try:
        import torch
        if torch.cuda.is_available():
            props = torch.cuda.get_device_properties(0)
            return round(props.total_memory / (1024 ** 3), 1)
    except Exception:
        pass
    return 0.0


def _hf_cache_dir() -> str:
    try:
        from huggingface_hub import constants as hf_const
        return str(hf_const.HF_HOME)
    except Exception:
        import os
        return str(os.path.expanduser("~/.cache/huggingface"))


def _disk_free_gb() -> float:
    import shutil as sh
    usage = sh.disk_usage(".")
    return round(usage.free / (1024 ** 3), 1)


def _check_internet() -> bool:
    try:
        import socket
        socket.setdefaulttimeout(3)
        socket.create_connection(("8.8.8.8", 53))
        return True
    except Exception:
        return False
