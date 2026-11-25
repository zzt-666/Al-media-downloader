import os
from pathlib import Path

from dotenv import load_dotenv

# backend/app/config.py -> parents[1]=backend, parents[2]=repo root
BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[2]

# Load backend/.env (do not override already-set process env vars)
load_dotenv(BACKEND_DIR / ".env", override=False)

DOWNLOAD_DIR = REPO_ROOT / "downloads"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
SUBS_DIR = DOWNLOAD_DIR / "subs"
SUBS_DIR.mkdir(parents=True, exist_ok=True)

MAX_CONCURRENT_DOWNLOADS = 1
FILE_TTL_SECONDS = 60 * 60  # 1 hour
DOWNLOAD_TIMEOUT_SECONDS = 600  # 10 minutes

ALLOWED_URL_SCHEMES = frozenset({"http", "https"})

CORS_ORIGINS = [
    "http://127.0.0.1:5173",
    "http://localhost:5173",
]

# Prefer H.264 (+ AAC) so Windows/macOS stock players can open the file.
# Fall back to any best video+audio, then progressive single-file.
DEFAULT_FORMAT = (
    "bv*[vcodec^=avc]+ba[ext=m4a]/"
    "bv*[vcodec^=avc]+ba/"
    "bv*+ba/b"
)

# AI summary — OpenAI-compatible Chat Completions (e.g. DeepSeek)
SUMMARY_LLM_API_KEY = (os.environ.get("SUMMARY_LLM_API_KEY") or "").strip()
SUMMARY_LLM_BASE_URL = (
    os.environ.get("SUMMARY_LLM_BASE_URL") or "https://api.deepseek.com/v1"
).rstrip("/")
SUMMARY_LLM_MODEL = os.environ.get("SUMMARY_LLM_MODEL") or "deepseek-chat"
SUMMARY_TIMEOUT_SECONDS = int(os.environ.get("SUMMARY_TIMEOUT_SECONDS") or "120")
SUMMARY_MAX_TRANSCRIPT_CHARS = int(
    os.environ.get("SUMMARY_MAX_TRANSCRIPT_CHARS") or "60000"
)
