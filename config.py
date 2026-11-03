"""Application configuration.

All values can be overridden with environment variables (see .env.example).
No secrets are hard-coded: if SECRET_KEY is not provided a random key is
generated for the current process.
"""
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _env_int(name, default):
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


SUPPORTED_LANGUAGES = {
    "auto": "Automatic detection",
    "en": "English",
    "hi": "Hindi",
    "kn": "Kannada",
    "mr": "Marathi",
    "ta": "Tamil",
    "te": "Telugu",
    "ml": "Malayalam",
    "bn": "Bengali",
    "gu": "Gujarati",
    "ur": "Urdu",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "pt": "Portuguese",
    "ru": "Russian",
    "ar": "Arabic",
    "zh": "Chinese",
    "ja": "Japanese",
}


class Config:
    """Flask configuration object."""

    BASE_DIR = BASE_DIR
    SECRET_KEY = os.getenv("SECRET_KEY") or secrets.token_hex(32)
    HOST = os.getenv("HOST", "127.0.0.1")
    PORT = _env_int("PORT", 5000)
    DEBUG = _env_bool("FLASK_DEBUG", False)
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

    # Uploads and exports
    MAX_UPLOAD_MB = _env_int("MAX_UPLOAD_MB", 100)
    MAX_CONTENT_LENGTH = MAX_UPLOAD_MB * 1024 * 1024
    UPLOAD_FOLDER = str(BASE_DIR / "uploads")
    EXPORT_FOLDER = str(BASE_DIR / "exports")
    EXPORT_RETENTION_HOURS = _env_int("EXPORT_RETENTION_HOURS", 24)
    ALLOWED_AUDIO_EXTENSIONS = frozenset({"wav", "mp3", "m4a", "flac", "ogg", "webm"})

    # Speech recognition (OpenAI Whisper, open-source)
    ALLOWED_WHISPER_MODELS = ("base", "small")
    DEFAULT_WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
    DEVICE = os.getenv("DEVICE", "auto").lower()  # auto | cpu | cuda
    AUDIO_CHUNK_SECONDS = _env_int("AUDIO_CHUNK_SECONDS", 300)

    # Summarization (Hugging Face Transformers)
    SUMMARIZER_MODEL = os.getenv("SUMMARIZER_MODEL", "sshleifer/distilbart-cnn-12-6")
    TEXT_CHUNK_WORDS = _env_int("TEXT_CHUNK_WORDS", 350)
    SUMMARY_MIN_WORDS = _env_int("SUMMARY_MIN_WORDS", 40)
    MIN_TRANSCRIPT_WORDS = _env_int("MIN_TRANSCRIPT_WORDS", 5)
    DEFAULT_SUMMARY_LENGTH = "medium"
    SUMMARY_LENGTHS = ("short", "medium", "detailed")

    SUPPORTED_LANGUAGES = SUPPORTED_LANGUAGES
