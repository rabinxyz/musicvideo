# MusicVid MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a CLI app that takes an audio file and generates a synchronized MP4 music video using stock footage, beat-synced cuts, and whisper-based subtitles.

**Architecture:** Pipeline of 4 stages (analyze → direct → fetch → assemble) orchestrated by a Click CLI. Each stage reads the previous stage's JSON output from `output/tmp/`. External APIs (Whisper, Claude, Pexels) are wrapped with tenacity retry. MoviePy + FFmpeg handle final video assembly.

**Tech Stack:** Python 3.11+, openai-whisper, librosa, anthropic SDK, Pexels API, MoviePy, FFmpeg, Click, tenacity

---

## File Structure

```
musicvid/
├── __init__.py                  # Package init, version
├── musicvid.py                  # Click CLI entry point
├── pipeline/
│   ├── __init__.py
│   ├── audio_analyzer.py        # Stage 1: Whisper transcription + librosa analysis
│   ├── director.py              # Stage 2: Claude scene planning
│   ├── stock_fetcher.py         # Stage 3: Pexels video fetching
│   └── assembler.py             # Stage 4: MoviePy video assembly
├── prompts/
│   └── director_system.txt      # System prompt for Claude director
├── requirements.txt
└── .env.example
tests/
├── __init__.py
├── conftest.py                  # Shared fixtures (sample analysis data, etc.)
├── test_audio_analyzer.py
├── test_director.py
├── test_stock_fetcher.py
├── test_assembler.py
└── test_cli.py
```

---

### Task 1: Project Scaffolding & Dependencies

**Files:**
- Create: `musicvid/__init__.py`
- Create: `musicvid/pipeline/__init__.py`
- Create: `musicvid/prompts/director_system.txt`
- Create: `musicvid/requirements.txt`
- Create: `musicvid/.env.example`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `setup.py`

- [ ] **Step 1: Create package structure**

```bash
mkdir -p musicvid/pipeline musicvid/prompts tests
```

- [ ] **Step 2: Write musicvid/__init__.py**

```python
"""Christian Music Video Generator."""

__version__ = "0.1.0"
```

- [ ] **Step 3: Write musicvid/pipeline/__init__.py**

```python
"""Pipeline stages for music video generation."""
```

- [ ] **Step 4: Write requirements.txt**

```
anthropic>=0.40.0
openai>=1.50.0
openai-whisper>=20231117
librosa>=0.10.0
moviepy>=1.0.3
click>=8.1.0
requests>=2.31.0
Pillow>=10.0.0
numpy>=1.24.0
soundfile>=0.12.0
pyyaml>=6.0
python-dotenv>=1.0.0
tqdm>=4.66.0
tenacity>=8.2.0
pytest>=7.0.0
```

- [ ] **Step 5: Write .env.example**

```
ANTHROPIC_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here
PEXELS_API_KEY=your_key_here
```

- [ ] **Step 6: Write setup.py**

```python
from setuptools import setup, find_packages

setup(
    name="musicvid",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        line.strip()
        for line in open("musicvid/requirements.txt")
        if line.strip() and not line.startswith("#")
    ],
    entry_points={
        "console_scripts": [
            "musicvid=musicvid.musicvid:cli",
        ],
    },
)
```

- [ ] **Step 7: Write director_system.txt prompt**

```
You are a music video director specializing in Protestant Christian worship music videos.

You will receive an audio analysis containing lyrics, beats, BPM, duration, sections, and mood/energy data.

Your job is to create a detailed scene plan for the music video as pure JSON (no markdown, no code fences).

STYLE RULES:
- Protestant Christian aesthetic only
- NO Catholic imagery: no Mary, no saints, no religious figures/statues
- ALLOWED: nature, light, simple cross, people in worship, abstract spiritual imagery
- Match visual energy to musical energy (quiet sections = calm visuals, climax = dramatic)

OUTPUT FORMAT (pure JSON):
{
  "overall_style": "contemplative|joyful|worship|powerful",
  "color_palette": ["#hex1", "#hex2", "#hex3"],
  "subtitle_style": {
    "font_size": 48,
    "color": "#FFFFFF",
    "outline_color": "#000000",
    "position": "center-bottom",
    "animation": "fade"
  },
  "scenes": [
    {
      "section": "intro|verse|chorus|bridge|outro",
      "start": 0.0,
      "end": 15.0,
      "visual_prompt": "Detailed description for stock video search",
      "motion": "slow_zoom_in|slow_zoom_out|pan_left|pan_right|static",
      "transition": "crossfade|cut|fade_black",
      "overlay": "none|particles|light_rays|bokeh"
    }
  ]
}

IMPORTANT:
- Scenes must cover the entire duration with no gaps
- Each scene should be 5-15 seconds long
- Transitions should align with beat times when possible
- Visual prompts should be specific enough to find matching stock footage
- Match the number of scenes to the song structure
```

- [ ] **Step 8: Write tests/conftest.py with shared fixtures**

