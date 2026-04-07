# Fix Director Prompt Size Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Trim `analysis` before sending to Claude in `_build_user_message()` so the prompt stays under 50 000 tokens, eliminating `BadRequestError 400 prompt too long`.

**Architecture:** Add a filtering step at the top of `_build_user_message()` that copies `analysis` without `energy_curve`, downsamples `beats` to ≤100 values, caps `energy_peaks` at 20, and caps `lyrics` at 50 segments. All other data and the rest of the function is untouched.

**Tech Stack:** Python 3.11+, existing `musicvid/pipeline/director.py`, `tests/test_director.py`, `pytest`.

---

### Task 1: Filter heavy fields in `_build_user_message()`

**Files:**
- Modify: `musicvid/pipeline/director.py:19-74` (function `_build_user_message`)
- Test: `tests/test_director.py`

- [ ] **Step 1: Write the failing tests**

Add these four tests at the bottom of `tests/test_director.py`:

```python
class TestBuildUserMessageFiltering:
    """energy_curve and large lists are trimmed before sending to Claude."""

    def _base_analysis(self):
        return {
            "duration": 300.0,
            "bpm": 120.0,
            "beats": [i * 0.5 for i in range(500)],        # 500 beats
            "energy_curve": [[i * 0.1, i * 0.01] for i in range(25800)],  # huge
            "energy_peaks": [i * 1.0 for i in range(50)],  # 50 peaks
            "lyrics": [{"start": i, "end": i + 1, "text": f"word {i}"} for i in range(100)],
            "sections": [],
            "mood_energy": "medium",
        }

    def test_energy_curve_excluded(self):
        msg = _build_user_message(self._base_analysis())
        assert "energy_curve" not in msg

    def test_beats_capped_at_100(self):
        msg = _build_user_message(self._base_analysis())
        data = json.loads(msg.split("Here is the audio analysis")[1].split("\n\nBPM:")[0].lstrip("for the music video:\n\n"))
        assert len(data["beats"]) <= 100

    def test_energy_peaks_capped_at_20(self):
        msg = _build_user_message(self._base_analysis())
        data = json.loads(msg.split("Here is the audio analysis")[1].split("\n\nBPM:")[0].lstrip("for the music video:\n\n"))
        assert len(data["energy_peaks"]) <= 20

    def test_lyrics_capped_at_50(self):
        msg = _build_user_message(self._base_analysis())
        data = json.loads(msg.split("Here is the audio analysis")[1].split("\n\nBPM:")[0].lstrip("for the music video:\n\n"))
        assert len(data["lyrics"]) <= 50
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/s.rzytki/Documents/aiprojects/musicvideo
python3 -m pytest tests/test_director.py::TestBuildUserMessageFiltering -v
```

Expected: 3–4 FAILs (energy_curve currently included, beats/peaks/lyrics not trimmed).

- [ ] **Step 3: Implement the fix in `_build_user_message()`**

Replace the opening of the function in `musicvid/pipeline/director.py`. The current line 32:

```python
    msg = f"Here is the audio analysis for the music video:\n\n{json.dumps(analysis, indent=2)}"
```

should become:

```python
    # Strip heavy fields not needed by the director for scene planning
    analysis_for_director = {k: v for k, v in analysis.items() if k != "energy_curve"}

    beats_full = analysis_for_director.get("beats", [])
    if len(beats_full) > 100:
        step = len(beats_full) // 100
        analysis_for_director["beats"] = beats_full[::step][:100]

    peaks = analysis_for_director.get("energy_peaks", [])
    if len(peaks) > 20:
        analysis_for_director["energy_peaks"] = peaks[:20]

    lyrics = analysis_for_director.get("lyrics", [])
    if len(lyrics) > 50:
        analysis_for_director["lyrics"] = lyrics[:50]

    msg = f"Here is the audio analysis for the music video:\n\n{json.dumps(analysis_for_director, indent=2)}"
```

**Important:** The `beats` variable on line 23 (`beats = analysis.get("beats", [])`) must remain reading from the original `analysis`, not `analysis_for_director`, so that `downbeats_preview` still uses all beats for accurate downbeat timestamps.

Full updated function (lines 19–74 of `director.py`):

