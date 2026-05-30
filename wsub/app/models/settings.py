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
    # 할루시네이션(반복 문장) 억제 파라미터
    repetition_penalty: float = 1.0
    no_repeat_ngram_size: int = 0
    hallucination_silence_threshold: float = 0.0  # 0 = 비활성


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
    dedup_segments: bool = True   # 중복 자막 제거 여부
    hallucination_level: str = "medium"  # off / weak / medium / strong
    whisper: WhisperSettings = field(default_factory=WhisperSettings)
    audio: AudioSettings = field(default_factory=AudioSettings)
