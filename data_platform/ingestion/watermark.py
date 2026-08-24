import json
import os
from pathlib import Path
from datetime import datetime

METADATA_DIR = Path(__file__).resolve().parents[2] / "data_platform" / "metadata" / "watermarks"
WATERMARK_FILE = METADATA_DIR / "watermarks.json"

def _load_watermarks() -> dict:
    """Load watermarks from the local JSON file."""
    if not WATERMARK_FILE.exists():
        return {}
    try:
        with open(WATERMARK_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_watermarks(watermarks: dict) -> None:
    """Save watermarks to the local JSON file."""
    METADATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(WATERMARK_FILE, "w") as f:
        json.dump(watermarks, f, indent=2)

def get_watermark(table_name: str) -> str:
    """Get the watermark timestamp for a table. Returns '1970-01-01 00:00:00' if not found."""
    watermarks = _load_watermarks()
    return watermarks.get(table_name, "1970-01-01 00:00:00")

def update_watermark(table_name: str, watermark: str) -> None:
    """Update the watermark timestamp for a table."""
    watermarks = _load_watermarks()
    watermarks[table_name] = watermark
    _save_watermarks(watermarks)

def clear_watermarks() -> None:
    """Clear all stored watermarks (useful for full reloads)."""
    if WATERMARK_FILE.exists():
        os.remove(WATERMARK_FILE)
