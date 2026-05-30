"""PyInstaller hook — ctranslate2 네이티브 라이브러리 포함."""
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

datas = collect_data_files("ctranslate2")
binaries = collect_dynamic_libs("ctranslate2")

hiddenimports = [
    "ctranslate2",
    "ctranslate2.converters",
    "ctranslate2.specs",
]
