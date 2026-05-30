"""CUDA runtime DLL registration for Windows.

The hard problem: CTranslate2 loads cublas64_12.dll lazily at inference time
via LoadLibrary, and it (plus its deps cublasLt64_12.dll / cudart64_12.dll)
must be resolvable at that moment. Predicting nvidia-wheel paths is fragile.

Robust strategy:
1. `import torch` first. The CUDA build of torch (cu121) bundles cublas /
   cudnn in torch/lib and calls os.add_dll_directory(torch/lib) on import,
   making those DLLs resolvable process-wide. This alone usually fixes it.
2. Also glob-search the Python env + CUDA_PATH for the DLLs, register each
   directory, and ctypes-preload them in dependency order so the modules are
   already resident when CTranslate2 asks for them.

Must run before any ctranslate2 / faster_whisper inference.
"""
from __future__ import annotations

import ctypes
import glob
import os
import sys

_registered = False
_diagnostics: list[str] = []


def register_cuda_dll_dirs(log=None) -> list[str]:
    """Register CUDA DLL dirs and pre-load DLLs. Returns diagnostic lines."""
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

    # ── 1. import torch first (registers torch/lib, loads CUDA DLLs) ───
    torch_lib = None
    try:
        import torch  # noqa: F401
        torch_lib = os.path.join(os.path.dirname(torch.__file__), "lib")
        cuda_ok = torch.cuda.is_available()
        _emit(f"[CUDA] torch {torch.__version__} import됨 (cuda={cuda_ok})")
        if torch_lib and os.path.isdir(torch_lib):
            try:
                os.add_dll_directory(torch_lib)  # type: ignore[attr-defined]
            except Exception:
                pass
            os.environ["PATH"] = torch_lib + os.pathsep + os.environ.get("PATH", "")
    except Exception as e:
        _emit(f"[CUDA] torch import 실패: {e}")

    # ── 2. Collect search roots ───────────────────────────────────────
    roots: list[str] = []
    if torch_lib and os.path.isdir(torch_lib):
        roots.append(torch_lib)
    for r in [sys.prefix, os.path.dirname(sys.executable)]:
        if r and os.path.isdir(r):
            roots.append(r)
    cuda_path = os.environ.get("CUDA_PATH", "")
    if cuda_path and os.path.isdir(cuda_path):
        roots.append(cuda_path)
    for p in [r"C:\Program Files\NVIDIA GPU Computing Toolkit",
              r"C:\Windows\System32"]:
        if os.path.isdir(p):
            roots.append(p)

    # ── 3. Find DLL files ─────────────────────────────────────────────
    target_dlls = [
        "cudart64_12.dll",
        "cublas64_12.dll",
        "cublasLt64_12.dll",
        "cudnn64_8.dll", "cudnn_ops_infer64_8.dll", "cudnn_cnn_infer64_8.dll",
        "cudnn64_9.dll", "cudnn_ops64_9.dll", "cudnn_cnn64_9.dll",
    ]
    found_dlls: dict[str, str] = {}
    for root in roots:
        for dll_name in target_dlls:
            if dll_name in found_dlls:
                continue
            matches = glob.glob(os.path.join(root, "**", dll_name), recursive=True)
            if matches:
                found_dlls[dll_name] = matches[0]

    # ── 4. Register found directories ─────────────────────────────────
    added: set[str] = set()
    for path in found_dlls.values():
        d = os.path.dirname(path)
        if d in added:
            continue
        try:
            os.add_dll_directory(d)  # type: ignore[attr-defined]
        except Exception:
            pass
        os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
        added.add(d)

    # ── 5. ctypes pre-load in dependency order ────────────────────────
    if "cublas64_12.dll" in found_dlls:
        _emit(f"[CUDA] cublas 발견: {found_dlls['cublas64_12.dll']}")
    else:
        _emit("[CUDA] ⚠️ cublas64_12.dll 을 찾지 못했습니다. "
              "torch(cu121) 또는 nvidia-cublas-cu12 설치를 확인하세요.")

    for dll_name in ["cudart64_12.dll", "cublasLt64_12.dll", "cublas64_12.dll",
                     "cudnn64_8.dll", "cudnn_ops_infer64_8.dll",
                     "cudnn_cnn_infer64_8.dll", "cudnn64_9.dll",
                     "cudnn_ops64_9.dll", "cudnn_cnn64_9.dll"]:
        if dll_name in found_dlls:
            try:
                ctypes.CDLL(found_dlls[dll_name])
            except Exception as e:
                _emit(f"[CUDA] {dll_name} preload 실패: {e}")

    _registered = True
    _diagnostics = diag
    return diag