```python
"""Shared test fixtures for musicvid tests."""

import pytest


@pytest.fixture
def sample_analysis():
    """Sample audio analysis output for testing downstream stages."""
    return {
        "lyrics": [
            {"start": 0.5, "end": 2.0, "text": "Amazing grace how sweet the sound",
             "words": [
                 {"word": "Amazing", "start": 0.5, "end": 0.9},
                 {"word": "grace", "start": 0.9, "end": 1.2},
                 {"word": "how", "start": 1.2, "end": 1.4},
                 {"word": "sweet", "start": 1.4, "end": 1.6},
                 {"word": "the", "start": 1.6, "end": 1.7},
                 {"word": "sound", "start": 1.7, "end": 2.0},
             ]},
            {"start": 2.5, "end": 4.0, "text": "That saved a wretch like me",
             "words": [
                 {"word": "That", "start": 2.5, "end": 2.7},
                 {"word": "saved", "start": 2.7, "end": 3.0},
                 {"word": "a", "start": 3.0, "end": 3.1},
                 {"word": "wretch", "start": 3.1, "end": 3.5},
                 {"word": "like", "start": 3.5, "end": 3.7},
                 {"word": "me", "start": 3.7, "end": 4.0},
             ]},
        ],
        "beats": [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0],
        "bpm": 120.0,
        "duration": 10.0,
        "sections": [
            {"label": "intro", "start": 0.0, "end": 2.0},
            {"label": "verse", "start": 2.0, "end": 6.0},
            {"label": "outro", "start": 6.0, "end": 10.0},
        ],
        "mood_energy": "contemplative",
        "language": "en",
    }


@pytest.fixture
def sample_scene_plan():
    """Sample director output for testing downstream stages."""
    return {
        "overall_style": "contemplative",
        "color_palette": ["#1a1a2e", "#16213e", "#e2e2e2"],
        "subtitle_style": {
            "font_size": 48,
            "color": "#FFFFFF",
            "outline_color": "#000000",
            "position": "center-bottom",
            "animation": "fade",
        },
        "scenes": [
            {
                "section": "intro",
                "start": 0.0,
                "end": 2.0,
                "visual_prompt": "mountain sunrise golden light peaceful morning",
                "motion": "slow_zoom_in",
                "transition": "fade_black",
                "overlay": "none",
            },
            {
                "section": "verse",
                "start": 2.0,
                "end": 6.0,
                "visual_prompt": "calm water reflection forest lake serene",
                "motion": "slow_zoom_out",
                "transition": "crossfade",
                "overlay": "light_rays",
            },
            {
                "section": "outro",
                "start": 6.0,
                "end": 10.0,
                "visual_prompt": "sunset clouds golden horizon peaceful",
                "motion": "pan_left",
                "transition": "fade_black",
                "overlay": "particles",
            },
        ],
    }


@pytest.fixture
def tmp_output(tmp_path):
    """Temporary output directory for tests."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    tmp_dir = output_dir / "tmp"
    tmp_dir.mkdir()
    return output_dir
```

- [ ] **Step 9: Write tests/__init__.py**

```python
```

- [ ] **Step 10: Verify structure and commit**

```bash
python -c "import musicvid; print(musicvid.__version__)"
```

Expected: `0.1.0`

```bash
git add musicvid/ tests/ setup.py
git commit -m "feat: project scaffolding with package structure, deps, and test fixtures"
```

---

### Task 2: Audio Analyzer (Stage 1)

**Files:**
- Create: `musicvid/pipeline/audio_analyzer.py`
- Create: `tests/test_audio_analyzer.py`

- [ ] **Step 1: Write the failing test for analyze_audio return structure**

```python
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

        # Setup whisper mock
        mock_model = MagicMock()
        mock_model.transcribe.return_value = mock_whisper_result
        mock_whisper.load_model.return_value = mock_model

        # Setup librosa mock
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/s.rzytki/Documents/aiprojects/musicvideo && python -m pytest tests/test_audio_analyzer.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'musicvid.pipeline.audio_analyzer'`

- [ ] **Step 3: Write the audio_analyzer implementation**

```python
"""Stage 1: Audio analysis using Whisper and librosa."""

import json
from pathlib import Path

import whisper
import librosa
import numpy as np


def _detect_sections(y, sr, duration):
    """Detect song sections using onset strength and beat structure.

    Uses a simple energy-based segmentation: split the song into chunks
    based on significant changes in spectral energy.
    """
    hop_length = 512
    # Compute mel spectrogram energy over time
    S = librosa.feature.melspectrogram(y=y, sr=sr, hop_length=hop_length)
    energy = librosa.power_to_db(S).mean(axis=0)

    # Smooth energy curve
    kernel_size = int(sr * 2 / hop_length)  # 2-second window
    if kernel_size % 2 == 0:
        kernel_size += 1
    if kernel_size > len(energy):
        kernel_size = max(3, len(energy) // 2 * 2 + 1)

    smoothed = np.convolve(energy, np.ones(kernel_size) / kernel_size, mode="same")

    # Find significant changes (section boundaries)
    diff = np.abs(np.diff(smoothed))
    threshold = np.mean(diff) + np.std(diff)
    boundary_frames = np.where(diff > threshold)[0]

    # Convert frames to times
    boundary_times = librosa.frames_to_time(boundary_frames, sr=sr, hop_length=hop_length)

    # Filter boundaries that are too close together (min 4 seconds apart)
    filtered = [0.0]
    for t in boundary_times:
        if t - filtered[-1] >= 4.0:
            filtered.append(round(float(t), 2))
    filtered.append(round(float(duration), 2))

    # Assign labels based on position
    labels = ["intro"]
    num_sections = len(filtered) - 1
    if num_sections <= 1:
        labels = ["verse"]
    elif num_sections == 2:
        labels = ["verse", "outro"]
    elif num_sections == 3:
        labels = ["intro", "verse", "outro"]
    else:
        labels = ["intro"]
        for i in range(1, num_sections - 1):
            if i % 2 == 1:
                labels.append("verse")
            else:
                labels.append("chorus")
        labels.append("outro")

    sections = []
    for i in range(len(filtered) - 1):
        sections.append({
            "label": labels[i] if i < len(labels) else "verse",
            "start": filtered[i],
            "end": filtered[i + 1],
        })

    return sections


def _estimate_mood(tempo, energy_mean):
    """Estimate mood/energy from tempo and spectral energy."""
    if tempo < 80:
        return "contemplative"
    elif tempo < 110:
        return "worship"
    elif tempo < 140:
        return "joyful"
    else:
        return "powerful"


def analyze_audio(audio_path, output_dir=None, whisper_model="base"):
    """Analyze audio file and return structured analysis.

    Args:
        audio_path: Path to audio file (MP3, WAV, FLAC, M4A, OGG).
        output_dir: Optional directory to save analysis.json.
        whisper_model: Whisper model size ('base' or 'small').

    Returns:
        dict with keys: lyrics, beats, bpm, duration, sections, mood_energy, language
    """
    # Transcribe with Whisper
    model = whisper.load_model(whisper_model)
    transcription = model.transcribe(audio_path, word_timestamps=True)

    # Extract lyrics with word-level timestamps
    lyrics = []
    for segment in transcription.get("segments", []):
        words = []
        for w in segment.get("words", []):
            words.append({
                "word": w["word"].strip(),
                "start": round(float(w["start"]), 2),
                "end": round(float(w["end"]), 2),
            })
        lyrics.append({
            "start": round(float(segment["start"]), 2),
            "end": round(float(segment["end"]), 2),
            "text": segment["text"].strip(),
            "words": words,
        })

    language = transcription.get("language", "en")

    # Load audio for librosa analysis
    y, sr = librosa.load(audio_path)
    duration = float(librosa.get_duration(y=y, sr=sr))

    # Beat tracking
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
    beat_times = librosa.frames_to_time(beat_frames, sr=sr)
    beats = [round(float(b), 2) for b in beat_times]
    bpm = round(float(tempo), 1)

    # Section detection
    sections = _detect_sections(y, sr, duration)

    # Mood estimation
    S = librosa.feature.melspectrogram(y=y, sr=sr)
    energy_mean = float(np.mean(librosa.power_to_db(S)))
    mood_energy = _estimate_mood(bpm, energy_mean)

    result = {
        "lyrics": lyrics,
        "beats": beats,
        "bpm": bpm,
        "duration": round(duration, 2),
        "sections": sections,
        "mood_energy": mood_energy,
        "language": language,
    }

    # Save to output directory if provided
    if output_dir:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        with open(output_path / "analysis.json", "w") as f:
            json.dump(result, f, indent=2)

    return result
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/s.rzytki/Documents/aiprojects/musicvideo && python -m pytest tests/test_audio_analyzer.py -v
```

Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add musicvid/pipeline/audio_analyzer.py tests/test_audio_analyzer.py
git commit -m "feat: add audio analyzer with Whisper transcription and librosa beat detection"
```

---

### Task 3: Director (Stage 2)

**Files:**
- Create: `musicvid/pipeline/director.py`
- Create: `tests/test_director.py`

- [ ] **Step 1: Write the failing test for director**

```python
"""Tests for director module."""

