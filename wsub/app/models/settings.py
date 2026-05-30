from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class WhisperSettings:
    temperature: float = 0.0
    beam_size: int = 5
    best_of: int = 5
    no_speech_threshold: float = 0.6
    compression_ratio_threshold: float = 2.4
    condition_on_previous_text: bool = True
    word_timestamps: bool = False
    vad_filter: bool = True


@dataclass
class AudioSettings:
    noise_reduction: bool = False
    silence_trimming: bool = False
    normalize_volume: bool = True
    voice_enhancement: bool = False
    sample_rate: int = 16000


@dataclass
class AppSettings:
    engine: str = "faster-whisper"
    model_name: str = "openai/whisper-large-v3"
    language: str = "auto"
    device: str = "auto"
    output_format: str = "srt"
    output_dir: str = ""
    whisper: WhisperSettings = field(default_factory=WhisperSettings)
    audio: AudioSettings = field(default_factory=AudioSettings)
