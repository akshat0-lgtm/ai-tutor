"""Central configuration. Reads GROQ_API_KEY (and optional overrides) from
backend/.env via python-dotenv."""
import os
from pathlib import Path

from dotenv import load_dotenv

# Load backend/.env (one level up from this file's app/ package).
BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "").strip()

# Models (overridable via env, but good free-tier defaults baked in).
GROQ_LLM_MODEL = os.getenv("GROQ_LLM_MODEL", "llama-3.3-70b-versatile").strip()
GROQ_WHISPER_MODEL = os.getenv("GROQ_WHISPER_MODEL", "whisper-large-v3-turbo").strip()
EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
).strip()

# Sarvam voice (conversation mode in Teach mode — optional feature).
SARVAM_TTS_MODEL = os.getenv("SARVAM_TTS_MODEL", "bulbul:v3").strip()
SARVAM_TTS_SPEAKER = os.getenv("SARVAM_TTS_SPEAKER", "shubh").strip()
SARVAM_TTS_LANGUAGE = os.getenv("SARVAM_TTS_LANGUAGE", "en-IN").strip()
SARVAM_STT_MODEL = os.getenv("SARVAM_STT_MODEL", "saaras:v3").strip()
SARVAM_STT_LANGUAGE = os.getenv("SARVAM_STT_LANGUAGE", "en-IN").strip()

# Below this top cosine-similarity score, a query is treated as out-of-context.
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.25"))

# CORS: allow the local Next.js dev server by default; override in prod.
_default_origins = "http://localhost:3000,http://127.0.0.1:3000"
CORS_ORIGINS = [
    o.strip() for o in os.getenv("CORS_ORIGINS", _default_origins).split(",") if o.strip()
]


def require_groq_key() -> str:
    if not GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Create backend/.env from .env.example "
            "and add your free key from https://console.groq.com/keys"
        )
    return GROQ_API_KEY


def require_sarvam_key() -> str:
    if not SARVAM_API_KEY:
        raise RuntimeError(
            "SARVAM_API_KEY is not set. Add it to backend/.env to use voice "
            "features — get a key at https://dashboard.sarvam.ai"
        )
    return SARVAM_API_KEY
