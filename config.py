"""Central configuration and folder locations for FinSight."""

from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv

load_dotenv()

# Keep all generated data inside the project so the workspace is portable.
ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
PROCESSED_DIR = DATA_DIR / "processed"
VECTOR_DIR = DATA_DIR / "vector_db"

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".csv", ".xlsx", ".xls"}

# These defaults can be overridden in the local .env file.
MAX_FILE_MB = float(os.getenv("MAX_FILE_MB", "25"))
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "900"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "120"))
RETRIEVAL_K = int(os.getenv("RETRIEVAL_K", "4"))
CHAT_MODEL = os.getenv("GEMINI_CHAT_MODEL", "gemini-3.5-flash-lite")
EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-2")


# A frozen settings object prevents accidental changes while the app is running.
@dataclass(frozen=True)
class Settings:
    """Read-only settings passed to the UI and document-processing code."""

    root: Path = ROOT
    max_file_mb: float = MAX_FILE_MB
    chunk_size: int = CHUNK_SIZE
    chunk_overlap: int = CHUNK_OVERLAP
    retrieval_k: int = RETRIEVAL_K
    chat_model: str = CHAT_MODEL
    embedding_model: str = EMBEDDING_MODEL


# Create the folders before any upload or vector database operation uses them.
def ensure_directories() -> None:
    """Create the folders used for uploads, metadata, and vector data."""
    for folder in (UPLOAD_DIR, PROCESSED_DIR, VECTOR_DIR):
        folder.mkdir(parents=True, exist_ok=True)


# Read either supported environment-variable name for the Gemini key.
def api_key() -> str:
    """Return the Gemini key, accepting either common environment name."""
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    google_key = os.getenv("GOOGLE_API_KEY", "").strip()
    return gemini_key or google_key
