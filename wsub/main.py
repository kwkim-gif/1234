#!/usr/bin/env python3
"""W-Sub 진입점 — 환경 검사 후 GUI 실행."""
from __future__ import annotations

import sys


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
    _check_python_version()
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