import json
from unittest.mock import patch, MagicMock

import pytest

from musicvid.pipeline.director import create_scene_plan


class TestCreateScenePlan:
    """Tests for the create_scene_plan function."""

    @patch("musicvid.pipeline.director.anthropic")
    def test_returns_valid_scene_plan(self, mock_anthropic, sample_analysis):
        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = json.dumps({
            "overall_style": "contemplative",
            "color_palette": ["#1a1a2e", "#16213e", "#e2e2e2"],
            "subtitle_style": {
                "font_size": 48,
                "color": "#FFFFFF",
                "outline_color": "#000000",
                "position": "center-bottom",
                "animation": "fade",
            },
            "scenes": [
                {
                    "section": "intro",
                    "start": 0.0,
                    "end": 2.0,
                    "visual_prompt": "mountain sunrise golden light",
                    "motion": "slow_zoom_in",
                    "transition": "fade_black",
                    "overlay": "none",
                },
                {
                    "section": "verse",
                    "start": 2.0,
                    "end": 6.0,
                    "visual_prompt": "calm water reflection",
                    "motion": "slow_zoom_out",
                    "transition": "crossfade",
                    "overlay": "none",
                },
                {
                    "section": "outro",
                    "start": 6.0,
                    "end": 10.0,
                    "visual_prompt": "sunset clouds golden",
                    "motion": "pan_left",
                    "transition": "fade_black",
                    "overlay": "none",
                },
            ],
        })

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.Anthropic.return_value = mock_client

        result = create_scene_plan(sample_analysis)

        assert "overall_style" in result
        assert "color_palette" in result
        assert "subtitle_style" in result
        assert "scenes" in result
        assert len(result["scenes"]) > 0

    @patch("musicvid.pipeline.director.anthropic")
    def test_scenes_cover_full_duration(self, mock_anthropic, sample_analysis):
        scenes = [
            {
                "section": "intro", "start": 0.0, "end": 5.0,
                "visual_prompt": "test", "motion": "slow_zoom_in",
                "transition": "fade_black", "overlay": "none",
            },
            {
                "section": "verse", "start": 5.0, "end": 10.0,
                "visual_prompt": "test", "motion": "slow_zoom_out",
                "transition": "crossfade", "overlay": "none",
            },
        ]
        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = json.dumps({
            "overall_style": "contemplative",
            "color_palette": ["#aaa", "#bbb", "#ccc"],
            "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                               "position": "center-bottom", "animation": "fade"},
            "scenes": scenes,
        })

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.Anthropic.return_value = mock_client

        result = create_scene_plan(sample_analysis)

        assert result["scenes"][0]["start"] == 0.0
        assert result["scenes"][-1]["end"] == sample_analysis["duration"]

    @patch("musicvid.pipeline.director.anthropic")
    def test_respects_style_override(self, mock_anthropic, sample_analysis):
        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = json.dumps({
            "overall_style": "joyful",
            "color_palette": ["#aaa", "#bbb", "#ccc"],
            "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                               "position": "center-bottom", "animation": "fade"},
            "scenes": [{"section": "verse", "start": 0.0, "end": 10.0,
                         "visual_prompt": "test", "motion": "static",
                         "transition": "cut", "overlay": "none"}],
        })

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.Anthropic.return_value = mock_client

        result = create_scene_plan(sample_analysis, style_override="joyful")

        # Verify the API was called with the style override mentioned
        call_args = mock_client.messages.create.call_args
        user_message = call_args[1]["messages"][0]["content"]
        assert "joyful" in user_message

    @patch("musicvid.pipeline.director.anthropic")
    def test_saves_to_output_dir(self, mock_anthropic, sample_analysis, tmp_output):
        plan_data = {
            "overall_style": "contemplative",
            "color_palette": ["#aaa"],
            "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                               "position": "center-bottom", "animation": "fade"},
            "scenes": [{"section": "verse", "start": 0.0, "end": 10.0,
                         "visual_prompt": "test", "motion": "static",
                         "transition": "cut", "overlay": "none"}],
        }
        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = json.dumps(plan_data)

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.Anthropic.return_value = mock_client

        output_dir = str(tmp_output / "tmp")
        result = create_scene_plan(sample_analysis, output_dir=output_dir)

        import json as json_mod
        saved = json_mod.loads((tmp_output / "tmp" / "scene_plan.json").read_text())
        assert saved["overall_style"] == "contemplative"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/s.rzytki/Documents/aiprojects/musicvideo && python -m pytest tests/test_director.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write the director implementation**

