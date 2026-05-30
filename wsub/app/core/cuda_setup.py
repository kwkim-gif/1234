"""CUDA runtime DLL registration for Windows.

Finds cublas64_12.dll / cudnn DLLs from multiple sources in priority order:
  1. ctranslate2 package dir (CUDA wheel bundles DLLs there)
  2. nvidia pip wheels (nvidia-cublas-cu12 etc.)
  3. torch/lib (if CUDA torch is installed)
  4. CUDA_PATH (system CUDA toolkit)
  5. Common system paths

Then registers dirs via os.add_dll_directory() + PATH, and ctypes-preloads
the DLLs in dependency order so CTranslate2's lazy LoadLibrary succeeds.
"""
from __future__ import annotations

import ctypes
import glob
import os
import sys

_registered = False
_diagnostics: list[str] = []


def register_cuda_dll_dirs(log=None) -> list[str]:
    global _registered, _diagnostics
    if _registered:
        if log:
            for line in _diagnostics:
                log(line)
        return _diagnostics
    if sys.platform != "win32":
        _registered = True
        return []

    diag: list[str] = []

    def _emit(msg: str) -> None:
        diag.append(msg)
        if log:
            log(msg)

    roots: list[str] = []

    # ── Priority 0: frozen EXE bundle dir (_internal) ─────────────────
    # PyInstaller가 번들한 cublas/cudnn DLL이 여기에 위치한다.
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass and os.path.isdir(meipass):
            roots.append(meipass)
        exe_dir = os.path.dirname(sys.executable)
        if os.path.isdir(exe_dir):
            roots.append(exe_dir)
            internal = os.path.join(exe_dir, "_internal")
            if os.path.isdir(internal):
                roots.append(internal)

    # ── Priority 1: ctranslate2 package dir ───────────────────────────
    # The CUDA wheel of CTranslate2 bundles cublas64_12.dll inside its package.
    try:
        import ctranslate2 as _ct2
        ct2_dir = os.path.dirname(_ct2.__file__)
        roots.append(ct2_dir)
        _emit(f"[CUDA] ctranslate2 {_ct2.__version__} dir: {ct2_dir}")
        devs = _ct2.get_cuda_device_count()
        _emit(f"[CUDA] ctranslate2 CUDA device count: {devs}")
    except Exception as e:
        _emit(f"[CUDA] ctranslate2 import 실패: {e}")

    # ── Priority 2: nvidia pip wheels ─────────────────────────────────
    try:
        import nvidia as _nv
        nv_base = os.path.dirname(_nv.__file__)
        for sub in ("cublas/bin", "cudnn/bin", "cuda_runtime/bin",
                    "cublas", "cudnn", "cuda_runtime"):
            p = os.path.join(nv_base, sub)
            if os.path.isdir(p):
                roots.append(p)
        _emit(f"[CUDA] nvidia wheel 발견: {nv_base}")
    except Exception:
        pass

    # ── Priority 3: torch/lib ─────────────────────────────────────────
    try:
        import torch as _torch
        is_cuda = "+cu" in _torch.__version__ or _torch.cuda.is_available()
        _emit(f"[CUDA] torch {_torch.__version__} (cuda={is_cuda})")
        if not is_cuda:
            _emit("[CUDA] torch는 CPU 빌드 (전사는 ctranslate2 GPU 백엔드를 사용하므로 무관)")
        tlib = os.path.join(os.path.dirname(_torch.__file__), "lib")
        if os.path.isdir(tlib):
            roots.append(tlib)
            try:
                os.add_dll_directory(tlib)  # type: ignore[attr-defined]
            except Exception:
                pass
            os.environ["PATH"] = tlib + os.pathsep + os.environ.get("PATH", "")
    except Exception as e:
        _emit(f"[CUDA] torch import 실패: {e}")

    # ── Priority 4: CUDA_PATH (system toolkit) ────────────────────────
    cuda_path = os.environ.get("CUDA_PATH", "")
    if cuda_path and os.path.isdir(cuda_path):
        roots.append(os.path.join(cuda_path, "bin"))
        roots.append(cuda_path)
        _emit(f"[CUDA] CUDA_PATH: {cuda_path}")

    # ── Priority 5: common system paths ──────────────────────────────
    for p in [sys.prefix, os.path.dirname(sys.executable),
              r"C:\Program Files\NVIDIA GPU Computing Toolkit",
              r"C:\Windows\System32"]:
        if p and os.path.isdir(p):
            roots.append(p)

    # ── Find DLL files ────────────────────────────────────────────────
    target_dlls = [
        "cudart64_12.dll",
        "cublas64_12.dll", "cublasLt64_12.dll",
        "cudnn64_8.dll", "cudnn_ops_infer64_8.dll", "cudnn_cnn_infer64_8.dll",
        "cudnn64_9.dll", "cudnn_ops64_9.dll", "cudnn_cnn64_9.dll",
    ]
    found_dlls: dict[str, str] = {}
    for root in roots:
        if not root or not os.path.isdir(root):
            continue
        for dll_name in target_dlls:
            if dll_name in found_dlls:
                continue
            # Check the directory itself first (no recursion for speed)
            direct = os.path.join(root, dll_name)
            if os.path.isfile(direct):
                found_dlls[dll_name] = direct
                continue
            # Then recursive glob (for nested like Lib/site-packages/...)
            matches = glob.glob(os.path.join(root, "**", dll_name), recursive=True)
            if matches:
                found_dlls[dll_name] = matches[0]

    if "cublas64_12.dll" in found_dlls:
        _emit(f"[CUDA] cublas64_12.dll 발견: {found_dlls['cublas64_12.dll']}")
    else:
        _emit("[CUDA] ⚠️ cublas64_12.dll 없음 — reinstall_cuda_run.bat 재실행 필요")

    # ── Register directories ──────────────────────────────────────────
    added_dirs: set[str] = set()
    for path in found_dlls.values():
        d = os.path.dirname(path)
        if d in added_dirs:
            continue
        try:
            os.add_dll_directory(d)  # type: ignore[attr-defined]
        except Exception:
            pass
        os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
        added_dirs.add(d)

    # ── ctypes pre-load in dependency order ───────────────────────────
    preload_order = [
        "cudart64_12.dll",
        "cublasLt64_12.dll", "cublas64_12.dll",
        "cudnn64_8.dll", "cudnn_ops_infer64_8.dll", "cudnn_cnn_infer64_8.dll",
        "cudnn64_9.dll", "cudnn_ops64_9.dll", "cudnn_cnn64_9.dll",
    ]
    for dll_name in preload_order:
        if dll_name in found_dlls:
            try:
                ctypes.CDLL(found_dlls[dll_name])
            except Exception as e:
                _emit(f"[CUDA] {dll_name} preload 실패: {e}")

    _registered = True
    _diagnostics = diag
    return diag
