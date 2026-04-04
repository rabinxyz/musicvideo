"""Tests for clip_selector module."""
import json
from unittest.mock import patch, MagicMock

import pytest

from musicvid.pipeline.clip_selector import select_clip


def _make_analysis(duration=180.0):
    return {
        "duration": duration,
        "bpm": 120,
        "sections": [
            {"label": "intro", "start": 0.0, "end": 20.0},
            {"label": "chorus", "start": 45.0, "end": 75.0},
        ],
        "lyrics": [
            {"start": 45.0, "end": 48.0, "text": "Amazing grace"},
            {"start": 48.0, "end": 52.0, "text": "How sweet the sound"},
            {"start": 52.0, "end": 56.0, "text": "That saved a wretch like me"},
        ],
    }


@patch("musicvid.pipeline.clip_selector.anthropic")
def test_select_clip_returns_start_end_reason(mock_anthropic):
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=json.dumps({
        "start": 45.0,
        "end": 60.0,
        "reason": "chorus is most recognizable",
    }))]
    mock_client.messages.create.return_value = mock_response

    result = select_clip(_make_analysis(), 15)

    assert result["start"] == 45.0
    assert result["end"] == 60.0
    assert "reason" in result


@patch("musicvid.pipeline.clip_selector.anthropic")
def test_select_clip_retries_on_invalid_json(mock_anthropic):
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client

    invalid_response = MagicMock()
    invalid_response.content = [MagicMock(text="not valid json")]
    valid_response = MagicMock()
    valid_response.content = [MagicMock(text=json.dumps({
        "start": 30.0,
        "end": 45.0,
        "reason": "chorus",
    }))]
    mock_client.messages.create.side_effect = [invalid_response, valid_response]

    result = select_clip(_make_analysis(), 15)

    assert mock_client.messages.create.call_count == 2
    assert result["start"] == 30.0


@patch("musicvid.pipeline.clip_selector.anthropic")
def test_select_clip_passes_clip_duration_in_prompt(mock_anthropic):
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=json.dumps({
        "start": 60.0,
        "end": 90.0,
        "reason": "chorus",
    }))]
    mock_client.messages.create.return_value = mock_response

    select_clip(_make_analysis(), 30)

    call_kwargs = mock_client.messages.create.call_args[1]
    user_content = call_kwargs["messages"][0]["content"]
    assert "30-second" in user_content


@patch("musicvid.pipeline.clip_selector.anthropic")
def test_select_clip_fallback_on_all_attempts_fail(mock_anthropic):
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="bad json")]
    mock_client.messages.create.return_value = mock_response

    result = select_clip(_make_analysis(duration=120.0), 15)

    # Fallback: center of 120s song → start at 52.5, end at 67.5
    assert result["start"] == pytest.approx(52.5, abs=1.0)
    assert result["end"] == pytest.approx(67.5, abs=1.0)
    assert "reason" in result
