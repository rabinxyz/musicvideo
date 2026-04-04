"""Tests for AI lyrics alignment using Claude API."""

import json
from unittest.mock import patch, MagicMock

import pytest

from musicvid.pipeline.lyrics_parser import align_with_claude


class TestAlignWithClaude:
    """Tests for align_with_claude function."""

    def _make_mock_response(self, content):
        """Helper to create a mock Claude API response."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=content)]
        return mock_response

    @patch("musicvid.pipeline.lyrics_parser.anthropic")
    def test_equal_segments_and_lines(self, mock_anthropic):
        """When N_segments == N_lines, each line maps to one segment."""
        whisper_segments = [
            {"start": 0.5, "end": 2.0, "text": "Amezing grejz hau swit de saund"},
            {"start": 2.5, "end": 4.0, "text": "Det sejwd a recz lajk mi"},
        ]
        file_lines = [
            "Amazing grace how sweet the sound",
            "That saved a wretch like me",
        ]
        expected = [
            {"start": 0.5, "end": 2.0, "text": "Amazing grace how sweet the sound"},
            {"start": 2.5, "end": 4.0, "text": "That saved a wretch like me"},
        ]

        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.create.return_value = self._make_mock_response(json.dumps(expected))

        result = align_with_claude(whisper_segments, file_lines)

        assert result == expected
        mock_client.messages.create.assert_called_once()
        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["model"] == "claude-sonnet-4-20250514"
        assert call_kwargs["max_tokens"] == 2000

    @patch("musicvid.pipeline.lyrics_parser.anthropic")
    def test_more_segments_than_lines_merges(self, mock_anthropic):
        """When N_segments > N_lines, Claude merges segments."""
        whisper_segments = [
            {"start": 0.0, "end": 1.0, "text": "seg1"},
            {"start": 1.0, "end": 2.0, "text": "seg2"},
            {"start": 2.0, "end": 3.0, "text": "seg3"},
        ]
        file_lines = ["Line one", "Line two"]
        merged = [
            {"start": 0.0, "end": 2.0, "text": "Line one"},
            {"start": 2.0, "end": 3.0, "text": "Line two"},
        ]

        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.create.return_value = self._make_mock_response(json.dumps(merged))

        result = align_with_claude(whisper_segments, file_lines)

        assert result == merged

    @patch("musicvid.pipeline.lyrics_parser.anthropic")
    def test_more_lines_than_segments_splits(self, mock_anthropic):
        """When N_lines > N_segments, Claude splits time for extra lines."""
        whisper_segments = [
            {"start": 0.0, "end": 2.0, "text": "seg1"},
        ]
        file_lines = ["Line one", "Line two", "Line three"]
        split = [
            {"start": 0.0, "end": 2.0, "text": "Line one"},
            {"start": 2.0, "end": 3.0, "text": "Line two"},
            {"start": 3.0, "end": 4.0, "text": "Line three"},
        ]

        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.create.return_value = self._make_mock_response(json.dumps(split))

        result = align_with_claude(whisper_segments, file_lines)

        assert result == split

    @patch("musicvid.pipeline.lyrics_parser.anthropic")
    def test_empty_segments_filtered(self, mock_anthropic):
        """Empty Whisper segments (text.strip()=='') should be filtered before sending."""
        whisper_segments = [
            {"start": 0.0, "end": 1.0, "text": "  "},
            {"start": 1.0, "end": 2.0, "text": "actual text"},
        ]
        file_lines = ["Correct text"]
        expected = [{"start": 1.0, "end": 2.0, "text": "Correct text"}]

        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.create.return_value = self._make_mock_response(json.dumps(expected))

        result = align_with_claude(whisper_segments, file_lines)

        assert result == expected
        call_kwargs = mock_client.messages.create.call_args[1]
        user_msg = call_kwargs["messages"][0]["content"]
        assert "actual text" in user_msg
        assert '"  "' not in user_msg

    @patch("musicvid.pipeline.lyrics_parser.anthropic")
    def test_validates_response_format(self, mock_anthropic):
        """Response missing required keys should raise ValueError."""
        whisper_segments = [{"start": 0.0, "end": 1.0, "text": "seg"}]
        file_lines = ["Line"]
        bad_response = [{"start": 0.0, "text": "Line"}]  # missing "end"

        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.create.return_value = self._make_mock_response(json.dumps(bad_response))

        with pytest.raises(ValueError, match="missing required key"):
            align_with_claude(whisper_segments, file_lines)

    @patch("musicvid.pipeline.lyrics_parser.anthropic")
    def test_json_parse_error_retries_then_raises(self, mock_anthropic):
        """Invalid JSON should retry up to 2 times, then raise ValueError."""
        whisper_segments = [{"start": 0.0, "end": 1.0, "text": "seg"}]
        file_lines = ["Line"]

        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.create.return_value = self._make_mock_response("not valid json {{{")

        with pytest.raises(ValueError, match="Failed to parse"):
            align_with_claude(whisper_segments, file_lines)

        # Should have been called 2 times (initial + 1 retry)
        assert mock_client.messages.create.call_count == 2

    @patch("musicvid.pipeline.lyrics_parser.anthropic")
    def test_prompt_contains_whisper_segments_and_file_lines(self, mock_anthropic):
        """Verify the prompt includes both Whisper segments and file lines."""
        whisper_segments = [{"start": 0.5, "end": 2.0, "text": "Whisper text here"}]
        file_lines = ["Correct lyrics text"]
        expected = [{"start": 0.5, "end": 2.0, "text": "Correct lyrics text"}]

        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.create.return_value = self._make_mock_response(json.dumps(expected))

        align_with_claude(whisper_segments, file_lines)

        call_kwargs = mock_client.messages.create.call_args[1]
        user_msg = call_kwargs["messages"][0]["content"]
        system_msg = call_kwargs["system"]

        assert "Whisper text here" in user_msg
        assert "Correct lyrics text" in user_msg
        assert "JSON" in system_msg

    @patch("musicvid.pipeline.lyrics_parser.anthropic")
    def test_strips_markdown_code_block_from_response(self, mock_anthropic):
        """If Claude wraps response in ```json...```, strip it."""
        whisper_segments = [{"start": 0.0, "end": 1.0, "text": "seg"}]
        file_lines = ["Line"]
        expected = [{"start": 0.0, "end": 1.0, "text": "Line"}]

        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        wrapped = '```json\n' + json.dumps(expected) + '\n```'
        mock_client.messages.create.return_value = self._make_mock_response(wrapped)

        result = align_with_claude(whisper_segments, file_lines)

        assert result == expected
