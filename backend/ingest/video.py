import subprocess
import tempfile
from pathlib import Path
from typing import Any

from groq import Groq

from config import GROQ_API_KEY, GROQ_WHISPER_MODEL


CHUNK_SECONDS = 10 * 60
MAX_GROQ_UPLOAD_BYTES = 25 * 1024 * 1024


def _run(command: list[str]) -> str:
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def transcribe_video(file_path: str | Path) -> list[dict[str, str | float]]:
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not configured")

    source_path = Path(file_path)
    client = Groq(api_key=GROQ_API_KEY)
    transcripts: list[dict[str, str | float]] = []

    with tempfile.TemporaryDirectory(prefix="studymate-audio-") as temp_directory:
        temp_path = Path(temp_directory)
        audio_path = temp_path / "audio.mp3"
        _run([
            "ffmpeg", "-y", "-i", str(source_path), "-vn", "-ac", "1", "-ar", "16000",
            "-b:a", "64k", str(audio_path),
        ])
        duration = float(_run([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path),
        ]))

        chunk_start = 0.0
        chunk_number = 0
        while chunk_start < duration:
            chunk_duration = min(CHUNK_SECONDS, duration - chunk_start)
            chunk_path = temp_path / f"chunk_{chunk_number:04d}.mp3"
            _run([
                "ffmpeg", "-y", "-ss", f"{chunk_start:.3f}", "-i", str(audio_path),
                "-t", f"{chunk_duration:.3f}", "-vn", "-c:a", "copy", str(chunk_path),
            ])
            if chunk_path.stat().st_size >= MAX_GROQ_UPLOAD_BYTES:
                raise RuntimeError("Audio chunk exceeds Groq's upload size limit")

            with chunk_path.open("rb") as audio_file:
                result = client.audio.transcriptions.create(
                    file=(chunk_path.name, audio_file.read()),
                    model=GROQ_WHISPER_MODEL,
                    response_format="verbose_json",
                )

            segments = _field(result, "segments", []) or []
            for segment in segments:
                text = str(_field(segment, "text", "")).strip()
                if not text:
                    continue
                transcripts.append({
                    "text": text,
                    "start": chunk_start + float(_field(segment, "start", 0.0)),
                    "end": chunk_start + float(_field(segment, "end", chunk_duration)),
                })

            if not segments:
                text = str(_field(result, "text", "")).strip()
                if text:
                    transcripts.append({
                        "text": text,
                        "start": chunk_start,
                        "end": chunk_start + chunk_duration,
                    })

            chunk_start += chunk_duration
            chunk_number += 1

    return transcripts