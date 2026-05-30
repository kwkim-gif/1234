"""PyInstaller hook — faster_whisper 패키지 데이터 포함."""
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

datas = collect_data_files("faster_whisper")
binaries = collect_dynamic_libs("faster_whisper")

# tokenizer assets
try:
    import faster_whisper
    fw_dir = Path(faster_whisper.__file__).parent
    for f in fw_dir.glob("**/*.tiktoken"):
        datas.append((str(f), "faster_whisper"))
    for f in fw_dir.glob("**/*.json"):
        datas.append((str(f), "faster_whisper"))
except Exception:
    pass
