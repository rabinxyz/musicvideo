"""Tests for audio_analyzer module."""

import json
from unittest.mock import patch, MagicMock
from pathlib import Path

import pytest
import numpy as np

from musicvid.pipeline.audio_analyzer import analyze_audio


@pytest.fixture
def mock_whisper_result():
    """Mock Whisper transcription result."""
    return {
        "segments": [
            {
                "start": 0.5,
                "end": 2.0,
                "text": " Amazing grace how sweet the sound",
                "words": [
                    {"word": " Amazing", "start": 0.5, "end": 0.9},
                    {"word": " grace", "start": 0.9, "end": 1.2},
                    {"word": " how", "start": 1.2, "end": 1.4},
                    {"word": " sweet", "start": 1.4, "end": 1.6},
                    {"word": " the", "start": 1.6, "end": 1.7},
                    {"word": " sound", "start": 1.7, "end": 2.0},
                ],
            },
        ],
        "language": "en",
    }


@pytest.fixture
def mock_audio_signal():
    """Mock audio signal (10 seconds at 22050 Hz)."""
    sr = 22050
    duration = 10.0
    y = np.random.randn(int(sr * duration)).astype(np.float32)
    return y, sr


class TestAnalyzeAudio:
    """Tests for the analyze_audio function."""

    @patch("musicvid.pipeline.audio_analyzer.whisper")
    @patch("musicvid.pipeline.audio_analyzer.librosa")
    def test_returns_required_keys(self, mock_librosa, mock_whisper, mock_whisper_result, mock_audio_signal, tmp_path):
        y, sr = mock_audio_signal

        mock_model = MagicMock()
        mock_model.transcribe.return_value = mock_whisper_result
        mock_whisper.load_model.return_value = mock_model

        mock_librosa.load.return_value = (y, sr)
        mock_librosa.beat.beat_track.return_value = (120.0, np.array([0, 11025, 22050]))
        mock_librosa.get_duration.return_value = 10.0
        mock_librosa.frames_to_time.return_value = np.array([0.0, 0.5, 1.0])

        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio data")

        result = analyze_audio(str(audio_file))

        assert "lyrics" in result
        assert "beats" in result
        assert "bpm" in result
        assert "duration" in result
        assert "sections" in result
        assert "mood_energy" in result
        assert "language" in result

    @patch("musicvid.pipeline.audio_analyzer.whisper")
    @patch("musicvid.pipeline.audio_analyzer.librosa")
    def test_lyrics_have_word_timestamps(self, mock_librosa, mock_whisper, mock_whisper_result, mock_audio_signal, tmp_path):
        y, sr = mock_audio_signal

        mock_model = MagicMock()
        mock_model.transcribe.return_value = mock_whisper_result
        mock_whisper.load_model.return_value = mock_model

        mock_librosa.load.return_value = (y, sr)
        mock_librosa.beat.beat_track.return_value = (120.0, np.array([0]))
        mock_librosa.get_duration.return_value = 10.0
        mock_librosa.frames_to_time.return_value = np.array([0.0])

        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio data")

        result = analyze_audio(str(audio_file))

        assert len(result["lyrics"]) > 0
        segment = result["lyrics"][0]
        assert "start" in segment
        assert "end" in segment
        assert "text" in segment
        assert "words" in segment
        assert len(segment["words"]) > 0
        word = segment["words"][0]
        assert "word" in word
        assert "start" in word
        assert "end" in word

    @patch("musicvid.pipeline.audio_analyzer.whisper")
    @patch("musicvid.pipeline.audio_analyzer.librosa")
    def test_beats_are_float_list(self, mock_librosa, mock_whisper, mock_whisper_result, mock_audio_signal, tmp_path):
        y, sr = mock_audio_signal

        mock_model = MagicMock()
        mock_model.transcribe.return_value = mock_whisper_result
        mock_whisper.load_model.return_value = mock_model

        mock_librosa.load.return_value = (y, sr)
        mock_librosa.beat.beat_track.return_value = (120.0, np.array([0, 11025, 22050]))
        mock_librosa.get_duration.return_value = 10.0
        mock_librosa.frames_to_time.return_value = np.array([0.0, 0.5, 1.0])

        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio data")

        result = analyze_audio(str(audio_file))

        assert isinstance(result["beats"], list)
        assert all(isinstance(b, float) for b in result["beats"])

    @patch("musicvid.pipeline.audio_analyzer.whisper")
    @patch("musicvid.pipeline.audio_analyzer.librosa")
    def test_sections_have_labels_and_times(self, mock_librosa, mock_whisper, mock_whisper_result, mock_audio_signal, tmp_path):
        y, sr = mock_audio_signal

        mock_model = MagicMock()
        mock_model.transcribe.return_value = mock_whisper_result
        mock_whisper.load_model.return_value = mock_model

        mock_librosa.load.return_value = (y, sr)
        mock_librosa.beat.beat_track.return_value = (120.0, np.array([0]))
        mock_librosa.get_duration.return_value = 10.0
        mock_librosa.frames_to_time.return_value = np.array([0.0])

        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio data")

        result = analyze_audio(str(audio_file))

        assert len(result["sections"]) > 0
        section = result["sections"][0]
        assert "label" in section
        assert "start" in section
        assert "end" in section

    @patch("musicvid.pipeline.audio_analyzer.whisper")
    @patch("musicvid.pipeline.audio_analyzer.librosa")
    def test_saves_to_output_dir(self, mock_librosa, mock_whisper, mock_whisper_result, mock_audio_signal, tmp_path):
        y, sr = mock_audio_signal

        mock_model = MagicMock()
        mock_model.transcribe.return_value = mock_whisper_result
        mock_whisper.load_model.return_value = mock_model

        mock_librosa.load.return_value = (y, sr)
        mock_librosa.beat.beat_track.return_value = (120.0, np.array([0]))
        mock_librosa.get_duration.return_value = 10.0
        mock_librosa.frames_to_time.return_value = np.array([0.0])

        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio data")
        output_dir = tmp_path / "output" / "tmp"
        output_dir.mkdir(parents=True)

        result = analyze_audio(str(audio_file), output_dir=str(output_dir))

        saved_file = output_dir / "analysis.json"
        assert saved_file.exists()
        saved_data = json.loads(saved_file.read_text())
        assert saved_data["bpm"] == result["bpm"]

    @patch("musicvid.pipeline.audio_analyzer.whisper")
    @patch("musicvid.pipeline.audio_analyzer.librosa")
    def test_transcribe_uses_polish_language_params(self, mock_librosa, mock_whisper, mock_whisper_result, mock_audio_signal, tmp_path):
        y, sr = mock_audio_signal

        mock_model = MagicMock()
        mock_model.transcribe.return_value = mock_whisper_result
        mock_whisper.load_model.return_value = mock_model

        mock_librosa.load.return_value = (y, sr)
        mock_librosa.beat.beat_track.return_value = (120.0, np.array([0]))
        mock_librosa.get_duration.return_value = 10.0
        mock_librosa.frames_to_time.return_value = np.array([0.0])

        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio data")

        analyze_audio(str(audio_file))

        call_kwargs = mock_model.transcribe.call_args[1]
        assert call_kwargs["language"] == "pl"
        assert call_kwargs["temperature"] == 0.0
        assert call_kwargs["condition_on_previous_text"] is True
        assert "initial_prompt" in call_kwargs
        assert "Polska" in call_kwargs["initial_prompt"]
