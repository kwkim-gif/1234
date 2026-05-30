from __future__ import annotations

from pathlib import Path


def _format_timestamp_srt(seconds: float) -> str:
    """초를 SRT 타임스탬프 형식(HH:MM:SS,mmm)으로 변환합니다."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_srt(segments: list[dict], output_path: Path) -> None:
    """세그먼트 목록을 SRT 형식으로 파일에 저장합니다."""
    lines: list[str] = []
    for i, seg in enumerate(segments, 1):
        start = _format_timestamp_srt(seg["start"])
        end = _format_timestamp_srt(seg["end"])
        text = seg["text"].strip()
        lines.append(f"{i}\n{start} --> {end}\n{text}\n")
    output_path.write_text("\n".join(lines), encoding="utf-8")


def write_txt(segments: list[dict], output_path: Path) -> None:
    """세그먼트 목록을 일반 텍스트 형식으로 파일에 저장합니다."""
    text = "\n".join(seg["text"].strip() for seg in segments)
    output_path.write_text(text, encoding="utf-8")


def build_output_path(
    source_path: Path,
    output_dir: str,
    language: str,
    fmt: str,
) -> Path:
    """출력 파일 경로를 결정합니다. 원본 파일명 그대로 확장자만 변경합니다."""
    filename = f"{source_path.stem}.{fmt}"
    if output_dir:
        return Path(output_dir) / filename
    return source_path.parent / filename


def remove_duplicate_segments(segments: list[dict]) -> list[dict]:
    """연속 중복 자막(hallucination)을 제거합니다."""
    cleaned: list[dict] = []
    prev_text = ""
    for seg in segments:
        text = seg["text"].strip()
        if text and text != prev_text:
            cleaned.append(seg)
            prev_text = text
    return cleaned