```python
def _build_user_message(analysis, style_override=None, mode=None):
    """Build the user message for Claude with analysis data."""
    duration = analysis.get("duration", 0)
    bpm = analysis.get("bpm", 120.0)
    beats = analysis.get("beats", [])

    bar_duration = 4 * (60.0 / bpm)
    suggested_scene_count = max(4, int(duration / (bar_duration * 4)))

    # Downbeats: every 4th beat starting from index 0
    downbeats = beats[::4] if beats else []
    downbeats_preview = [round(d, 2) for d in downbeats[:20]]

    # Strip heavy fields not needed by the director for scene planning
    analysis_for_director = {k: v for k, v in analysis.items() if k != "energy_curve"}

    beats_full = analysis_for_director.get("beats", [])
    if len(beats_full) > 100:
        step = len(beats_full) // 100
        analysis_for_director["beats"] = beats_full[::step][:100]

    peaks = analysis_for_director.get("energy_peaks", [])
    if len(peaks) > 20:
        analysis_for_director["energy_peaks"] = peaks[:20]

    lyrics = analysis_for_director.get("lyrics", [])
    if len(lyrics) > 50:
        analysis_for_director["lyrics"] = lyrics[:50]

    msg = f"Here is the audio analysis for the music video:\n\n{json.dumps(analysis_for_director, indent=2)}"
    msg += f"\n\nBPM: {bpm:.0f}"
    msg += f"\nBar duration (4 beats): {bar_duration:.2f}s"
    msg += f"\nOptimal scene duration (4 bars): {bar_duration * 4:.2f}s"
    msg += f"\nSuggested scene count for this song: {suggested_scene_count}"
    msg += f"\nDownbeats (every 4th beat, first 20): {downbeats_preview}"
    msg += f"\n\nSCENE LENGTH RULES:"
    msg += f"\n- Minimum scene: 2 bars = {bar_duration * 2:.2f}s"
    msg += f"\n- Optimal scene: 4 bars = {bar_duration * 4:.2f}s"
    msg += f"\n- Maximum scene: 8 bars = {bar_duration * 8:.2f}s"
    msg += f"\n- Target: {suggested_scene_count} scenes of ~{bar_duration * 4:.1f}s each"
    msg += f"\n- Each scene start/end should align with a downbeat from the list above"
    msg += f"\n\nGenerate approximately {suggested_scene_count} scenes (maximum {suggested_scene_count + 4})."

    # Section-based length guidance
    bar_duration_val = bar_duration
    section_lengths = {
        "intro":  (6 * bar_duration_val, 8 * bar_duration_val),
        "verse":  (4 * bar_duration_val, 6 * bar_duration_val),
        "chorus": (2 * bar_duration_val, 3 * bar_duration_val),
        "bridge": (4 * bar_duration_val, 8 * bar_duration_val),
        "outro":  (6 * bar_duration_val, 10 * bar_duration_val),
    }
    msg += f"\n\nDŁUGOŚCI SCEN (KRYTYCZNE — stosuj się dokładnie):"
    msg += f"\nBPM={bpm:.0f}, jeden takt = {bar_duration_val:.2f}s"
    msg += f"\n- intro:  {section_lengths['intro'][0]:.1f}s - {section_lengths['intro'][1]:.1f}s"
    msg += f"\n- verse:  {section_lengths['verse'][0]:.1f}s - {section_lengths['verse'][1]:.1f}s"
    msg += f"\n- chorus: {section_lengths['chorus'][0]:.1f}s - {section_lengths['chorus'][1]:.1f}s (KRÓTKIE = ENERGIA)"
    msg += f"\n- bridge: {section_lengths['bridge'][0]:.1f}s - {section_lengths['bridge'][1]:.1f}s"
    msg += f"\n- outro:  {section_lengths['outro'][0]:.1f}s - {section_lengths['outro'][1]:.1f}s"
    msg += f"\nNIE rób równych odcinków. Refren MUSI być krótszy niż zwrotka."

    if style_override and style_override != "auto":
        msg += f"\n\nIMPORTANT: Override the style to be '{style_override}' regardless of the mood detected in the audio."

    if mode == "runway":
        msg += (
            "\n\nMODE: runway — Use TYPE_VIDEO_RUNWAY for climactic scenes (chorus, bridge). "
            "Use TYPE_VIDEO_STOCK for intro, verse, outro. "
            "Minimum 40% of scenes must be TYPE_VIDEO_RUNWAY. "
            "TYPE_AI is NOT available in this mode — do not use it."
        )
    return msg
```

- [ ] **Step 4: Run the new tests to verify they pass**

```bash
python3 -m pytest tests/test_director.py::TestBuildUserMessageFiltering -v
```

Expected: 4 PASSED.

- [ ] **Step 5: Run the full director test suite**

```bash
python3 -m pytest tests/test_director.py -v
```

Expected: all existing tests still pass (no regressions).

- [ ] **Step 6: Commit**

```bash
git add musicvid/pipeline/director.py tests/test_director.py
git commit -m "fix: trim energy_curve/beats/lyrics from director prompt to stay under token limit"
```