```python
"""Stage 2: Scene direction using Claude API."""

import json
from pathlib import Path

import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential


PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def _load_system_prompt():
    """Load the director system prompt from file."""
    prompt_file = PROMPTS_DIR / "director_system.txt"
    return prompt_file.read_text()


def _build_user_message(analysis, style_override=None):
    """Build the user message for Claude with analysis data."""
    msg = f"Here is the audio analysis for the music video:\n\n{json.dumps(analysis, indent=2)}"
    if style_override and style_override != "auto":
        msg += f"\n\nIMPORTANT: Override the style to be '{style_override}' regardless of the mood detected in the audio."
    return msg


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=30))
def _call_claude(system_prompt, user_message):
    """Call Claude API with retry logic."""
    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    return response.content[0].text


def _validate_scene_plan(plan, duration):
    """Validate and fix the scene plan to ensure it covers the full duration."""
    if not plan.get("scenes"):
        raise ValueError("Scene plan has no scenes")

    # Sort scenes by start time
    plan["scenes"].sort(key=lambda s: s["start"])

    # Ensure first scene starts at 0
    plan["scenes"][0]["start"] = 0.0

    # Ensure last scene ends at duration
    plan["scenes"][-1]["end"] = duration

    return plan


def create_scene_plan(analysis, style_override=None, output_dir=None):
    """Create a scene plan using Claude API.

    Args:
        analysis: Audio analysis dict from Stage 1.
        style_override: Optional style override (contemplative/joyful/worship/powerful).
        output_dir: Optional directory to save scene_plan.json.

    Returns:
        dict with keys: overall_style, color_palette, subtitle_style, scenes
    """
    system_prompt = _load_system_prompt()
    user_message = _build_user_message(analysis, style_override)

    response_text = _call_claude(system_prompt, user_message)

    # Parse JSON (Claude might wrap in code fences)
    text = response_text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1])

    plan = json.loads(text)
    plan = _validate_scene_plan(plan, analysis["duration"])

    if output_dir:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        with open(output_path / "scene_plan.json", "w") as f:
            json.dump(plan, f, indent=2)

    return plan
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/s.rzytki/Documents/aiprojects/musicvideo && python -m pytest tests/test_director.py -v
```

Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add musicvid/pipeline/director.py tests/test_director.py musicvid/prompts/director_system.txt
git commit -m "feat: add director module for Claude-powered scene planning"
```

---

### Task 4: Stock Fetcher (Stage 3)

**Files:**
- Create: `musicvid/pipeline/stock_fetcher.py`
- Create: `tests/test_stock_fetcher.py`

- [ ] **Step 1: Write the failing test for stock_fetcher**

```python
"""Tests for stock_fetcher module."""

import json
from unittest.mock import patch, MagicMock
from pathlib import Path

import pytest

from musicvid.pipeline.stock_fetcher import fetch_videos, _build_search_query


class TestBuildSearchQuery:
    """Tests for search query building."""

    def test_uses_visual_prompt(self):
        scene = {
            "visual_prompt": "mountain sunrise golden light peaceful morning",
            "section": "intro",
        }
        query = _build_search_query(scene, "contemplative")
        assert "mountain" in query or "sunrise" in query

    def test_style_mapping_contemplative(self):
        scene = {"visual_prompt": "", "section": "verse"}
        query = _build_search_query(scene, "contemplative")
        assert len(query) > 0

    def test_style_mapping_joyful(self):
        scene = {"visual_prompt": "", "section": "verse"}
        query = _build_search_query(scene, "joyful")
        assert len(query) > 0


class TestFetchVideos:
    """Tests for the fetch_videos function."""

    @patch("musicvid.pipeline.stock_fetcher.requests")
    def test_returns_video_paths_per_scene(self, mock_requests, sample_scene_plan, tmp_output):
        # Mock successful Pexels API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "videos": [
                {
                    "id": 123,
                    "video_files": [
                        {"id": 1, "quality": "hd", "width": 1920, "height": 1080,
                         "link": "https://example.com/video.mp4"},
                    ],
                },
            ],
        }
        mock_response.content = b"fake video data"
        mock_response.iter_content = MagicMock(return_value=[b"fake video data"])
        mock_requests.get.return_value = mock_response

        output_dir = str(tmp_output / "tmp")
        result = fetch_videos(sample_scene_plan, output_dir=output_dir)

        assert len(result) == len(sample_scene_plan["scenes"])
        for entry in result:
            assert "scene_index" in entry
            assert "video_path" in entry
            assert "search_query" in entry

    @patch("musicvid.pipeline.stock_fetcher.requests")
    def test_saves_manifest(self, mock_requests, sample_scene_plan, tmp_output):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "videos": [
                {
                    "id": 456,
                    "video_files": [
                        {"id": 2, "quality": "hd", "width": 1920, "height": 1080,
                         "link": "https://example.com/v2.mp4"},
                    ],
                },
            ],
        }
        mock_response.content = b"fake video data"
        mock_response.iter_content = MagicMock(return_value=[b"fake video data"])
        mock_requests.get.return_value = mock_response

        output_dir = str(tmp_output / "tmp")
        result = fetch_videos(sample_scene_plan, output_dir=output_dir)

        manifest_path = tmp_output / "tmp" / "fetch_manifest.json"
        assert manifest_path.exists()

    @patch("musicvid.pipeline.stock_fetcher.requests")
    def test_handles_api_failure_gracefully(self, mock_requests, sample_scene_plan, tmp_output):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = Exception("API Error")
        mock_requests.get.return_value = mock_response

        output_dir = str(tmp_output / "tmp")
        # Should not raise, should provide placeholder/fallback
        result = fetch_videos(sample_scene_plan, output_dir=output_dir)

        assert len(result) == len(sample_scene_plan["scenes"])
        for entry in result:
            assert "video_path" in entry
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/s.rzytki/Documents/aiprojects/musicvideo && python -m pytest tests/test_stock_fetcher.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write the stock_fetcher implementation**

