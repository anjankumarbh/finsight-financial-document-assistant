"""Simple local workspace persistence."""

import json
import shutil
from pathlib import Path

from .config import PROCESSED_DIR, UPLOAD_DIR, VECTOR_DIR, ensure_directories


# Keep the original bytes so the workspace can be restored after a restart.
def save_upload(name: str, data: bytes) -> Path:
    """Save an accepted upload in the local workspace."""
    ensure_directories()
    path = UPLOAD_DIR / Path(name).name
    path.write_bytes(data)
    return path


# Store only lightweight metadata; the document text stays in the index.
def save_processed(name: str, payload: dict) -> None:
    """Save small processing metadata for later inspection or restart."""
    ensure_directories()
    output = PROCESSED_DIR / f"{Path(name).stem}.json"
    output.write_text(
        json.dumps(payload, indent=2, default=str),
        encoding="utf-8",
    )


# The Clear workspace button calls this function to reset the local project data.
def clear_workspace() -> None:
    """Remove uploaded files, metadata, and persisted vector data."""
    for folder in (UPLOAD_DIR, PROCESSED_DIR, VECTOR_DIR):
        if folder.exists():
            for child in folder.iterdir():
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink()
