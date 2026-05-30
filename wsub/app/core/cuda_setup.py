"""CUDA 런타임 DLL 경로 등록.

faster-whisper(CTranslate2)는 CUDA 12용 cublas64_12.dll / cudnn DLL을 필요로 합니다.
시스템에 torch cu118만 설치된 경우 cublas64_12.dll을 찾지 못해 CPU로 폴백됩니다.
nvidia pip 휠(nvidia-cublas-cu12, nvidia-cudnn-cu12)이 설치되어 있으면
해당 DLL 디렉터리를 Windows DLL 검색 경로에 등록하여 CUDA를 사용할 수 있게 합니다.

faster_whisper를 import하기 전에 register_cuda_dll_dirs()를 호출해야 합니다.
"""
from __future__ import annotations

import os
import sys

_registered = False


def register_cuda_dll_dirs() -> list[str]:
    """nvidia pip 휠의 DLL 디렉터리를 등록합니다. 등록된 경로 목록을 반환합니다."""
    global _registered
    added: list[str] = []
    if _registered or sys.platform != "win32":
        return added

    candidates: list[str] = []

    # 1) nvidia pip 휠 패키지 (nvidia-cublas-cu12, nvidia-cudnn-cu12 등)
    try:
        import nvidia  # type: ignore
        nvidia_root = os.path.dirname(nvidia.__file__)
        for sub in ("cublas", "cudnn", "cuda_runtime", "cuda_nvrtc"):
            bin_dir = os.path.join(nvidia_root, sub, "bin")
            if os.path.isdir(bin_dir):
                candidates.append(bin_dir)
    except Exception:
        pass

    # 2) CUDA Toolkit 표준 설치 경로 (CUDA_PATH 환경변수)
    cuda_path = os.environ.get("CUDA_PATH")
    if cuda_path:
        bin_dir = os.path.join(cuda_path, "bin")
        if os.path.isdir(bin_dir):
            candidates.append(bin_dir)

    for d in candidates:
        try:
            os.add_dll_directory(d)  # type: ignore[attr-defined]
            os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
            added.append(d)
        except Exception:
            pass

    _registered = True
    return added
