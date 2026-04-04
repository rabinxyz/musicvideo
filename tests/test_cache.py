"""Tests for the pipeline cache utilities."""

import json
from pathlib import Path

from musicvid.pipeline.cache import get_audio_hash, load_cache, save_cache


class TestGetAudioHash:
    """Tests for audio file hashing."""

    def test_returns_12_char_hex_string(self, tmp_path):
        audio = tmp_path / "song.mp3"
        audio.write_bytes(b"x" * 100_000)
        result = get_audio_hash(str(audio))
        assert len(result) == 12
        assert all(c in "0123456789abcdef" for c in result)

    def test_same_file_same_hash(self, tmp_path):
        audio = tmp_path / "song.mp3"
        audio.write_bytes(b"identical content here" * 1000)
        assert get_audio_hash(str(audio)) == get_audio_hash(str(audio))

    def test_different_content_different_hash(self, tmp_path):
        a = tmp_path / "a.mp3"
        b = tmp_path / "b.mp3"
        a.write_bytes(b"content_a" * 1000)
        b.write_bytes(b"content_b" * 1000)
        assert get_audio_hash(str(a)) != get_audio_hash(str(b))

    def test_only_reads_first_64kb(self, tmp_path):
        """Files that share the first 64KB but differ after should hash the same."""
        shared = b"A" * 65536
        a = tmp_path / "a.mp3"
        b = tmp_path / "b.mp3"
        a.write_bytes(shared + b"extra_a")
        b.write_bytes(shared + b"extra_b")
        assert get_audio_hash(str(a)) == get_audio_hash(str(b))


class TestLoadCache:
    """Tests for loading cached JSON files."""

    def test_returns_none_when_missing(self, tmp_path):
        result = load_cache(str(tmp_path), "nonexistent.json")
        assert result is None

    def test_returns_data_when_exists(self, tmp_path):
        data = {"bpm": 120, "duration": 30.5}
        (tmp_path / "analysis.json").write_text(json.dumps(data))
        result = load_cache(str(tmp_path), "analysis.json")
        assert result == data


class TestSaveCache:
    """Tests for saving cache files."""

    def test_creates_file(self, tmp_path):
        save_cache(str(tmp_path), "test.json", {"key": "value"})
        assert (tmp_path / "test.json").exists()
        loaded = json.loads((tmp_path / "test.json").read_text())
        assert loaded == {"key": "value"}

    def test_creates_directory_if_missing(self, tmp_path):
        cache_dir = tmp_path / "sub" / "dir"
        save_cache(str(cache_dir), "test.json", [1, 2, 3])
        assert (cache_dir / "test.json").exists()
