"""Tests for the lyrics parser module."""

import pytest

from musicvid.pipeline.lyrics_parser import parse


class TestVariantA:
    """Variant A: lines without timestamps, evenly distributed."""

    def test_four_lines_60s_audio(self, tmp_path):
        lyrics_file = tmp_path / "lyrics.txt"
        lyrics_file.write_text("Line one\nLine two\nLine three\nLine four\n")
        result = parse(str(lyrics_file), 60.0)
        assert len(result) == 4
        assert result[0] == {"start": 0.0, "end": 14.7, "text": "Line one"}
        assert result[1] == {"start": 15.0, "end": 29.7, "text": "Line two"}
        assert result[2] == {"start": 30.0, "end": 44.7, "text": "Line three"}
        assert result[3] == {"start": 45.0, "end": 59.7, "text": "Line four"}

    def test_single_line(self, tmp_path):
        lyrics_file = tmp_path / "lyrics.txt"
        lyrics_file.write_text("Only line\n")
        result = parse(str(lyrics_file), 10.0)
        assert len(result) == 1
        assert result[0] == {"start": 0.0, "end": 9.7, "text": "Only line"}

    def test_blank_lines_are_skipped(self, tmp_path):
        lyrics_file = tmp_path / "lyrics.txt"
        lyrics_file.write_text("Line one\n\nLine two\n\n")
        result = parse(str(lyrics_file), 20.0)
        assert len(result) == 2
        assert result[0]["text"] == "Line one"
        assert result[1]["text"] == "Line two"

    def test_empty_file_raises_value_error(self, tmp_path):
        lyrics_file = tmp_path / "lyrics.txt"
        lyrics_file.write_text("")
        with pytest.raises(ValueError, match="empty"):
            parse(str(lyrics_file), 60.0)

    def test_whitespace_only_file_raises_value_error(self, tmp_path):
        lyrics_file = tmp_path / "lyrics.txt"
        lyrics_file.write_text("   \n  \n")
        with pytest.raises(ValueError, match="empty"):
            parse(str(lyrics_file), 60.0)
