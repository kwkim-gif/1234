from __future__ import annotations

APP_NAME = "W-Sub"
APP_VERSION = "1.0.0"

VIDEO_EXTENSIONS: set[str] = {
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".asf",
    ".mpg", ".mpeg", ".flv", ".webm", ".ts", ".m2ts",
}

AUDIO_EXTENSIONS: set[str] = {
    ".mp3", ".wav", ".aac", ".flac", ".ogg",
    ".opus", ".m4a", ".wma",
}

SUPPORTED_EXTENSIONS: set[str] = VIDEO_EXTENSIONS | AUDIO_EXTENSIONS

SUPPORTED_MODELS: list[dict] = [
    {"id": "openai/whisper-tiny",             "name": "Whisper Tiny",         "size_gb": 0.15},
    {"id": "openai/whisper-base",             "name": "Whisper Base",         "size_gb": 0.29},
    {"id": "openai/whisper-small",            "name": "Whisper Small",        "size_gb": 0.97},
    {"id": "openai/whisper-medium",           "name": "Whisper Medium",       "size_gb": 3.06},
    {"id": "openai/whisper-large-v1",         "name": "Whisper Large v1",     "size_gb": 6.17},
    {"id": "openai/whisper-large-v2",         "name": "Whisper Large v2",     "size_gb": 6.17},
    {"id": "openai/whisper-large-v3",         "name": "Whisper Large v3",     "size_gb": 6.17},
    {"id": "openai/whisper-large-v3-turbo",   "name": "Whisper Large Turbo",  "size_gb": 3.09},
    # kotoba-whisper-v2.0-faster: CTranslate2 변환 버전 → faster-whisper 직접 사용 가능
    {"id": "kotoba-tech/kotoba-whisper-v2.0-faster", "name": "Kotoba Whisper v2 (Fast)", "size_gb": 6.17},
    {"id": "litagin/anime-whisper",                  "name": "Anime Whisper",             "size_gb": 6.17},
]

SUPPORTED_LANGUAGES: list[dict[str, str]] = [
    {"code": "auto", "name": "Auto Detect"},
    {"code": "ko",   "name": "Korean"},
    {"code": "en",   "name": "English"},
    {"code": "ja",   "name": "Japanese"},
    {"code": "zh",   "name": "Chinese (Simplified)"},
    {"code": "zh-TW","name": "Chinese (Traditional)"},
    {"code": "es",   "name": "Spanish"},
    {"code": "fr",   "name": "French"},
    {"code": "de",   "name": "German"},
    {"code": "it",   "name": "Italian"},
    {"code": "ru",   "name": "Russian"},
    {"code": "pt",   "name": "Portuguese"},
    {"code": "ar",   "name": "Arabic"},
    {"code": "hi",   "name": "Hindi"},
    {"code": "vi",   "name": "Vietnamese"},
    {"code": "th",   "name": "Thai"},
    {"code": "id",   "name": "Indonesian"},
    {"code": "nl",   "name": "Dutch"},
    {"code": "pl",   "name": "Polish"},
    {"code": "tr",   "name": "Turkish"},
]

SAMPLE_RATES: list[int] = [16000, 22050, 44100]

OUTPUT_FORMATS: list[str] = ["srt", "txt"]

DISK_SPACE_WARNING_GB: float = 10.0