```python
"""Stage 3: Stock video fetching from Pexels API."""

import json
import os
from pathlib import Path

import requests
from tenacity import retry, stop_after_attempt, wait_exponential


STYLE_QUERIES = {
    "contemplative": ["mountain sunrise", "calm water reflection", "forest light"],
    "joyful": ["sunlight meadow", "golden fields", "bright sky clouds"],
    "worship": ["hands raised light", "crowd worship", "candles warm"],
    "powerful": ["storm clouds dramatic", "ocean waves", "mountain peak"],
}

PEXELS_API_URL = "https://api.pexels.com/videos/search"


def _build_search_query(scene, overall_style):
    """Build a Pexels search query from scene data.

    Uses the visual_prompt if available, otherwise falls back to style-based queries.
    """
    prompt = scene.get("visual_prompt", "").strip()
    if prompt:
        # Take the first few keywords from the visual prompt
        words = prompt.split()[:5]
        return " ".join(words)

    # Fallback to style-based queries
    queries = STYLE_QUERIES.get(overall_style, STYLE_QUERIES["contemplative"])
    section = scene.get("section", "verse")
    idx = hash(section) % len(queries)
    return queries[idx]


def _get_best_video_file(video_files, min_width=1280):
    """Select the best quality video file from Pexels response."""
    hd_files = [f for f in video_files if f.get("width", 0) >= min_width]
    if hd_files:
        return max(hd_files, key=lambda f: f.get("width", 0))
    return max(video_files, key=lambda f: f.get("width", 0)) if video_files else None


def _create_placeholder_video(output_path, scene):
    """Create a placeholder black frame when video fetch fails."""
    from PIL import Image
    img = Image.new("RGB", (1920, 1080), color=(20, 20, 40))
    placeholder_path = output_path.with_suffix(".png")
    img.save(str(placeholder_path))
    return str(placeholder_path)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=30))
def _search_pexels(query, api_key):
    """Search Pexels for videos matching the query."""
    headers = {"Authorization": api_key}
    params = {
        "query": query,
        "orientation": "landscape",
        "size": "large",
        "per_page": 3,
    }
    response = requests.get(PEXELS_API_URL, headers=headers, params=params)
    response.raise_for_status()
    return response.json()


def _download_video(url, output_path, api_key):
    """Download a video file from URL."""
    headers = {"Authorization": api_key}
    response = requests.get(url, headers=headers, stream=True)
    response.raise_for_status()
    with open(output_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    return str(output_path)


def fetch_videos(scene_plan, output_dir=None):
    """Fetch stock videos for each scene in the plan.

    Args:
        scene_plan: Scene plan dict from Stage 2.
        output_dir: Directory to save downloaded videos.

    Returns:
        list of dicts with keys: scene_index, video_path, search_query
    """
    api_key = os.environ.get("PEXELS_API_KEY", "")
    overall_style = scene_plan.get("overall_style", "contemplative")
    scenes = scene_plan.get("scenes", [])

    if output_dir:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        videos_dir = output_path / "videos"
        videos_dir.mkdir(exist_ok=True)
    else:
        videos_dir = Path(".")

    results = []

    for i, scene in enumerate(scenes):
        query = _build_search_query(scene, overall_style)
        video_path = None

        try:
            if api_key:
                search_result = _search_pexels(query, api_key)
                videos = search_result.get("videos", [])
                if videos:
                    video_data = videos[0]
                    video_file = _get_best_video_file(video_data.get("video_files", []))
                    if video_file:
                        dest = videos_dir / f"scene_{i:03d}.mp4"
                        video_path = _download_video(video_file["link"], dest, api_key)
        except Exception:
            pass

        if not video_path:
            # Create placeholder
            dest = videos_dir / f"scene_{i:03d}"
            video_path = _create_placeholder_video(dest, scene)

        results.append({
            "scene_index": i,
            "video_path": video_path,
            "search_query": query,
        })

    # Save manifest
    if output_dir:
        manifest_path = Path(output_dir) / "fetch_manifest.json"
        with open(manifest_path, "w") as f:
            json.dump(results, f, indent=2)

    return results
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/s.rzytki/Documents/aiprojects/musicvideo && python -m pytest tests/test_stock_fetcher.py -v
```

Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add musicvid/pipeline/stock_fetcher.py tests/test_stock_fetcher.py
git commit -m "feat: add stock fetcher with Pexels API integration and placeholders"
```

---

### Task 5: Assembler (Stage 4)

**Files:**
- Create: `musicvid/pipeline/assembler.py`
- Create: `tests/test_assembler.py`

- [ ] **Step 1: Write the failing test for assembler**

```python
"""Tests for assembler module."""

import json
from unittest.mock import patch, MagicMock, call
from pathlib import Path

import pytest
import numpy as np

from musicvid.pipeline.assembler import (
    assemble_video,
    _create_ken_burns_clip,
    _create_subtitle_clips,
    _get_resolution,
)


