# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 빌드 스펙 — W-Sub 단일 EXE 생성

import sys
from pathlib import Path
import shutil

block_cipher = None

# FFmpeg 바이너리 자동 포함 (PATH에서 찾음)
ffmpeg_path = shutil.which("ffmpeg")
ffprobe_path = shutil.which("ffprobe")

binaries = []
if ffmpeg_path:
    binaries.append((ffmpeg_path, "."))
if ffprobe_path:
    binaries.append((ffprobe_path, "."))

hidden_imports = [
    # PySide6
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    # faster-whisper
    "faster_whisper",
    "ctranslate2",
    # openai-whisper
    "whisper",
    "whisper.tokenizer",
    # transformers
    "transformers",
    "transformers.pipelines",
    "transformers.models.whisper",
    # torch
    "torch",
    "torchaudio",
    # huggingface_hub
    "huggingface_hub",
    # numpy / psutil
    "numpy",
    "psutil",
    # app modules
    "app",
    "app.core",
    "app.engines",
    "app.models",
    "app.viewmodels",
    "app.views",
    "app.config",
]

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=binaries,
    datas=[],
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "scipy"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="W-Sub",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,           # Windows Defender 오탐 방지를 위해 UPX 비활성화
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,       # GUI 앱 — 콘솔 숨김
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,           # resources/icons/wsub.ico 준비 시 경로 지정
)
