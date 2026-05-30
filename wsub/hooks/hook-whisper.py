"""PyInstaller hook — openai-whisper 에셋(multilingual.tiktoken 등) 포함."""
from PyInstaller.utils.hooks import collect_data_files

datas = collect_data_files("whisper")
