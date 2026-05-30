# -*- mode: python ; coding: utf-8 -*-
"""
W-Sub PyInstaller 빌드 스펙 (onefile 모드 — 단일 EXE)

주의사항:
  - 파일 크기: 2~5 GB (torch 포함 시)
  - 첫 실행 시 temp 폴더 압축 해제로 30~60초 소요
  - 매 실행마다 압축 해제 반복 (runtime_tmpdir 설정 시 캐시 가능)

권장: 배포용은 build.spec (onedir) 사용
"""
import shutil
from pathlib import Path

binaries: list[tuple[str, str]] = []
for binary_name in ("ffmpeg", "ffprobe"):
    found = shutil.which(binary_name)
    if found:
        binaries.append((found, "."))

ct2_datas: list[tuple[str, str]] = []
try:
    import ctranslate2
    ct2_dir = Path(ctranslate2.__file__).parent
    for pattern in ("*.dll", "*.so", "*.pyd"):
        for f in ct2_dir.glob(pattern):
            ct2_datas.append((str(f), "ctranslate2"))
except ImportError:
    pass

# CUDA 12 런타임 DLL (cublas / cudnn) — GPU 가속 필수
# nvidia는 네임스페이스 패키지라 __file__이 None일 수 있으므로 __path__ 사용.
try:
    import nvidia
    for _nv_root in [Path(p) for p in getattr(nvidia, "__path__", [])]:
        for _nv_sub in ("cublas/bin", "cudnn/bin", "cuda_runtime/bin"):
            _nv_dir = _nv_root / _nv_sub
            if _nv_dir.exists():
                for _dll in _nv_dir.glob("*.dll"):
                    binaries.append((str(_dll), "."))
except Exception:
    pass

qt_datas: list[tuple[str, str]] = []
try:
    from PySide6 import __file__ as pyside6_init
    pyside6_dir = Path(pyside6_init).parent
    for plugin_dir in ("plugins/platforms", "plugins/styles"):
        full = pyside6_dir / plugin_dir
        if full.exists():
            qt_datas.append((str(full), plugin_dir))
except ImportError:
    pass

hidden_imports = [
    "PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets",
    "faster_whisper", "ctranslate2",
    "whisper", "whisper.tokenizer",
    "transformers", "transformers.pipelines",
    "torch", "torchaudio",
    "huggingface_hub", "numpy", "psutil", "requests",
    "app", "app.core", "app.engines", "app.models",
    "app.viewmodels", "app.views", "app.config",
]

icon_path = str(Path("resources/icons/wsub.ico")) if Path("resources/icons/wsub.ico").exists() else None

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=binaries,
    datas=ct2_datas + qt_datas,
    hiddenimports=hidden_imports,
    hookspath=["hooks"],
    excludes=["tkinter", "matplotlib", "scipy"],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="W-Sub",
    debug=False,
    strip=False,
    upx=False,
    console=False,
    # 고정 temp 디렉토리로 재실행 시 압축 해제 생략
    runtime_tmpdir=r"%LOCALAPPDATA%\W-Sub\runtime",
    icon=icon_path,
)
