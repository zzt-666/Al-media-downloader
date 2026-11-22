from pathlib import Path

# Repo root: backend/app/config.py -> parents[2]
REPO_ROOT = Path(__file__).resolve().parents[2]

DOWNLOAD_DIR = REPO_ROOT / "downloads"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

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
