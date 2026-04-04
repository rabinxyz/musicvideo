"""Cache utilities for the MusicVid pipeline."""

import hashlib
import json
from pathlib import Path


def get_audio_hash(audio_path):
    """Return a 12-char hex hash of the first 64KB of the audio file."""
    with open(audio_path, "rb") as f:
        data = f.read(65536)
    return hashlib.md5(data).hexdigest()[:12]


def load_cache(cache_dir, filename):
    """Load a JSON cache file if it exists, else return None."""
    path = Path(cache_dir) / filename
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return None


def save_cache(cache_dir, filename, data):
    """Save data as JSON to cache_dir/filename."""
    path = Path(cache_dir) / filename
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