class TestGetResolution:
    """Tests for resolution mapping."""

    def test_720p(self):
        assert _get_resolution("720p") == (1280, 720)

    def test_1080p(self):
        assert _get_resolution("1080p") == (1920, 1080)

    def test_4k(self):
        assert _get_resolution("4k") == (3840, 2160)

    def test_default(self):
        assert _get_resolution("unknown") == (1920, 1080)


class TestCreateSubtitleClips:
    """Tests for subtitle clip generation."""

    def test_creates_clips_for_lyrics(self, sample_analysis, sample_scene_plan):
        subtitle_style = sample_scene_plan["subtitle_style"]
        clips = _create_subtitle_clips(
            sample_analysis["lyrics"],
            subtitle_style,
            (1920, 1080),
        )
        assert len(clips) == len(sample_analysis["lyrics"])

    def test_empty_lyrics(self, sample_scene_plan):
        subtitle_style = sample_scene_plan["subtitle_style"]
        clips = _create_subtitle_clips([], subtitle_style, (1920, 1080))
        assert len(clips) == 0


class TestAssembleVideo:
    """Tests for the main assemble_video function."""

    @patch("musicvid.pipeline.assembler.VideoFileClip")
    @patch("musicvid.pipeline.assembler.ImageClip")
    @patch("musicvid.pipeline.assembler.AudioFileClip")
    @patch("musicvid.pipeline.assembler.TextClip")
    @patch("musicvid.pipeline.assembler.CompositeVideoClip")
    @patch("musicvid.pipeline.assembler.concatenate_videoclips")
    def test_produces_output_file(
        self, mock_concat, mock_composite, mock_text, mock_audio,
        mock_image, mock_video, sample_analysis, sample_scene_plan, tmp_output
    ):
        # Setup mocks
        mock_clip = MagicMock()
        mock_clip.duration = 5.0
        mock_clip.size = (1920, 1080)
        mock_clip.w = 1920
        mock_clip.h = 1080
        mock_clip.resize.return_value = mock_clip
        mock_clip.subclip.return_value = mock_clip
        mock_clip.set_duration.return_value = mock_clip
        mock_clip.set_position.return_value = mock_clip
        mock_clip.set_start.return_value = mock_clip
        mock_clip.crossfadein.return_value = mock_clip
        mock_clip.crossfadeout.return_value = mock_clip
        mock_clip.fadein.return_value = mock_clip
        mock_clip.fadeout.return_value = mock_clip
        mock_clip.fl.return_value = mock_clip

        mock_video.return_value = mock_clip
        mock_image.return_value = mock_clip
        mock_audio.return_value = mock_clip
        mock_text.return_value = mock_clip
        mock_concat.return_value = mock_clip
        mock_composite.return_value = mock_clip

        fetch_manifest = [
            {"scene_index": 0, "video_path": "/fake/scene_000.mp4", "search_query": "test"},
            {"scene_index": 1, "video_path": "/fake/scene_001.mp4", "search_query": "test"},
            {"scene_index": 2, "video_path": "/fake/scene_002.png", "search_query": "test"},
        ]

        output_file = str(tmp_output / "output.mp4")

        assemble_video(
            analysis=sample_analysis,
            scene_plan=sample_scene_plan,
            fetch_manifest=fetch_manifest,
            audio_path="/fake/audio.mp3",
            output_path=output_file,
            resolution="1080p",
        )

        # Verify write_videofile was called
        mock_clip.write_videofile.assert_called_once()
        call_kwargs = mock_clip.write_videofile.call_args
        assert output_file in call_kwargs[0] or call_kwargs[1].get("filename") == output_file or output_file in str(call_kwargs)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/s.rzytki/Documents/aiprojects/musicvideo && python -m pytest tests/test_assembler.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write the assembler implementation**

