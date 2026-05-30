#!/usr/bin/env python
"""W-Sub CUDA 환경 점검 스크립트.

PyTorch / CTranslate2 의 CUDA 인식 여부와 cublas64_12.dll 존재를 확인합니다.
reinstall_cuda.ps1 마지막 단계에서 호출됩니다.
"""
from __future__ import annotations

import os
import sys


def check_torch() -> None:
    print("[PyTorch]")
    try:
        import torch
        print(f"  버전: {torch.__version__}")
        avail = torch.cuda.is_available()
        print(f"  CUDA 사용 가능: {avail}")
        print(f"  CUDA 버전: {torch.version.cuda if avail else 'N/A'}")
        if avail:
            print(f"  GPU: {torch.cuda.get_device_name(0)}")
    except Exception as e:
        print(f"  [오류] {e}")


def check_ctranslate2() -> None:
    print("\n[CTranslate2]")
    try:
        import ctranslate2
        print(f"  버전: {ctranslate2.__version__}")
        devs = ctranslate2.get_cuda_device_count()
        print(f"  CUDA 장치 수: {devs}")
        if devs == 0:
            print("  [주의] CUDA 장치를 인식하지 못했습니다 (CPU로 동작).")
    except Exception as e:
        print(f"  [오류] {e}")


def find_cublas() -> None:
    print("\n[cublas64_12.dll 탐색]")
    roots: list[str] = []
    cuda_path = os.environ.get("CUDA_PATH")
    if cuda_path:
        roots.append(cuda_path)
    roots.append(sys.prefix)  # 가상환경/파이썬 설치 경로 (nvidia 휠 포함)

    for base in roots:
        if not base or not os.path.isdir(base):
            continue
        for root, _dirs, files in os.walk(base):
            for f in files:
                if f.lower() == "cublas64_12.dll":
                    print(f"  발견: {os.path.join(root, f)}")
                    return
    print("  [주의] cublas64_12.dll 을 찾지 못했습니다.")
    print("         nvidia-cublas-cu12 휠 또는 CUDA Toolkit 12.x 설치가 필요합니다.")


if __name__ == "__main__":
    check_torch()
    check_ctranslate2()
    find_cublas()
