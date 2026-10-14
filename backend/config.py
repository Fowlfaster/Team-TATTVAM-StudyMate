import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _folder_path(variable_name: str, default: str) -> Path:
    path = Path(os.getenv(variable_name, default)).expanduser()
    if not path.is_absolute():
        path = BASE_DIR / path
    return path.resolve()


GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_CHAT_MODEL = os.getenv("GROQ_CHAT_MODEL", "openai/gpt-oss-20b")
GROQ_WHISPER_MODEL = os.getenv("GROQ_WHISPER_MODEL", "whisper-large-v3")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
JWT_SECRET = os.getenv("JWT_SECRET", "studymate-development-secret-change-before-deployment")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))

DATABASE_PATH = _folder_path("DATABASE_PATH", "studymate.db")
UPLOADS_DIR = _folder_path("UPLOADS_DIR", "uploads")
CHROMA_DIR = _folder_path("CHROMA_DIR", "chroma_data")
