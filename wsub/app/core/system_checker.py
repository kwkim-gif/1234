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
    cuda_ok, cuda_ver = _check_cuda()
    return SystemInfo(
        python_version=_python_version(),
        python_ok=sys.version_info >= (3, 11),
        ffmpeg_available=_check_ffmpeg()[0],
        ffmpeg_version=_check_ffmpeg()[1],
        cuda_available=cuda_ok,
        cuda_version=cuda_ver,
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
    # 1순위: ctranslate2 (faster-whisper 실제 백엔드) — torch 설치 없이도 감지
    try:
        import ctranslate2
        if ctranslate2.get_cuda_device_count() > 0:
            ver = _get_cuda_version_from_nvml()
            return True, ver or "detected"
    except Exception:
        pass

    # 2순위: torch
    try:
        import torch
        if torch.cuda.is_available():
            return True, torch.version.cuda or "unknown"
    except ImportError:
        pass

    # 3순위: nvidia-ml-py / pynvml
    try:
        import pynvml
        pynvml.nvmlInit()
        return True, _get_cuda_version_from_nvml() or "detected"
    except Exception:
        pass

    return False, ""


def _get_cuda_version_from_nvml() -> str:
    """NVML을 통해 CUDA 드라이버 버전을 가져옵니다."""
    try:
        import pynvml
        pynvml.nvmlInit()
        ver = pynvml.nvmlSystemGetCudaDriverVersion_v2()
        major, minor = divmod(ver, 1000)
        return f"{major}.{minor // 10}"
    except Exception:
        pass
    # ctranslate2에서 버전 추출 시도
    try:
        import ctranslate2
        info = ctranslate2.__version__
        return ""
    except Exception:
        return ""


def _gpu_name() -> str:
    # ctranslate2/NVML 우선 시도
    try:
        import pynvml
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        return pynvml.nvmlDeviceGetName(handle)
    except Exception:
        pass
    try:
        import torch
        if torch.cuda.is_available():
            return torch.cuda.get_device_name(0)
    except Exception:
        pass
    # nvidia-smi 직접 실행
    try:
        import subprocess
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5,
        )
        name = result.stdout.strip()
        if name:
            return name
    except Exception:
        pass
    return "N/A"


def _gpu_vram() -> float:
    try:
        import pynvml
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        return round(info.total / (1024 ** 3), 1)
    except Exception:
        pass
    try:
        import torch
        if torch.cuda.is_available():
            props = torch.cuda.get_device_properties(0)
            return round(props.total_memory / (1024 ** 3), 1)
    except Exception:
        pass
    try:
        import subprocess
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        mb = result.stdout.strip()
        if mb:
            return round(int(mb) / 1024, 1)
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
