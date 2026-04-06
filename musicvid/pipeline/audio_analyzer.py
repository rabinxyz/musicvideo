"""Stage 1: Audio analysis using Whisper and librosa."""

import json
from pathlib import Path

import whisper
import librosa
import numpy as np


def _detect_sections(y, sr, duration):
    """Detect song sections using onset strength and beat structure."""
    hop_length = 512
    try:
        S = librosa.feature.melspectrogram(y=y, sr=sr, hop_length=hop_length)
        energy = np.asarray(librosa.power_to_db(S).mean(axis=0), dtype=float)
    except Exception:
        return [{"label": "verse", "start": 0.0, "end": round(float(duration), 2)}]

    if len(energy) == 0:
        return [{"label": "verse", "start": 0.0, "end": round(float(duration), 2)}]

    kernel_size = int(sr * 2 / hop_length)
    if kernel_size % 2 == 0:
        kernel_size += 1
    if kernel_size > len(energy):
        kernel_size = max(3, len(energy) // 2 * 2 + 1)

    smoothed = np.convolve(energy, np.ones(kernel_size) / kernel_size, mode="same")

    diff = np.abs(np.diff(smoothed))
    threshold = np.mean(diff) + np.std(diff)
    boundary_frames = np.where(diff > threshold)[0]

    boundary_times = librosa.frames_to_time(boundary_frames, sr=sr, hop_length=hop_length)

    filtered = [0.0]
    for t in boundary_times:
        if t - filtered[-1] >= 4.0:
            filtered.append(round(float(t), 2))
    filtered.append(round(float(duration), 2))

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


def analyze_audio(audio_path, output_dir=None, whisper_model="small"):
    """Analyze audio file and return structured analysis.

    Args:
        audio_path: Path to audio file (MP3, WAV, FLAC, M4A, OGG).
        output_dir: Optional directory to save analysis.json.
        whisper_model: Whisper model size ('base' or 'small').

    Returns:
        dict with keys: lyrics, beats, bpm, duration, sections, mood_energy, language
    """
    model = whisper.load_model(whisper_model)
    transcription = model.transcribe(
        audio_path,
        word_timestamps=True,
        language="pl",
        initial_prompt="Polska pieśń chrześcijańska. Słowa: tylko, Bogu, zbawienie, Pan, dusza, serce, chwała.",
        temperature=0.0,
        condition_on_previous_text=True,
    )

    lyrics = []
    for segment in transcription.get("segments", []):
        text = segment["text"].strip()
        if not text:
            continue
        if len(text) < 2:
            continue
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
            "text": text,
            "words": words,
        })

    language = transcription.get("language", "en")

    y, sr = librosa.load(audio_path)
    duration = float(librosa.get_duration(y=y, sr=sr))

    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
    beat_times = librosa.frames_to_time(beat_frames, sr=sr)
    beats = [round(float(b), 2) for b in beat_times]
    bpm = round(float(tempo[0] if hasattr(tempo, '__len__') else tempo), 1)
    sections = _detect_sections(y, sr, duration)

    S = librosa.feature.melspectrogram(y=y, sr=sr)
    energy_mean = float(np.mean(librosa.power_to_db(S)))
    mood_energy = _estimate_mood(bpm, energy_mean)

    # Energy peaks: onset strength peaks (used by WOW effects for cut timing)
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    raw_peaks = librosa.util.peak_pick(
        onset_env, pre_max=3, post_max=3,
        pre_avg=3, post_avg=5, delta=0.5, wait=10
    )
    peak_times = librosa.frames_to_time(raw_peaks, sr=sr)
    energy_peaks = [round(float(t), 2) for t in peak_times]

    result = {
        "lyrics": lyrics,
        "beats": beats,
        "bpm": bpm,
        "duration": round(duration, 2),
        "sections": sections,
        "mood_energy": mood_energy,
        "language": language,
        "energy_peaks": energy_peaks,
    }

    if output_dir:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        with open(output_path / "analysis.json", "w") as f:
            json.dump(result, f, indent=2)

    return result
