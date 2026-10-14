import os
from pathlib import Path
import sys

from dotenv import dotenv_values, load_dotenv


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
FRONTEND_ORIGINS = [
    origin.strip()
    for origin in os.getenv("FRONTEND_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "studymate_v2")

DATABASE_PATH = _folder_path("DATABASE_PATH", "studymate.db")
UPLOADS_DIR = _folder_path("UPLOADS_DIR", "uploads")
CHROMA_DIR = _folder_path("CHROMA_DIR", "chroma_data")
MODEL_CACHE_DIR = _folder_path("MODEL_CACHE_DIR", "model_cache")


def get_groq_api_key() -> str:
    key = os.getenv("GROQ_API_KEY", "").strip()
    if key:
        return key
    return str(dotenv_values(BASE_DIR / ".env").get("GROQ_API_KEY") or "").strip()

DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
CHROMA_DIR.mkdir(parents=True, exist_ok=True)
MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)

if not GROQ_API_KEY:
    print("WARNING: GROQ_API_KEY is not configured; AI features will be unavailable.", file=sys.stderr)
if JWT_SECRET == "studymate-development-secret-change-before-deployment":
    print("WARNING: JWT_SECRET is using the development default; set a secure secret before deployment.", file=sys.stderr)
