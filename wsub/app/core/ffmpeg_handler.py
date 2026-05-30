from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from app.models.settings import AudioSettings


class FFmpegHandler:
    """FFmpeg를 사용하여 미디어 파일을 오디오로 변환하고 전처리합니다."""

    def extract_audio(
        self,
        input_path: Path,
        audio_settings: AudioSettings,
    ) -> Path:
        """미디어 파일에서 오디오를 추출하고 전처리하여 임시 WAV 파일 경로를 반환합니다."""
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.close()
        output_path = Path(tmp.name)

        filters = self._build_filters(audio_settings)
        cmd = self._build_command(input_path, output_path, audio_settings.sample_rate, filters)

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg 오류:\n{result.stderr[-500:]}")

        return output_path

    def get_duration(self, file_path: Path) -> float:
        """미디어 파일의 재생 시간(초)을 반환합니다."""
        cmd = [
            "ffprobe", "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(file_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        try:
            return float(result.stdout.strip())
        except ValueError:
            return 0.0

    @staticmethod
    def is_available() -> bool:
        """FFmpeg가 설치되어 있는지 확인합니다."""
        import shutil
        return shutil.which("ffmpeg") is not None

    def _build_filters(self, settings: AudioSettings) -> list[str]:
        filters: list[str] = []
        if settings.normalize_volume:
            filters.append("loudnorm")
        if settings.noise_reduction:
            # 기본 고주파/저주파 필터로 노이즈 감소 근사
            filters.append("highpass=f=80,lowpass=f=8000")
        if settings.silence_trimming:
            filters.append("silenceremove=start_periods=1:start_silence=0.5:start_threshold=-50dB")
        if settings.voice_enhancement:
            filters.append("equalizer=f=1000:t=h:width=200:g=3")
        return filters

    def _build_command(
        self,
        input_path: Path,
        output_path: Path,
        sample_rate: int,
        filters: list[str],
    ) -> list[str]:
        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-ar", str(sample_rate),
            "-ac", "1",
            "-vn",
        ]
        if filters:
            cmd += ["-af", ",".join(filters)]
        cmd.append(str(output_path))
        return cmd
