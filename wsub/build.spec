# -*- mode: python ; coding: utf-8 -*-
"""
W-Sub PyInstaller 빌드 스펙 (onedir 모드 — 권장)

빌드 결과: dist/W-Sub/ 폴더 + 내부 W-Sub.exe
onefile 대비 장점:
  - 시작 속도 10~30배 빠름 (temp 압축해제 없음)
  - Windows Defender 오탐 최소화
  - 업데이트 시 변경된 파일만 교체 가능
"""
import shutil
import sys
from pathlib import Path

# ── FFmpeg 바이너리 자동 탐색 ──────────────────────────────────────
binaries: list[tuple[str, str]] = []
for binary_name in ("ffmpeg", "ffprobe"):
    found = shutil.which(binary_name)
    if found:
        binaries.append((found, "."))
    # Windows 일반 설치 경로 추가 탐색
    for candidate in (
        rf"C:\ffmpeg\bin\{binary_name}.exe",
        rf"C:\Program Files\ffmpeg\bin\{binary_name}.exe",
        rf"C:\tools\ffmpeg\bin\{binary_name}.exe",
    ):
        if Path(candidate).exists() and not found:
            binaries.append((candidate, "."))
            break

# ── ctranslate2 / faster-whisper 공유 라이브러리 ───────────────────
# ctranslate2 는 .dll/.so 를 직접 포함해야 합니다
ct2_datas: list[tuple[str, str]] = []
try:
    import ctranslate2
    ct2_dir = Path(ctranslate2.__file__).parent
    for pattern in ("*.dll", "*.so", "*.pyd", "assets/*"):
        for f in ct2_dir.glob(pattern):
            ct2_datas.append((str(f), "ctranslate2"))
except ImportError:
    pass

# ── CUDA 12 런타임 DLL (cublas / cudnn) — GPU 가속 필수 ────────────
# ctranslate2 wheel은 cublas64_12.dll / cudnn DLL을 포함하지 않으므로
# nvidia pip 휠에서 직접 수집하여 _internal 루트에 둔다.
# (런타임에 cuda_setup이 이 위치를 찾아 preload)
# nvidia는 네임스페이스 패키지라 __file__이 None일 수 있으므로 __path__ 사용.
try:
    import nvidia
    _nv_roots = [Path(p) for p in getattr(nvidia, "__path__", [])]
    for _nv_root in _nv_roots:
        for _nv_sub in ("cublas/bin", "cudnn/bin", "cuda_runtime/bin"):
            _nv_dir = _nv_root / _nv_sub
            if _nv_dir.exists():
                for _dll in _nv_dir.glob("*.dll"):
                    binaries.append((str(_dll), "."))
except Exception:
    pass

# ── faster_whisper 에셋 (tokenizer vocab 등) ──────────────────────
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

# ── PySide6 Qt 플러그인 (플랫폼 플러그인 필수) ─────────────────────
qt_datas: list[tuple[str, str]] = []
try:
    from PySide6 import __file__ as pyside6_init
    pyside6_dir = Path(pyside6_init).parent
    for plugin_dir in ("plugins/platforms", "plugins/styles", "plugins/imageformats"):
        full = pyside6_dir / plugin_dir
        if full.exists():
            qt_datas.append((str(full), plugin_dir))
except ImportError:
    pass

all_datas = ct2_datas + fw_datas + qt_datas

# ── hidden imports ─────────────────────────────────────────────────
hidden_imports = [
    # PySide6
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtNetwork",
    "PySide6.QtSvg",
    # faster-whisper / ctranslate2
    "faster_whisper",
    "faster_whisper.audio",
    "faster_whisper.feature_extractor",
    "faster_whisper.tokenizer",
    "faster_whisper.transcribe",
    "faster_whisper.utils",
    "faster_whisper.vad",
    "ctranslate2",
    # openai-whisper
    "whisper",
    "whisper.audio",
    "whisper.decoding",
    "whisper.model",
    "whisper.tokenizer",
    "whisper.transcribe",
    "whisper.utils",
    # transformers
    "transformers",
    "transformers.pipelines",
    "transformers.pipelines.automatic_speech_recognition",
    "transformers.models.whisper",
    "transformers.models.whisper.modeling_whisper",
    "transformers.models.whisper.tokenization_whisper",
    "transformers.models.whisper.feature_extraction_whisper",
    # torch
    "torch",
    "torch.nn",
    "torch.nn.functional",
    "torchaudio",
    "torchaudio.functional",
    # huggingface_hub
    "huggingface_hub",
    "huggingface_hub.utils",
    # numpy / psutil / requests
    "numpy",
    "numpy.core._multiarray_umath",
    "psutil",
    "requests",
    "urllib3",
    # app
    "app",
    "app.core",
    "app.core.transcription_service",
    "app.core.model_manager",
    "app.core.ffmpeg_handler",
    "app.core.subtitle_writer",
    "app.core.system_checker",
    "app.engines",
    "app.engines.base_engine",
    "app.engines.faster_whisper_engine",
    "app.engines.openai_whisper_engine",
    "app.engines.hf_whisper_engine",
    "app.models",
    "app.models.job",
    "app.models.model_info",
    "app.models.settings",
    "app.viewmodels",
    "app.viewmodels.main_viewmodel",
    "app.viewmodels.queue_viewmodel",
    "app.viewmodels.model_manager_viewmodel",
    "app.views",
    "app.views.main_window",
    "app.views.widgets.drop_area",
    "app.views.widgets.file_table",
    "app.views.widgets.log_panel",
    "app.views.widgets.progress_bar",
    "app.views.dialogs.settings_dialog",
    "app.views.dialogs.model_dialog",
    "app.config",
    "app.config.constants",
    "app.config.config_manager",
]

# ── 아이콘 경로 ────────────────────────────────────────────────────
icon_path = str(Path("resources/icons/wsub.ico")) if Path("resources/icons/wsub.ico").exists() else None

# ── Analysis ───────────────────────────────────────────────────────
a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=binaries,
    datas=all_datas,
    hiddenimports=hidden_imports,
    hookspath=["hooks"],
    hooksconfig={},
    runtime_hooks=["hooks/rthook_ffmpeg.py"] if Path("hooks/rthook_ffmpeg.py").exists() else [],
    excludes=["tkinter", "_tkinter", "matplotlib", "scipy", "IPython", "jupyter"],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],                         # onedir: 바이너리는 COLLECT로 분리
    exclude_binaries=True,
    name="W-Sub",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,              # GUI 앱 — 콘솔 숨김
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="W-Sub",
)
