"""
런타임 훅 — EXE와 같은 디렉토리의 ffmpeg/ffprobe를 PATH 앞에 추가합니다.
onedir 배포 시 ffmpeg.exe를 W-Sub 폴더에 넣으면 자동으로 인식됩니다.
"""
import os
import sys

_exe_dir = os.path.dirname(sys.executable if getattr(sys, "frozen", False) else __file__)
os.environ["PATH"] = _exe_dir + os.pathsep + os.environ.get("PATH", "")
