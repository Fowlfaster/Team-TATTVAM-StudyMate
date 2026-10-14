from pathlib import Path

from yt_dlp import YoutubeDL


def download_youtube_audio(url: str, output_path: str | Path) -> Path:
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    output_template = destination.with_suffix("")
    options = {
        "format": "bestaudio/best",
        "outtmpl": str(output_template),
        "quiet": True,
        "no_warnings": True,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "64",
        }],
    }

    with YoutubeDL(options) as downloader:
        downloader.download([url])

    if not destination.exists():
        raise FileNotFoundError(f"YouTube audio was not created at {destination}")
    return destination