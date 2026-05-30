#!/usr/bin/env python
"""W-Sub CUDA environment check.

Verifies PyTorch / CTranslate2 CUDA detection and the presence of
cublas64_12.dll. Called at the end of reinstall_cuda.ps1 / .bat.
(ASCII-only output to avoid console encoding issues.)
"""
from __future__ import annotations

import os
import sys


def check_torch() -> None:
    print("[PyTorch]")
    try:
        import torch
        print(f"  version: {torch.__version__}")
        avail = torch.cuda.is_available()
        print(f"  CUDA available: {avail}")
        print(f"  CUDA version: {torch.version.cuda if avail else 'N/A'}")
        if avail:
            print(f"  GPU: {torch.cuda.get_device_name(0)}")
    except Exception as e:
        print(f"  [ERROR] {e}")


def check_ctranslate2() -> None:
    print("\n[CTranslate2]")
    try:
        import ctranslate2
        print(f"  version: {ctranslate2.__version__}")
        devs = ctranslate2.get_cuda_device_count()
        print(f"  CUDA device count: {devs}")
        if devs == 0:
            print("  [WARN] No CUDA device detected (will run on CPU).")
    except Exception as e:
        print(f"  [ERROR] {e}")


def find_cublas() -> None:
    print("\n[cublas64_12.dll search]")
    roots: list[str] = []
    cuda_path = os.environ.get("CUDA_PATH")
    if cuda_path:
        roots.append(cuda_path)
    roots.append(sys.prefix)  # venv / python install (includes nvidia wheels)

    for base in roots:
        if not base or not os.path.isdir(base):
            continue
        for root, _dirs, files in os.walk(base):
            for f in files:
                if f.lower() == "cublas64_12.dll":
                    print(f"  found: {os.path.join(root, f)}")
                    return
    print("  [WARN] cublas64_12.dll not found.")
    print("         Needs nvidia-cublas-cu12 wheel or CUDA Toolkit 12.x.")


if __name__ == "__main__":
    check_torch()
    check_ctranslate2()
    find_cublas()
