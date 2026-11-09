import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Base storage directory for pending uploaded files
STORAGE_BASE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "storage", "pending_uploads")
)


def _ensure_storage_dir() -> str:
    """Ensure the pending uploads storage directory exists."""
    os.makedirs(STORAGE_BASE_DIR, exist_ok=True)
    return STORAGE_BASE_DIR


def get_pending_file_path(upload_id: str) -> str:
    """Get the absolute filesystem path for a pending upload's raw bytes."""
    storage_dir = _ensure_storage_dir()
    safe_id = os.path.basename(str(upload_id))
    return os.path.join(storage_dir, f"{safe_id}.bin")


def save_pending_file_to_disk(upload_id: str, content: bytes) -> str:
    """
    Persist uploaded file content durably to disk.
    Returns the file path where bytes were saved.
    """
    file_path = get_pending_file_path(upload_id)
    with open(file_path, "wb") as f:
        f.write(content)
    logger.info("Saved pending upload bytes to disk for upload_id=%s (size=%d bytes)", upload_id, len(content))
    return file_path


def read_pending_file_from_disk(upload_id: str) -> Optional[bytes]:
    """
    Read persisted pending upload content from disk.
    Returns bytes if present, or None if file does not exist.
    """
    file_path = get_pending_file_path(upload_id)
    if os.path.exists(file_path):
        try:
            with open(file_path, "rb") as f:
                return f.read()
        except OSError as e:
            logger.error("Failed to read pending upload file %s: %s", file_path, e)
            return None
    return None


def delete_pending_file_from_disk(upload_id: str) -> bool:
    """
    Remove persisted pending upload file from disk after successful ingestion or cancellation.
    """
    file_path = get_pending_file_path(upload_id)
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            logger.info("Deleted pending upload bytes for upload_id=%s", upload_id)
            return True
        except OSError as e:
            logger.warning("Could not delete pending upload file %s: %s", file_path, e)
    return False
