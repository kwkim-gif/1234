from __future__ import annotations

import json
from dataclasses import asdict, fields
from pathlib import Path

from app.models.settings import AppSettings, WhisperSettings, AudioSettings


CONFIG_PATH = Path.home() / ".wsub" / "config.json"


def _settings_from_dict(d: dict) -> AppSettings:
    whisper_d = d.pop("whisper", {})
    audio_d = d.pop("audio", {})

    whisper_fields = {f.name for f in fields(WhisperSettings)}
    audio_fields = {f.name for f in fields(AudioSettings)}

    whisper = WhisperSettings(**{k: v for k, v in whisper_d.items() if k in whisper_fields})
    audio = AudioSettings(**{k: v for k, v in audio_d.items() if k in audio_fields})

    app_fields = {f.name for f in fields(AppSettings)} - {"whisper", "audio"}
    return AppSettings(
        **{k: v for k, v in d.items() if k in app_fields},
        whisper=whisper,
        audio=audio,
    )


def load_settings() -> AppSettings:
    """설정 파일에서 AppSettings를 로드합니다."""
    if not CONFIG_PATH.exists():
        return AppSettings()
    try:
        with CONFIG_PATH.open(encoding="utf-8") as f:
            data = json.load(f)
        return _settings_from_dict(data)
    except Exception:
        return AppSettings()


def save_settings(settings: AppSettings) -> None:
    """AppSettings를 JSON 파일로 저장합니다."""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CONFIG_PATH.open("w", encoding="utf-8") as f:
        json.dump(asdict(settings), f, indent=2, ensure_ascii=False)