```python
"""Stage 4: Video assembly using MoviePy + FFmpeg."""

import json
from pathlib import Path

from moviepy.editor import (
    VideoFileClip,
    ImageClip,
    AudioFileClip,
    TextClip,
    CompositeVideoClip,
    concatenate_videoclips,
)


RESOLUTION_MAP = {
    "720p": (1280, 720),
    "1080p": (1920, 1080),
    "4k": (3840, 2160),
}


def _get_resolution(resolution_str):
    """Map resolution string to (width, height) tuple."""
    return RESOLUTION_MAP.get(resolution_str, (1920, 1080))


def _create_ken_burns_clip(clip, duration, motion="slow_zoom_in", target_size=(1920, 1080)):
    """Apply Ken Burns effect (zoom/pan) to a clip.

    Args:
        clip: MoviePy clip (video or image).
        duration: Desired duration in seconds.
        motion: One of slow_zoom_in, slow_zoom_out, pan_left, pan_right, static.
        target_size: Output resolution (width, height).
    """
    w, h = target_size
    clip = clip.resize(newsize=(int(w * 1.15), int(h * 1.15)))
    clip = clip.set_duration(duration)

    if motion == "slow_zoom_in":
        def zoom_in(get_frame, t):
            progress = t / duration
            scale = 1.0 + 0.15 * progress
            frame = get_frame(t)
            fh, fw = frame.shape[:2]
            new_w, new_h = int(fw / scale), int(fh / scale)
            x = (fw - new_w) // 2
            y = (fh - new_h) // 2
            cropped = frame[y:y + new_h, x:x + new_w]
            from PIL import Image
            import numpy as np
            img = Image.fromarray(cropped).resize((w, h), Image.LANCZOS)
            return np.array(img)
        return clip.fl(zoom_in)

    elif motion == "slow_zoom_out":
        def zoom_out(get_frame, t):
            progress = t / duration
            scale = 1.15 - 0.15 * progress
            frame = get_frame(t)
            fh, fw = frame.shape[:2]
            new_w, new_h = int(fw / scale), int(fh / scale)
            x = (fw - new_w) // 2
            y = (fh - new_h) // 2
            cropped = frame[y:y + new_h, x:x + new_w]
            from PIL import Image
            import numpy as np
            img = Image.fromarray(cropped).resize((w, h), Image.LANCZOS)
            return np.array(img)
        return clip.fl(zoom_out)

    elif motion == "pan_left":
        def pan_l(get_frame, t):
            progress = t / duration
            frame = get_frame(t)
            fh, fw = frame.shape[:2]
            max_offset = fw - w
            x = int(max_offset * (1 - progress))
            cropped = frame[0:h, x:x + w]
            return cropped
        return clip.fl(pan_l)

    elif motion == "pan_right":
        def pan_r(get_frame, t):
            progress = t / duration
            frame = get_frame(t)
            fh, fw = frame.shape[:2]
            max_offset = fw - w
            x = int(max_offset * progress)
            cropped = frame[0:h, x:x + w]
            return cropped
        return clip.fl(pan_r)

    else:  # static
        clip = clip.resize(newsize=(w, h))
        clip = clip.set_duration(duration)
        return clip


def _create_subtitle_clips(lyrics, subtitle_style, size):
    """Create subtitle TextClips from lyrics with word-level timing.

    Args:
        lyrics: List of lyric segments with start/end/text.
        subtitle_style: Dict with font_size, color, outline_color, position, animation.
        size: Tuple (width, height) for positioning.

    Returns:
        List of TextClip objects.
    """
    clips = []
    font_size = subtitle_style.get("font_size", 48)
    color = subtitle_style.get("color", "#FFFFFF")
    outline_color = subtitle_style.get("outline_color", "#000000")
    margin_bottom = 80

    for segment in lyrics:
        duration = segment["end"] - segment["start"]
        if duration <= 0:
            continue

        txt_clip = TextClip(
            segment["text"],
            fontsize=font_size,
            color=color,
            stroke_color=outline_color,
            stroke_width=2,
            font="Arial-Bold",
            method="caption",
            size=(size[0] - 100, None),
        )
        txt_clip = txt_clip.set_duration(duration)
        txt_clip = txt_clip.set_start(segment["start"])
        txt_clip = txt_clip.set_position(("center", size[1] - margin_bottom - font_size))

        # Apply fade animation
        fade_duration = min(0.3, duration / 3)
        txt_clip = txt_clip.crossfadein(fade_duration).crossfadeout(fade_duration)

        clips.append(txt_clip)

    return clips


def _load_scene_clip(video_path, scene, target_size):
    """Load a video or image clip for a scene."""
    path = Path(video_path)
    duration = scene["end"] - scene["start"]

    if path.suffix.lower() in (".png", ".jpg", ".jpeg", ".bmp"):
        clip = ImageClip(str(path))
    else:
        clip = VideoFileClip(str(path))
        if clip.duration < duration:
            # Loop video if shorter than needed
            loops = int(duration / clip.duration) + 1
            clip = concatenate_videoclips([clip] * loops)
        clip = clip.subclip(0, duration)

    return _create_ken_burns_clip(clip, duration, scene.get("motion", "static"), target_size)


def assemble_video(analysis, scene_plan, fetch_manifest, audio_path, output_path, resolution="1080p"):
    """Assemble the final music video.

    Args:
        analysis: Audio analysis dict from Stage 1.
        scene_plan: Scene plan dict from Stage 2.
        fetch_manifest: List of dicts with scene_index, video_path, search_query.
        audio_path: Path to the original audio file.
        output_path: Path for the output MP4 file.
        resolution: Output resolution string (720p, 1080p, 4k).
    """
    target_size = _get_resolution(resolution)
    scenes = scene_plan["scenes"]

    # Build scene clips
    scene_clips = []
    for manifest_entry in fetch_manifest:
        idx = manifest_entry["scene_index"]
        scene = scenes[idx]
        clip = _load_scene_clip(manifest_entry["video_path"], scene, target_size)
        scene_clips.append(clip)

    # Concatenate scene clips
    video = concatenate_videoclips(scene_clips, method="compose")

    # Add subtitles
    subtitle_clips = _create_subtitle_clips(
        analysis.get("lyrics", []),
        scene_plan.get("subtitle_style", {}),
        target_size,
    )

    # Composite video with subtitles
    final = CompositeVideoClip([video] + subtitle_clips, size=target_size)

    # Add audio
    audio = AudioFileClip(audio_path)
    final = final.set_audio(audio)
    final = final.set_duration(min(final.duration, audio.duration))

    # Export
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    final.write_videofile(
        output_path,
        codec="libx264",
        audio_codec="aac",
        bitrate="8000k",
        fps=30,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/s.rzytki/Documents/aiprojects/musicvideo && python -m pytest tests/test_assembler.py -v
```

Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add musicvid/pipeline/assembler.py tests/test_assembler.py
git commit -m "feat: add video assembler with Ken Burns effects and subtitles"
```

---

### Task 6: CLI Entry Point

**Files:**
- Create: `musicvid/musicvid.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test for CLI**

