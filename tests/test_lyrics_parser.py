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


class TestVariantB:
    """Variant B: lines with MM:SS or HH:MM:SS timestamps."""

    def test_mm_ss_format(self, tmp_path):
        lyrics_file = tmp_path / "lyrics.txt"
        lyrics_file.write_text("0:00 First line\n0:30 Second line\n1:00 Third line\n")
        result = parse(str(lyrics_file), 90.0)
        assert len(result) == 3
        assert result[0] == {"start": 0.0, "end": 29.7, "text": "First line"}
        assert result[1] == {"start": 30.0, "end": 59.7, "text": "Second line"}
        assert result[2] == {"start": 60.0, "end": 89.0, "text": "Third line"}

    def test_hh_mm_ss_format(self, tmp_path):
        lyrics_file = tmp_path / "lyrics.txt"
        lyrics_file.write_text("0:00:00 Opening\n0:01:30 Middle\n0:03:00 End\n")
        result = parse(str(lyrics_file), 240.0)
        assert len(result) == 3
        assert result[0] == {"start": 0.0, "end": 89.7, "text": "Opening"}
        assert result[1] == {"start": 90.0, "end": 179.7, "text": "Middle"}
        assert result[2] == {"start": 180.0, "end": 239.0, "text": "End"}

    def test_last_line_ends_at_duration_minus_one(self, tmp_path):
        lyrics_file = tmp_path / "lyrics.txt"
        lyrics_file.write_text("0:00 Only line\n")
        result = parse(str(lyrics_file), 60.0)
        assert len(result) == 1
        assert result[0]["end"] == 59.0

    def test_two_digit_minutes(self, tmp_path):
        lyrics_file = tmp_path / "lyrics.txt"
        lyrics_file.write_text("00:00 Start\n12:30 Later\n")
        result = parse(str(lyrics_file), 800.0)
        assert result[0]["start"] == 0.0
        assert result[1]["start"] == 750.0


from musicvid.pipeline.lyrics_parser import merge_whisper_with_lyrics_file


class TestMergeWhisperWithLyricsFile:
    """Tests for deterministic Whisper+lyrics alignment."""

    def _make_segments(self, count, start=0.0, duration=2.0):
        """Create N evenly-spaced whisper segments."""
        return [
            {"start": start + i * duration, "end": start + i * duration + duration - 0.2, "text": f"seg{i}"}
            for i in range(count)
        ]

    def _make_lines(self, count):
        return [f"Line {i+1}" for i in range(count)]

    def test_equal_segments_and_lines_maps_one_to_one(self):
        segments = self._make_segments(8)
        lines = self._make_lines(8)
        result = merge_whisper_with_lyrics_file(segments, lines, 20.0)
        assert len(result) == 8
        assert result[3]["text"] == "Line 4"
        assert result[3]["start"] == pytest.approx(segments[3]["start"] - 0.05, abs=0.01)

    def test_more_segments_than_lines_groups_proportionally(self):
        segments = self._make_segments(12)
        lines = self._make_lines(6)
        result = merge_whisper_with_lyrics_file(segments, lines, 30.0)
        assert len(result) == 6
        assert result[0]["start"] == pytest.approx(max(0.0, segments[0]["start"] - 0.05), abs=0.01)
        assert result[5]["end"] == pytest.approx(segments[11]["end"], abs=0.01)
        for item in result:
            assert item["text"] in lines

    def test_fewer_segments_than_lines_splits_time(self):
        segments = self._make_segments(4, duration=3.0)
        lines = self._make_lines(12)
        result = merge_whisper_with_lyrics_file(segments, lines, 12.0)
        assert len(result) == 12
        for item in result:
            assert item["start"] >= 0.0
            assert item["end"] > item["start"]

    def test_no_overlap_between_subtitles(self):
        segments = [
            {"start": 0.0, "end": 5.0, "text": "seg0"},
            {"start": 5.0, "end": 10.0, "text": "seg1"},
        ]
        lines = ["Line one", "Line two"]
        result = merge_whisper_with_lyrics_file(segments, lines, 10.0)
        # Step 3 enforces 0.15s gap before step 4 applies -0.05s pre-display
        # offset to start times, so the final gap can be as low as 0.10s.
        # Assert no actual overlap in the final output.
        for i in range(len(result) - 1):
            gap = result[i+1]["start"] - result[i]["end"]
            assert gap >= -0.001

    def test_minimum_subtitle_duration(self):
        segments = [{"start": 0.0, "end": 0.3, "text": "short"}]
        lines = ["Short line"]
        result = merge_whisper_with_lyrics_file(segments, lines, 10.0)
        assert result[0]["end"] - result[0]["start"] >= 0.8

    def test_maximum_subtitle_duration(self):
        segments = [{"start": 0.0, "end": 20.0, "text": "very long"}]
        lines = ["Long line"]
        result = merge_whisper_with_lyrics_file(segments, lines, 25.0)
        assert result[0]["end"] - result[0]["start"] <= 8.0

    def test_empty_lines_raises_value_error(self):
        segments = [{"start": 0.0, "end": 2.0, "text": "seg"}]
        with pytest.raises(ValueError, match="empty"):
            merge_whisper_with_lyrics_file(segments, [], 10.0)

    def test_empty_whisper_segments_filtered_before_matching(self):
        segments = [
            {"start": 0.0, "end": 1.0, "text": "  "},
            {"start": 1.0, "end": 3.0, "text": "real"},
        ]
        lines = ["Correct line"]
        result = merge_whisper_with_lyrics_file(segments, lines, 5.0)
        assert len(result) == 1
        assert result[0]["text"] == "Correct line"

    def test_result_sorted_chronologically(self):
        segments = self._make_segments(4)
        lines = self._make_lines(4)
        result = merge_whisper_with_lyrics_file(segments, lines, 10.0)
        starts = [r["start"] for r in result]
        assert starts == sorted(starts)

    def test_pre_display_offset_applied(self):
        segments = [{"start": 1.0, "end": 3.0, "text": "seg"}]
        lines = ["Line"]
        result = merge_whisper_with_lyrics_file(segments, lines, 5.0)
        assert result[0]["start"] == pytest.approx(0.95, abs=0.01)

    def test_pre_display_offset_clamped_to_zero(self):
        segments = [{"start": 0.03, "end": 2.0, "text": "seg"}]
        lines = ["Line"]
        result = merge_whisper_with_lyrics_file(segments, lines, 5.0)
        assert result[0]["start"] >= 0.0
