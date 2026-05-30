#!/usr/bin/env python3
"""W-Sub 진입점 — 환경 검사 후 GUI 실행."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def _setup_frozen_paths() -> None:
    """PyInstaller onedir EXE 실행 시 경로를 올바르게 설정합니다."""
    if not getattr(sys, "frozen", False):
        return

    # EXE 디렉토리를 PATH 앞에 추가 (번들된 ffmpeg 인식)
    exe_dir = Path(sys.executable).parent
    os.environ["PATH"] = str(exe_dir) + os.pathsep + os.environ.get("PATH", "")

    # PySide6 Qt 플러그인 경로 설정
    qt_plugins = exe_dir / "plugins"
    if qt_plugins.exists():
        os.environ["QT_PLUGIN_PATH"] = str(qt_plugins)

    # HuggingFace 캐시를 사용자 홈 디렉토리로 유지
    if "HF_HOME" not in os.environ:
        os.environ["HF_HOME"] = str(Path.home() / ".cache" / "huggingface")


def _check_python_version() -> None:
    if sys.version_info < (3, 11):
        print(f"[오류] Python 3.11 이상이 필요합니다. 현재: {sys.version}")
        sys.exit(1)


def _run_startup_checks() -> None:
    """시작 시 환경 검사 항목을 순서대로 실행하고 결과를 출력합니다."""
    from app.core.system_checker import check_system
    from app.config.constants import DISK_SPACE_WARNING_GB

    print("=" * 50)
    print(" W-Sub 환경 검사")
    print("=" * 50)

    info = check_system()

    _print_check("Python 버전 (3.11+)", info.python_ok, f"{info.python_version}")
    _print_check("FFmpeg 설치",         info.ffmpeg_available, info.ffmpeg_version or "미설치")
    _print_check("CUDA 가용",           info.cuda_available, info.cuda_version or "미감지")
    _print_check("GPU 정보",            bool(info.gpu_name and info.gpu_name != "N/A"),
                 f"{info.gpu_name}  VRAM {info.gpu_vram_gb}GB")
    _print_check("HuggingFace 캐시",    True, info.hf_cache_dir)
    _print_check(f"디스크 여유 공간 ({DISK_SPACE_WARNING_GB}GB 권장)",
                 info.disk_free_gb >= DISK_SPACE_WARNING_GB,
                 f"{info.disk_free_gb:.1f} GB")
    _print_check("인터넷 연결",          info.internet_available, "")

    print("=" * 50)


def _print_check(label: str, ok: bool, detail: str) -> None:
    mark = "✅" if ok else "⚠️ "
    detail_str = f"  ({detail})" if detail else ""
    print(f"  {mark}  {label}{detail_str}")


def main() -> None:
    _setup_frozen_paths()
    _check_python_version()

    # ctranslate2/faster_whisper가 import되기 전에 CUDA DLL 경로 등록 (GPU 가속용)
    try:
        from app.core.cuda_setup import register_cuda_dll_dirs
        added = register_cuda_dll_dirs()
        if added:
            print(f"[CUDA] DLL 경로 등록: {len(added)}개")
            for d in added:
                print(f"        {d}")
    except Exception as e:
        print(f"[CUDA] DLL 경로 등록 실패: {e}")

    _run_startup_checks()

    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt

    app = QApplication(sys.argv)
    app.setApplicationName("W-Sub")
    app.setApplicationVersion("1.0.0")

    # 다크 팔레트 기본 적용
    app.setStyle("Fusion")
    _apply_dark_palette(app)

    from app.viewmodels.main_viewmodel import MainViewModel
    from app.views.main_window import MainWindow

    vm = MainViewModel()
    window = MainWindow(vm)
    window.show()

    sys.exit(app.exec())


def _apply_dark_palette(app) -> None:
    from PySide6.QtGui import QColor, QPalette

    palette = QPalette()
    dark = QColor(30, 30, 30)
    mid_dark = QColor(45, 45, 45)
    text = QColor(220, 220, 220)
    highlight = QColor(74, 158, 255)

    palette.setColor(QPalette.Window,          dark)
    palette.setColor(QPalette.WindowText,      text)
    palette.setColor(QPalette.Base,            QColor(18, 18, 18))
    palette.setColor(QPalette.AlternateBase,   mid_dark)
    palette.setColor(QPalette.ToolTipBase,     dark)
    palette.setColor(QPalette.ToolTipText,     text)
    palette.setColor(QPalette.Text,            text)
    palette.setColor(QPalette.Button,          mid_dark)
    palette.setColor(QPalette.ButtonText,      text)
    palette.setColor(QPalette.BrightText,      QColor(255, 80, 80))
    palette.setColor(QPalette.Highlight,       highlight)
    palette.setColor(QPalette.HighlightedText, QColor(0, 0, 0))

    app.setPalette(palette)


if __name__ == "__main__":
    main()