```python
"""Tests for the CLI entry point."""

import json
from unittest.mock import patch, MagicMock
from pathlib import Path

import pytest
from click.testing import CliRunner

from musicvid.musicvid import cli


@pytest.fixture
def runner():
    return CliRunner()


class TestCLI:
    """Tests for the Click CLI."""

    def test_help_shows_usage(self, runner):
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "audio_file" in result.output.lower() or "AUDIO_FILE" in result.output

    def test_missing_audio_file(self, runner):
        result = runner.invoke(cli, [])
        assert result.exit_code != 0

    def test_invalid_audio_file(self, runner, tmp_path):
        result = runner.invoke(cli, [str(tmp_path / "nonexistent.mp3")])
        assert result.exit_code != 0

    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.fetch_videos")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    def test_full_pipeline_integration(
        self, mock_analyze, mock_direct, mock_fetch, mock_assemble, runner, tmp_path
    ):
        # Create a fake audio file
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")

        # Mock stage outputs
        mock_analyze.return_value = {
            "lyrics": [], "beats": [0.0, 0.5], "bpm": 120.0,
            "duration": 10.0, "sections": [{"label": "verse", "start": 0.0, "end": 10.0}],
            "mood_energy": "contemplative", "language": "en",
        }
        mock_direct.return_value = {
            "overall_style": "contemplative",
            "color_palette": ["#aaa"],
            "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                               "position": "center-bottom", "animation": "fade"},
            "scenes": [{"section": "verse", "start": 0.0, "end": 10.0,
                         "visual_prompt": "test", "motion": "static",
                         "transition": "cut", "overlay": "none"}],
        }
        mock_fetch.return_value = [
            {"scene_index": 0, "video_path": "/fake/v.mp4", "search_query": "test"},
        ]

        output_dir = tmp_path / "output"
        result = runner.invoke(cli, [
            str(audio_file),
            "--output", str(output_dir),
            "--mode", "stock",
            "--style", "auto",
            "--resolution", "1080p",
        ])

        assert result.exit_code == 0
        mock_analyze.assert_called_once()
        mock_direct.assert_called_once()
        mock_fetch.assert_called_once()
        mock_assemble.assert_called_once()

    def test_mode_option_values(self, runner, tmp_path):
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake")
        for mode in ["stock", "ai", "hybrid"]:
            result = runner.invoke(cli, [str(audio_file), "--mode", mode, "--help"])
            # --help should work regardless
            assert result.exit_code == 0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/s.rzytki/Documents/aiprojects/musicvideo && python -m pytest tests/test_cli.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write the CLI implementation**

```python
"""MusicVid CLI — Christian Music Video Generator."""

import json
import sys
from pathlib import Path

import click
from dotenv import load_dotenv

from musicvid.pipeline.audio_analyzer import analyze_audio
from musicvid.pipeline.director import create_scene_plan
from musicvid.pipeline.stock_fetcher import fetch_videos
from musicvid.pipeline.assembler import assemble_video


load_dotenv()


@click.command()
@click.argument("audio_file", type=click.Path(exists=True))
@click.option("--mode", type=click.Choice(["stock", "ai", "hybrid"]), default="stock", help="Video source mode.")
@click.option("--style", type=click.Choice(["auto", "contemplative", "joyful", "worship", "powerful"]), default="auto", help="Visual style.")
@click.option("--output", type=click.Path(), default="./output/", help="Output directory.")
@click.option("--resolution", type=click.Choice(["720p", "1080p", "4k"]), default="1080p", help="Output resolution.")
@click.option("--lang", default="auto", help="Language for transcription.")
def cli(audio_file, mode, style, output, resolution, lang):
    """Generate a music video from AUDIO_FILE."""
    audio_path = Path(audio_file).resolve()
    output_dir = Path(output).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir = output_dir / "tmp"
    tmp_dir.mkdir(exist_ok=True)

    # Stage 1: Analyze Audio
    click.echo("[1/4] Analyzing audio...")
    analysis = analyze_audio(str(audio_path), output_dir=str(tmp_dir))
    click.echo(f"  BPM: {analysis['bpm']}, Duration: {analysis['duration']}s, "
               f"Sections: {len(analysis['sections'])}, Mood: {analysis['mood_energy']}")

    # Stage 2: Direct Scenes
    click.echo("[2/4] Creating scene plan...")
    style_override = style if style != "auto" else None
    scene_plan = create_scene_plan(analysis, style_override=style_override, output_dir=str(tmp_dir))
    click.echo(f"  Style: {scene_plan['overall_style']}, Scenes: {len(scene_plan['scenes'])}")

    # Stage 3: Fetch Videos
    click.echo("[3/4] Fetching stock videos...")
    fetch_manifest = fetch_videos(scene_plan, output_dir=str(tmp_dir))
    fetched = sum(1 for f in fetch_manifest if f["video_path"].endswith(".mp4"))
    click.echo(f"  Fetched: {fetched}/{len(fetch_manifest)} videos")

    # Stage 4: Assemble Video
    click.echo("[4/4] Assembling video...")
    output_filename = audio_path.stem + "_musicvideo.mp4"
    output_path = str(output_dir / output_filename)
    assemble_video(
        analysis=analysis,
        scene_plan=scene_plan,
        fetch_manifest=fetch_manifest,
        audio_path=str(audio_path),
        output_path=output_path,
        resolution=resolution,
    )
    click.echo(f"  Done! Output: {output_path}")


if __name__ == "__main__":
    cli()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/s.rzytki/Documents/aiprojects/musicvideo && python -m pytest tests/test_cli.py -v
```

Expected: All 5 tests PASS

- [ ] **Step 5: Run full test suite**

```bash
cd /Users/s.rzytki/Documents/aiprojects/musicvideo && python -m pytest tests/ -v
```

Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add musicvid/musicvid.py tests/test_cli.py
git commit -m "feat: add Click CLI entry point with 4-stage pipeline orchestration"
```

---

### Task 7: Integration & Final Polish

**Files:**
- Modify: `musicvid/.env.example`
- Modify: `.gitignore`

- [ ] **Step 1: Update .gitignore**

Add to `.gitignore`:
```
output/
*.mp4
*.pyc
__pycache__/
.env
*.egg-info/
dist/
build/
.eggs/
```

- [ ] **Step 2: Verify the full package imports correctly**

```bash
cd /Users/s.rzytki/Documents/aiprojects/musicvideo && python -c "
from musicvid.pipeline.audio_analyzer import analyze_audio
from musicvid.pipeline.director import create_scene_plan
from musicvid.pipeline.stock_fetcher import fetch_videos
from musicvid.pipeline.assembler import assemble_video
from musicvid.musicvid import cli
print('All imports OK')
"
```

Expected: `All imports OK`

- [ ] **Step 3: Run full test suite one final time**

```bash
cd /Users/s.rzytki/Documents/aiprojects/musicvideo && python -m pytest tests/ -v --tb=short
```

Expected: All tests PASS

- [ ] **Step 4: Final commit**

```bash
git add .gitignore musicvid/.env.example
git commit -m "chore: update gitignore and finalize project structure"
```
