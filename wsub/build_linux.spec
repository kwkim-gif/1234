# -*- mode: python ; coding: utf-8 -*-
"""W-Sub PyInstaller 빌드 스펙 — Linux onedir."""
import shutil
from pathlib import Path

binaries: list[tuple[str, str]] = []
for name in ("ffmpeg", "ffprobe"):
    found = shutil.which(name)
    if found:
        binaries.append((found, "."))

# ctranslate2 공유 라이브러리
ct2_datas: list[tuple[str, str]] = []
try:
    import ctranslate2
    ct2_dir = Path(ctranslate2.__file__).parent
    for f in ct2_dir.glob("*.so*"):
        ct2_datas.append((str(f), "ctranslate2"))
    for f in ct2_dir.glob("**/*.py"):
        rel = f.relative_to(ct2_dir.parent)
        ct2_datas.append((str(f), str(rel.parent)))
except ImportError:
    pass

# faster_whisper 에셋
fw_datas: list[tuple[str, str]] = []
try:
    import faster_whisper
    fw_dir = Path(faster_whisper.__file__).parent
    for f in fw_dir.glob("**/*"):
        if f.is_file() and f.suffix in (".json", ".txt", ".tiktoken"):
            rel = f.relative_to(fw_dir.parent)
            fw_datas.append((str(f), str(rel.parent)))
except ImportError:
    pass

# PySide6 Qt 플러그인
qt_datas: list[tuple[str, str]] = []
try:
    from PySide6 import __file__ as pyside6_init
    pyside6_dir = Path(pyside6_init).parent
    for plugin_dir in ("Qt/plugins/platforms", "Qt/plugins/xcbglintegrations",
                       "Qt/plugins/styles", "Qt/plugins/imageformats",
                       "Qt/lib"):
        full = pyside6_dir / plugin_dir
        if full.exists():
            qt_datas.append((str(full), f"PySide6/{plugin_dir}"))
except ImportError:
    pass

all_datas = ct2_datas + fw_datas + qt_datas

hidden_imports = [
    "PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets",
    "PySide6.QtNetwork", "PySide6.QtSvg",
    "faster_whisper", "faster_whisper.audio", "faster_whisper.feature_extractor",
    "faster_whisper.tokenizer", "faster_whisper.transcribe",
    "faster_whisper.utils", "faster_whisper.vad",
    "ctranslate2",
    "huggingface_hub", "huggingface_hub.utils",
    "numpy", "numpy.core._multiarray_umath",
    "psutil", "requests", "urllib3",
    "app", "app.core", "app.engines", "app.models",
    "app.viewmodels", "app.views", "app.config",
    "app.core.transcription_service", "app.core.model_manager",
    "app.core.ffmpeg_handler", "app.core.subtitle_writer",
    "app.core.system_checker",
    "app.engines.base_engine", "app.engines.faster_whisper_engine",
    "app.engines.openai_whisper_engine", "app.engines.hf_whisper_engine",
    "app.models.job", "app.models.model_info", "app.models.settings",
    "app.viewmodels.main_viewmodel", "app.viewmodels.queue_viewmodel",
    "app.viewmodels.model_manager_viewmodel",
    "app.views.main_window",
    "app.views.widgets.drop_area", "app.views.widgets.file_table",
    "app.views.widgets.log_panel", "app.views.widgets.progress_bar",
    "app.views.dialogs.settings_dialog", "app.views.dialogs.model_dialog",
    "app.config.constants", "app.config.config_manager",
]

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=binaries,
    datas=all_datas,
    hiddenimports=hidden_imports,
    hookspath=["hooks"],
    runtime_hooks=["hooks/rthook_ffmpeg.py"],
    excludes=["tkinter", "_tkinter", "matplotlib", "scipy",
              "IPython", "jupyter", "openai", "transformers", "torch", "torchaudio"],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="wsub",
    debug=False,
    strip=True,
    upx=False,
    console=True,   # Linux: 터미널에서 실행, 로그 확인 용이
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=True,
    upx=False,
    name="wsub",
)
