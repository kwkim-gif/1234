"""CUDA runtime DLL registration for Windows.

Strategy:
1. Search the entire Python environment for cublas64_12.dll and cudnn DLLs.
2. Register each found directory via os.add_dll_directory() AND prepend to PATH.
3. Pre-load the DLLs with ctypes so Windows marks them as already-loaded;
   when CTranslate2 calls LoadLibrary("cublas64_12.dll") during inference it
   gets the already-resident module instead of searching (and failing).

Must be called before any ctranslate2 / faster_whisper import.
"""
from __future__ import annotations

import ctypes
import glob
import os
import sys

_registered = False
_registered_dirs: list[str] = []


def register_cuda_dll_dirs() -> list[str]:
    """Find CUDA 12 DLLs, register their dirs, and pre-load them.

    Returns the list of directories that were added.
    """
    global _registered, _registered_dirs
    if _registered:
        return _registered_dirs
    if sys.platform != "win32":
        _registered = True
        return []

    # ── 1. Collect search roots ────────────────────────────────────────
    roots: list[str] = []

    # Python / venv prefix (nvidia-cublas-cu12 wheel installs here)
    for r in [sys.prefix, os.path.dirname(sys.executable)]:
        if r and os.path.isdir(r):
            roots.append(r)

    # CUDA Toolkit system install
    cuda_path = os.environ.get("CUDA_PATH", "")
    if cuda_path and os.path.isdir(cuda_path):
        roots.append(cuda_path)

    # Common system paths
    for p in [r"C:\Program Files\NVIDIA GPU Computing Toolkit",
              r"C:\Windows\System32"]:
        if os.path.isdir(p):
            roots.append(p)

    # ── 2. Find DLL files ─────────────────────────────────────────────
    target_dlls = [
        "cublas64_12.dll",
        "cublasLt64_12.dll",
        "cudnn64_8.dll",
        "cudnn_ops_infer64_8.dll",
        "cudnn_cnn_infer64_8.dll",
        "cudnn64_9.dll",
        "cudart64_12.dll",
    ]

    found_dirs: set[str] = set()
    found_dlls: dict[str, str] = {}  # dll_name -> full_path

    for root in roots:
        for dll_name in target_dlls:
            if dll_name in found_dlls:
                continue
            # Recursive search limited to a few levels to avoid scanning too deep
            pattern = os.path.join(root, "**", dll_name)
            matches = glob.glob(pattern, recursive=True)
            if matches:
                found_dlls[dll_name] = matches[0]
                found_dirs.add(os.path.dirname(matches[0]))

    # ── 3. Register directories ───────────────────────────────────────
    added: list[str] = []
    for d in found_dirs:
        try:
            os.add_dll_directory(d)          # type: ignore[attr-defined]
        except Exception:
            pass
        # Also prepend to PATH for older LoadLibrary calls
        os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
        added.append(d)

    # ── 4. Pre-load critical DLLs with ctypes ─────────────────────────
    # This places the DLLs in the process's loaded-module list so that
    # CTranslate2's runtime LoadLibrary("cublas64_12.dll") succeeds even
    # when the directory isn't in the DLL search path at call time.
    preload_order = [
        "cudart64_12.dll",
        "cublas64_12.dll",
        "cublasLt64_12.dll",
        "cudnn64_8.dll",
        "cudnn_ops_infer64_8.dll",
        "cudnn_cnn_infer64_8.dll",
        "cudnn64_9.dll",
    ]
    for dll_name in preload_order:
        if dll_name in found_dlls:
            try:
                ctypes.CDLL(found_dlls[dll_name])
            except Exception:
                pass

    _registered = True
    _registered_dirs = added
    return added


def find_cublas_dll() -> str | None:
    """Return the path to cublas64_12.dll if found, else None."""
    for r in [sys.prefix, os.environ.get("CUDA_PATH", ""),
              r"C:\Program Files\NVIDIA GPU Computing Toolkit"]:
        if not r or not os.path.isdir(r):
            continue
        for p in glob.glob(os.path.join(r, "**", "cublas64_12.dll"), recursive=True):
            return p
    return None
