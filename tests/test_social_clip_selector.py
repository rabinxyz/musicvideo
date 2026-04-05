"""Tests for social_clip_selector module."""
import json
from unittest.mock import patch, MagicMock

import pytest

from musicvid.pipeline.social_clip_selector import select_social_clips


def _make_analysis(duration=180.0):
    return {
        "duration": duration,
        "bpm": 120,
        "sections": [
            {"label": "intro", "start": 0.0, "end": 20.0},
            {"label": "verse", "start": 20.0, "end": 60.0},
            {"label": "chorus", "start": 60.0, "end": 90.0},
            {"label": "bridge", "start": 90.0, "end": 120.0},
            {"label": "outro", "start": 120.0, "end": 180.0},
        ],
        "lyrics": [
            {"start": 20.0, "end": 24.0, "text": "First verse line"},
            {"start": 60.0, "end": 64.0, "text": "Chorus line one"},
            {"start": 90.0, "end": 94.0, "text": "Bridge moment"},
        ],
    }


def _mock_claude_response(clips):
    """Helper to create a mock Claude API response."""
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=json.dumps({"clips": clips}))]
    return mock_response


@patch("musicvid.pipeline.social_clip_selector.anthropic")
def test_returns_three_clips_with_required_fields(mock_anthropic):
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client
    clips = [
        {"id": "A", "start": 60.0, "end": 75.0, "section": "chorus", "reason": "Best hook"},
        {"id": "B", "start": 20.0, "end": 35.0, "section": "verse", "reason": "Opening"},
        {"id": "C", "start": 90.0, "end": 105.0, "section": "bridge", "reason": "Emotional peak"},
    ]
    mock_client.messages.create.return_value = _mock_claude_response(clips)

    result = select_social_clips(_make_analysis(), 15)

    assert len(result["clips"]) == 3
    for clip in result["clips"]:
        assert "id" in clip
        assert "start" in clip
        assert "end" in clip
        assert "section" in clip
        assert "reason" in clip


@patch("musicvid.pipeline.social_clip_selector.anthropic")
def test_retries_on_invalid_json(mock_anthropic):
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client

    invalid_response = MagicMock()
    invalid_response.content = [MagicMock(text="not valid json")]
    valid_clips = [
        {"id": "A", "start": 60.0, "end": 75.0, "section": "chorus", "reason": "Hook"},
        {"id": "B", "start": 20.0, "end": 35.0, "section": "verse", "reason": "Verse"},
        {"id": "C", "start": 90.0, "end": 105.0, "section": "bridge", "reason": "Bridge"},
    ]
    valid_response = _mock_claude_response(valid_clips)
    mock_client.messages.create.side_effect = [invalid_response, valid_response]

    result = select_social_clips(_make_analysis(), 15)

    assert mock_client.messages.create.call_count == 2
    assert len(result["clips"]) == 3


@patch("musicvid.pipeline.social_clip_selector.anthropic")
def test_passes_clip_duration_in_prompt(mock_anthropic):
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client
    clips = [
        {"id": "A", "start": 60.0, "end": 90.0, "section": "chorus", "reason": "Hook"},
        {"id": "B", "start": 20.0, "end": 50.0, "section": "verse", "reason": "Verse"},
        {"id": "C", "start": 90.0, "end": 120.0, "section": "bridge", "reason": "Bridge"},
    ]
    mock_client.messages.create.return_value = _mock_claude_response(clips)

    select_social_clips(_make_analysis(), 30)

    call_kwargs = mock_client.messages.create.call_args[1]
    user_content = call_kwargs["messages"][0]["content"]
    assert "30 seconds" in user_content


@patch("musicvid.pipeline.social_clip_selector.anthropic")
def test_fallback_on_all_attempts_fail(mock_anthropic):
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="bad json")]
    mock_client.messages.create.return_value = mock_response

    result = select_social_clips(_make_analysis(duration=180.0), 15)

    assert len(result["clips"]) == 3
    # Fallback clips should be evenly spaced and non-overlapping
    starts = sorted(c["start"] for c in result["clips"])
    for i in range(len(starts) - 1):
        end_i = starts[i] + 15
        assert starts[i + 1] >= end_i  # no overlap


@patch("musicvid.pipeline.social_clip_selector.anthropic")
def test_30s_prompt_mentions_chorus_priority(mock_anthropic):
    """For 30s clips the prompt should mention chorus/refrain as priority."""
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text='{"clips": [{"id": "A", "start": 10.0, "end": 40.0, "section": "chorus", "reason": "test"}, {"id": "B", "start": 60.0, "end": 90.0, "section": "verse", "reason": "test"}, {"id": "C", "start": 120.0, "end": 150.0, "section": "bridge", "reason": "test"}]}')]
    mock_client.messages.create.return_value = mock_response

    analysis = {
        "lyrics": [{"start": 0.0, "end": 30.0, "text": "test lyric"}],
        "sections": [{"label": "chorus", "start": 0.0, "end": 30.0}],
        "duration": 180.0,
        "bpm": 120,
    }
    select_social_clips(analysis, 30)

    call_args = mock_client.messages.create.call_args
    user_message = call_args[1]["messages"][0]["content"]
    assert "Pełny refren" in user_message or "refren" in user_message.lower() or "chorus" in user_message.lower()


@patch("musicvid.pipeline.social_clip_selector.anthropic")
def test_15s_prompt_no_chorus_priority_block(mock_anthropic):
    """For 15s clips the chorus-priority block is NOT added."""
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text='{"clips": [{"id": "A", "start": 10.0, "end": 25.0, "section": "verse", "reason": "test"}, {"id": "B", "start": 60.0, "end": 75.0, "section": "chorus", "reason": "test"}, {"id": "C", "start": 120.0, "end": 135.0, "section": "bridge", "reason": "test"}]}')]
    mock_client.messages.create.return_value = mock_response

    analysis = {
        "lyrics": [{"start": 0.0, "end": 15.0, "text": "test lyric"}],
        "sections": [{"label": "verse", "start": 0.0, "end": 15.0}],
        "duration": 180.0,
        "bpm": 120,
    }
    select_social_clips(analysis, 15)

    call_args = mock_client.messages.create.call_args
    user_message = call_args[1]["messages"][0]["content"]
    assert "Pełny refren (priorytet najwyższy)" not in user_message


@patch("musicvid.pipeline.social_clip_selector.anthropic")
def test_rejects_response_with_wrong_clip_count(mock_anthropic):
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client

    # First response: only 2 clips (wrong)
    two_clips_response = MagicMock()
    two_clips_response.content = [MagicMock(text=json.dumps({"clips": [
        {"id": "A", "start": 60.0, "end": 75.0, "section": "chorus", "reason": "Hook"},
        {"id": "B", "start": 20.0, "end": 35.0, "section": "verse", "reason": "Verse"},
    ]}))]

    # Second response: 3 clips (correct)
    valid_clips = [
        {"id": "A", "start": 60.0, "end": 75.0, "section": "chorus", "reason": "Hook"},
        {"id": "B", "start": 20.0, "end": 35.0, "section": "verse", "reason": "Verse"},
        {"id": "C", "start": 90.0, "end": 105.0, "section": "bridge", "reason": "Bridge"},
    ]
    mock_client.messages.create.side_effect = [two_clips_response, _mock_claude_response(valid_clips)]

    result = select_social_clips(_make_analysis(), 15)

    assert mock_client.messages.create.call_count == 2
    assert len(result["clips"]) == 3
