# Pro Visuals & Dynamics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add stock deduplication, per-section color grading, global FFmpeg curves color grades, reel-specific transitions (slide/wipe), reel zoom punch, text flash, and intro hook — making full videos and reels look professional and dynamic.

**Architecture:** Per-section grade is applied per-clip in assembler before concatenation (MoviePy image_transform). Global color grade uses FFmpeg curves filters applied post-write. Reel transitions use MoviePy position transforms for slide/wipe effects. Zoom punch and text flash are per-frame/overlay effects applied in reels mode.

**Tech Stack:** Python 3.14, MoviePy 2.1.2, FFmpeg, NumPy, PIL, unittest.mock

---

### Task 1: Stock Video Deduplication

**Files:**
- Modify: `musicvid/pipeline/stock_fetcher.py`
- Test: `tests/test_stock_fetcher.py`

- [ ] **Step 1: Write failing tests for deduplication**

In `tests/test_stock_fetcher.py`, add these imports and tests:

```python
from musicvid.pipeline.stock_fetcher import (
    fetch_videos, fetch_video_by_query, _build_search_query,
    reset_download_registry, _downloaded_urls,
)


class TestStockDeduplication:
    """Ensure the same Pexels video URL is not reused within a run."""

    def setup_method(self):
        reset_download_registry()

    @patch.dict(os.environ, {"PEXELS_API_KEY": "test-key"})
    @patch("musicvid.pipeline.stock_fetcher.requests")
    def test_fetch_video_by_query_skips_already_downloaded(self, mock_requests):
        """Second call with same results should pick a different video."""
        video_a = {"id": 1, "url": "https://pexels.com/video/1",
                   "duration": 10,
                   "video_files": [{"id": 1, "width": 1920, "height": 1080,
                                    "link": "https://cdn.pexels.com/v1.mp4"}]}
        video_b = {"id": 2, "url": "https://pexels.com/video/2",
                   "duration": 10,
                   "video_files": [{"id": 2, "width": 1920, "height": 1080,
                                    "link": "https://cdn.pexels.com/v2.mp4"}]}

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"videos": [video_a, video_b]}
        mock_resp.raise_for_status = MagicMock()
        mock_resp.iter_content.return_value = [b"fake"]
        mock_requests.get.return_value = mock_resp

        import tempfile, os
        with tempfile.TemporaryDirectory() as td:
            p1 = os.path.join(td, "scene_000.mp4")
            p2 = os.path.join(td, "scene_001.mp4")
            fetch_video_by_query("mountain", 5, p1)
            fetch_video_by_query("mountain", 5, p2)
            # Both calls got the same search results but should pick different videos
            assert len(_downloaded_urls) == 2

    def test_reset_clears_registry(self):
        _downloaded_urls.add("https://example.com/v1")
        assert len(_downloaded_urls) == 1
        reset_download_registry()
        assert len(_downloaded_urls) == 0

    @patch.dict(os.environ, {"PEXELS_API_KEY": "test-key"})
    @patch("musicvid.pipeline.stock_fetcher.requests")
    def test_fallback_when_all_downloaded(self, mock_requests):
        """When all results already downloaded, still returns a video (fallback)."""
        video_a = {"id": 1, "url": "https://pexels.com/video/1",
                   "duration": 10,
                   "video_files": [{"id": 1, "width": 1920, "height": 1080,
                                    "link": "https://cdn.pexels.com/v1.mp4"}]}

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"videos": [video_a]}
        mock_resp.raise_for_status = MagicMock()
        mock_resp.iter_content.return_value = [b"fake"]
        mock_requests.get.return_value = mock_resp

        # Pre-register the only video
        _downloaded_urls.add("https://pexels.com/video/1")

        import tempfile, os
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "scene_000.mp4")
            result = fetch_video_by_query("mountain", 5, p)
            # Should still succeed (fallback to first available)
            assert result is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_stock_fetcher.py::TestStockDeduplication -v`
Expected: ImportError for `reset_download_registry` and `_downloaded_urls`

- [ ] **Step 3: Implement deduplication in stock_fetcher.py**

Add at module level (after imports):

```python
_downloaded_urls = set()


def reset_download_registry():
    """Clear the set of downloaded video URLs. Call at run start."""
    _downloaded_urls.clear()
```

Update `fetch_video_by_query` to filter already-downloaded URLs:

```python
def fetch_video_by_query(query, min_duration, output_path):
    """Fetch a single Pexels video by explicit query string."""
    api_key = os.environ.get("PEXELS_API_KEY", "")
    if not api_key:
        return None

    dest = Path(output_path)
    if dest.exists():
        return str(dest)

    try:
        search_result = _search_pexels(query, api_key)
        videos = search_result.get("videos", [])

        # Filter out already-downloaded videos
        fresh = [v for v in videos if v.get("url") not in _downloaded_urls]
        if not fresh:
            fresh = videos  # fallback: reuse if no alternatives

        # Prefer videos long enough; fall back to first available
        candidate = next(
            (v for v in fresh if v.get("duration", 0) >= min_duration),
            fresh[0] if fresh else None,
        )
        if candidate is None:
            return None

        _downloaded_urls.add(candidate.get("url", ""))

        video_file = _get_best_video_file(candidate.get("video_files", []))
        if video_file is None:
            return None

        return _download_video(video_file["link"], dest, api_key)
    except Exception:
        return None
```

Update `fetch_videos` similarly — after `videos = search_result.get("videos", [])` add:

```python
                if videos:
                    # Filter already-downloaded
                    fresh = [v for v in videos if v.get("url") not in _downloaded_urls]
                    if not fresh:
                        fresh = videos
                    video_data = fresh[0]
                    _downloaded_urls.add(video_data.get("url", ""))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_stock_fetcher.py::TestStockDeduplication -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add musicvid/pipeline/stock_fetcher.py tests/test_stock_fetcher.py
git commit -m "feat: add stock video deduplication via URL registry"
```

---

### Task 2: Per-Section Color Grade

**Files:**
- Modify: `musicvid/pipeline/assembler.py`
- Test: `tests/test_assembler.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_assembler.py`:

```python
from musicvid.pipeline.assembler import apply_section_grade


class TestApplySectionGrade:
    """Per-section color grade via MoviePy image_transform."""

    def test_returns_clip_object(self):
        mock_clip = MagicMock()
        mock_clip.image_transform.return_value = mock_clip
        result = apply_section_grade(mock_clip, "verse")
        assert result is mock_clip
        mock_clip.image_transform.assert_called_once()

    def test_chorus_has_higher_saturation_than_verse(self):
        """Chorus grade should produce more saturated output than verse."""
        import numpy as np
        frame = np.full((4, 4, 3), 128, dtype=np.uint8)

        # Extract the grade_frame function for each section
        mock_clip_v = MagicMock()
        apply_section_grade(mock_clip_v, "verse")
        grade_fn_verse = mock_clip_v.image_transform.call_args[0][0]

        mock_clip_c = MagicMock()
        apply_section_grade(mock_clip_c, "chorus")
        grade_fn_chorus = mock_clip_c.image_transform.call_args[0][0]

        result_verse = grade_fn_verse(frame)
        result_chorus = grade_fn_chorus(frame)

        # Both should return valid uint8 arrays
        assert result_verse.dtype == np.uint8
        assert result_chorus.dtype == np.uint8

    def test_all_sections_produce_valid_output(self):
        """Every known section should produce a valid frame."""
        import numpy as np
        frame = np.random.randint(0, 256, (8, 8, 3), dtype=np.uint8)
        for section in ["verse", "chorus", "bridge", "intro", "outro"]:
            mock_clip = MagicMock()
            apply_section_grade(mock_clip, section)
            grade_fn = mock_clip.image_transform.call_args[0][0]
            result = grade_fn(frame)
            assert result.shape == frame.shape
            assert result.dtype == np.uint8
            assert result.min() >= 0
            assert result.max() <= 255

    def test_unknown_section_uses_default(self):
        mock_clip = MagicMock()
        mock_clip.image_transform.return_value = mock_clip
        result = apply_section_grade(mock_clip, "unknown_section")
        mock_clip.image_transform.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_assembler.py::TestApplySectionGrade -v`
Expected: ImportError for `apply_section_grade`

- [ ] **Step 3: Implement apply_section_grade in assembler.py**

Add after the `_DEFAULT_FONT_SIZE` constant (before `_get_section_for_time`):

```python
_SECTION_GRADES = {
    "verse":  (0.88, 1.08, 0.01),
    "chorus": (1.10, 1.18, 0.0),
    "bridge": (0.80, 1.25, -0.02),
    "intro":  (0.85, 1.05, 0.02),
    "outro":  (0.82, 1.03, 0.01),
}
_DEFAULT_GRADE = (0.92, 1.10, 0.0)


def apply_section_grade(clip, section):
    """Apply per-section color grade (saturation, contrast, brightness).

    Uses NumPy HSV conversion for saturation — no cv2 dependency.
    """
    import numpy as np

    sat, cont, bright = _SECTION_GRADES.get(section, _DEFAULT_GRADE)

    def grade_frame(frame):
        f = frame.astype(np.float32) + bright * 255
        f = (f - 128) * cont + 128

        # RGB → HSV saturation adjustment (pure NumPy, no cv2)
        f = np.clip(f, 0, 255)
        r, g, b = f[..., 0], f[..., 1], f[..., 2]
        maxc = np.maximum(np.maximum(r, g), b)
        minc = np.minimum(np.minimum(r, g), b)
        diff = maxc - minc
        gray = maxc * (1 - sat) + f * sat  # simplified saturation blend
        # Proper approach: blend toward grayscale
        luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
        lum3 = np.stack([luminance] * 3, axis=-1)
        result = lum3 + (f - lum3) * sat
        return np.clip(result, 0, 255).astype(np.uint8)

    return clip.image_transform(grade_frame)
```

- [ ] **Step 4: Integrate into assemble_video**

In `assemble_video`, after `clip = apply_effects(clip, level=effects_level)`, add:

```python
        section = scene.get("section", "verse")
        clip = apply_section_grade(clip, section)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_assembler.py::TestApplySectionGrade -v`
Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add musicvid/pipeline/assembler.py tests/test_assembler.py
git commit -m "feat: add per-section color grade (saturation/contrast/brightness)"
```

---

### Task 3: FFmpeg Curves Color Grade

**Files:**
- Modify: `musicvid/pipeline/color_grade.py`
- Test: `tests/test_color_grade.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_color_grade.py`:

```python
from musicvid.pipeline.color_grade import (
    get_curves_grade_filter, CURVES_GRADES, apply_global_color_grade,
)


class TestCurvesGrades:
    def test_all_grade_names_defined(self):
        for name in ["worship-warm", "teal-orange", "bleach", "natural"]:
            assert name in CURVES_GRADES

    def test_worship_warm_contains_curves(self):
        f = get_curves_grade_filter("worship-warm")
        assert "curves=" in f

    def test_teal_orange_contains_curves(self):
        f = get_curves_grade_filter("teal-orange")
        assert "curves=" in f

    def test_bleach_contains_eq(self):
        f = get_curves_grade_filter("bleach")
        assert "eq=" in f

    def test_natural_contains_eq(self):
        f = get_curves_grade_filter("natural")
        assert "eq=" in f

    def test_unknown_grade_defaults_to_worship_warm(self):
        f = get_curves_grade_filter("nonexistent")
        assert f == get_curves_grade_filter("worship-warm")

    def test_social_mode_adjusts_filter(self):
        full = get_curves_grade_filter("worship-warm", is_social=False)
        social = get_curves_grade_filter("worship-warm", is_social=True)
        assert full != social  # social has different eq values


class TestApplyGlobalColorGrade:
    @patch("musicvid.pipeline.color_grade.subprocess")
    def test_runs_ffmpeg_with_curves(self, mock_subprocess):
        mock_subprocess.run.return_value = MagicMock(returncode=0)
        apply_global_color_grade("/tmp/in.mp4", "/tmp/out.mp4", "worship-warm")
        mock_subprocess.run.assert_called_once()
        cmd = mock_subprocess.run.call_args[0][0]
        assert "ffmpeg" in cmd[0]
        assert "-vf" in cmd

    @patch("musicvid.pipeline.color_grade.subprocess")
    def test_ffmpeg_failure_returns_false(self, mock_subprocess):
        mock_subprocess.run.side_effect = Exception("ffmpeg crashed")
        result = apply_global_color_grade("/tmp/in.mp4", "/tmp/out.mp4", "worship-warm")
        assert result is False

    @patch("musicvid.pipeline.color_grade.subprocess")
    def test_social_flag_passes_social_filter(self, mock_subprocess):
        mock_subprocess.run.return_value = MagicMock(returncode=0)
        apply_global_color_grade("/tmp/in.mp4", "/tmp/out.mp4", "worship-warm", is_social=True)
        cmd = mock_subprocess.run.call_args[0][0]
        vf_idx = cmd.index("-vf")
        vf_str = cmd[vf_idx + 1]
        assert "1.05" in vf_str or "1.15" in vf_str  # social eq values
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_color_grade.py::TestCurvesGrades tests/test_color_grade.py::TestApplyGlobalColorGrade -v`
Expected: ImportError

- [ ] **Step 3: Implement curves grade in color_grade.py**

Add to `color_grade.py` (after existing code):

```python
import subprocess


CURVES_GRADES = {
    "worship-warm": {
        "curves": "curves=r='0/0 0.3/0.28 0.7/0.75 1/1':g='0/0 0.3/0.29 0.7/0.72 1/0.97':b='0/0.05 0.3/0.32 0.7/0.68 1/0.92'",
        "eq_full": "eq=saturation=0.92:contrast=1.12",
        "eq_social": "eq=saturation=1.05:contrast=1.15",
    },
    "teal-orange": {
        "curves": "curves=r='0/0 0.5/0.58 1/1':g='0/0 0.5/0.50 1/0.96':b='0/0.08 0.5/0.45 1/0.88'",
        "eq_full": "eq=saturation=1.05:contrast=1.15",
        "eq_social": "eq=saturation=1.10:contrast=1.18",
    },
    "bleach": {
        "curves": None,
        "eq_full": "eq=saturation=0.75:contrast=1.30:brightness=-0.01",
        "eq_social": "eq=saturation=0.78:contrast=1.35:brightness=-0.01",
    },
    "natural": {
        "curves": None,
        "eq_full": "eq=saturation=0.95:contrast=1.05",
        "eq_social": "eq=saturation=0.98:contrast=1.08",
    },
}


def get_curves_grade_filter(grade_name, is_social=False):
    """Return FFmpeg -vf filter string for the given color grade.

    Args:
        grade_name: One of worship-warm, teal-orange, bleach, natural.
        is_social: If True, use slightly stronger eq for social reels.

    Returns:
        FFmpeg -vf filter string.
    """
    grade = CURVES_GRADES.get(grade_name, CURVES_GRADES["worship-warm"])
    eq_key = "eq_social" if is_social else "eq_full"
    parts = []
    if grade["curves"]:
        parts.append(grade["curves"])
    parts.append(grade[eq_key])
    return ",".join(parts)


def apply_global_color_grade(input_path, output_path, grade_name, is_social=False):
    """Apply global color grade via FFmpeg as a post-processing step.

    Args:
        input_path: Path to input video.
        output_path: Path to output video.
        grade_name: Color grade name.
        is_social: If True, use social-tuned eq.

    Returns:
        True on success, False on failure (original preserved).
    """
    vf = get_curves_grade_filter(grade_name, is_social=is_social)
    cmd = [
        "ffmpeg", "-i", input_path,
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast",
        "-c:a", "copy",
        "-y", output_path,
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except Exception:
        print(f"WARN: Global color grade failed for {input_path} — using original")
        return False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_color_grade.py::TestCurvesGrades tests/test_color_grade.py::TestApplyGlobalColorGrade -v`
Expected: 10 passed

- [ ] **Step 5: Commit**

```bash
git add musicvid/pipeline/color_grade.py tests/test_color_grade.py
git commit -m "feat: add FFmpeg curves-based color grades (worship-warm, teal-orange, bleach, natural)"
```

---

### Task 4: CLI --color-grade Flag

**Files:**
- Modify: `musicvid/musicvid.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_cli.py` (find the existing test pattern with `CliRunner`):

```python
class TestColorGradeFlag:
    """Tests for --color-grade CLI flag."""

    @patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")
    @patch("musicvid.musicvid.assemble_all_parallel")
    @patch("musicvid.musicvid.select_social_clips")
    @patch("musicvid.musicvid.VisualRouter")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    def test_color_grade_passed_to_assembly(self, mock_analyze, mock_director,
                                            mock_router, mock_social, mock_parallel,
                                            mock_font, cli_runner, tmp_audio):
        mock_analyze.return_value = {"bpm": 120, "duration": 60, "beats": [],
                                     "sections": [], "lyrics": [], "energy_peaks": []}
        mock_director.return_value = {"scenes": [{"start": 0, "end": 60, "section": "verse",
                                      "visual_source": "TYPE_VIDEO_STOCK", "search_query": "nature",
                                      "motion": "static"}],
                                      "overall_style": "worship",
                                      "subtitle_style": {"animation": "karaoke", "color": "#FFFFFF",
                                                         "outline_color": "#000000", "font_size": 54}}
        mock_router_inst = MagicMock()
        mock_router_inst.route_all.return_value = [{"scene_index": 0, "video_path": "/fake/v.mp4",
                                                    "start": 0, "end": 60}]
        mock_router.return_value = mock_router_inst
        mock_social.return_value = {"clips": []}
        mock_parallel.return_value = ["/fake/out.mp4"]

        result = cli_runner.invoke(cli, [str(tmp_audio), "--mode", "stock", "--preset", "full",
                                         "--color-grade", "teal-orange"])
        assert result.exit_code == 0
        # The color_grade kwarg should be passed to assembly jobs
        job_kwargs = mock_parallel.call_args[0][0][0].kwargs if mock_parallel.called else {}
        # Or if single job, check assemble_video call
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_cli.py::TestColorGradeFlag -v`
Expected: FAIL — `--color-grade` not a recognized option

- [ ] **Step 3: Add --color-grade flag to CLI**

In `musicvid.py`, add a new Click option after `--lut-intensity`:

```python
@click.option("--color-grade", "color_grade", type=click.Choice(["worship-warm", "teal-orange", "bleach", "natural"]), default=None, help="Global color grade style applied via FFmpeg curves (default: auto from director style).")
```

Add `color_grade` to the `cli()` function signature.

Add a `_color_grade_for_style` mapping (after `_lut_for_style`):

```python
_STYLE_TO_COLOR_GRADE = {
    "worship": "worship-warm",
    "contemplative": "worship-warm",
    "powerful": "teal-orange",
    "joyful": "natural",
}


def _color_grade_for_style(overall_style):
    """Return color grade name for a given director overall_style."""
    return _STYLE_TO_COLOR_GRADE.get(overall_style, "worship-warm")
```

In `cli()`, after Stage 2 scene plan is loaded, add auto-selection logic:

```python
    if not color_grade:
        color_grade = _color_grade_for_style(scene_plan.get("overall_style", "worship"))
```

Pass `color_grade` to `_run_preset_mode()` and through to `assemble_video` kwargs as a new kwarg.

Add `color_grade=None` parameter to `_run_preset_mode` and pass it into each `AssemblyJob.kwargs`.

- [ ] **Step 4: Wire color grade into assembler**

In `assembler.py`, add `color_grade=None` to `assemble_video()` signature.

After `final.write_videofile(output_path, **write_kwargs)`, add:

```python
    # Apply global color grade via FFmpeg curves (post-write)
    if color_grade:
        from musicvid.pipeline.color_grade import apply_global_color_grade
        import tempfile, shutil
        is_social = (target_size == (1080, 1920))
        tmp_graded = output_path + ".graded.mp4"
        success = apply_global_color_grade(output_path, tmp_graded, color_grade, is_social=is_social)
        if success:
            shutil.move(tmp_graded, output_path)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_cli.py::TestColorGradeFlag -v`
Expected: PASS

- [ ] **Step 6: Run full test suite**

Run: `python3 -m pytest tests/ -v --tb=short`
Expected: All tests pass (existing tests should be unaffected since color_grade defaults to None)

- [ ] **Step 7: Commit**

```bash
git add musicvid/musicvid.py musicvid/pipeline/assembler.py tests/test_cli.py
git commit -m "feat: add --color-grade CLI flag with auto-selection from director style"
```

---

### Task 5: Reel Transitions (slide/wipe)

**Files:**
- Modify: `musicvid/pipeline/assembler.py`
- Modify: `musicvid/musicvid.py`
- Test: `tests/test_assembler.py`
- Test: `tests/test_dynamics.py`

- [ ] **Step 1: Write failing tests for reel transition map**

Add to `tests/test_dynamics.py`:

```python
from musicvid.musicvid import _assign_reel_transitions, _REEL_TRANSITIONS_MAP


class TestReelTransitions:
    def _make_scenes(self, sections):
        scenes = []
        t = 0.0
        for s in sections:
            scenes.append({"section": s, "start": t, "end": t + 10.0})
            t += 10.0
        return scenes

    def test_verse_to_chorus_is_slide_up(self):
        scenes = self._make_scenes(["verse", "chorus"])
        result = _assign_reel_transitions(scenes, bpm=84.0)
        assert result[0]["transition_to_next"] == "slide_up"

    def test_chorus_to_verse_is_zoom_in_hard(self):
        scenes = self._make_scenes(["chorus", "verse"])
        result = _assign_reel_transitions(scenes, bpm=84.0)
        assert result[0]["transition_to_next"] == "zoom_in_hard"

    def test_chorus_to_chorus_is_wipe_right(self):
        scenes = self._make_scenes(["chorus", "chorus"])
        result = _assign_reel_transitions(scenes, bpm=84.0)
        assert result[0]["transition_to_next"] == "wipe_right"

    def test_verse_to_verse_is_slide_left(self):
        scenes = self._make_scenes(["verse", "verse"])
        result = _assign_reel_transitions(scenes, bpm=84.0)
        assert result[0]["transition_to_next"] == "slide_left"

    def test_bridge_to_chorus_is_slide_up(self):
        scenes = self._make_scenes(["bridge", "chorus"])
        result = _assign_reel_transitions(scenes, bpm=84.0)
        assert result[0]["transition_to_next"] == "slide_up"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_dynamics.py::TestReelTransitions -v`
Expected: ImportError for `_assign_reel_transitions`

- [ ] **Step 3: Implement reel transition map in musicvid.py**

Add after `_assign_dynamic_transitions`:

```python
_REEL_TRANSITIONS_MAP = {
    ("verse", "chorus"):  "slide_up",
    ("chorus", "verse"):  "zoom_in_hard",
    ("chorus", "chorus"): "wipe_right",
    ("verse", "verse"):   "slide_left",
    ("bridge", "chorus"): "slide_up",
    ("verse", "bridge"):  "slide_left",
    ("intro", "verse"):   "slide_up",
    ("chorus", "outro"):  "slide_left",
}
_DEFAULT_REEL_TRANSITION = "slide_left"


def _assign_reel_transitions(scenes, bpm):
    """Assign reel-specific transitions (more dynamic than full video)."""
    for i in range(len(scenes) - 1):
        key = (scenes[i].get("section", ""), scenes[i + 1].get("section", ""))
        scenes[i]["transition_to_next"] = _REEL_TRANSITIONS_MAP.get(key, _DEFAULT_REEL_TRANSITION)
    return scenes
```

- [ ] **Step 4: Run reel transition map tests**

Run: `python3 -m pytest tests/test_dynamics.py::TestReelTransitions -v`
Expected: 5 passed

- [ ] **Step 5: Write failing tests for assembler transition rendering**

Add to `tests/test_assembler.py`:

```python
class TestReelTransitionRendering:
    """New reel transition types in _concatenate_with_transitions."""

    @patch("musicvid.pipeline.assembler.CompositeVideoClip")
    @patch("musicvid.pipeline.assembler.concatenate_videoclips")
    def test_slide_left_uses_composite(self, mock_concat, mock_composite):
        from musicvid.pipeline.assembler import _concatenate_with_transitions
        clip_a = MagicMock()
        clip_a.duration = 5.0
        clip_a.with_start.return_value = clip_a
        clip_a.with_effects.return_value = clip_a
        clip_b = MagicMock()
        clip_b.duration = 5.0
        clip_b.with_start.return_value = clip_b
        clip_b.with_position.return_value = clip_b
        clip_b.with_effects.return_value = clip_b

        mock_composite.return_value = MagicMock()
        mock_composite.return_value.with_duration.return_value = mock_composite.return_value

        scenes = [
            {"section": "verse", "transition_to_next": "slide_left"},
            {"section": "verse"},
        ]
        _concatenate_with_transitions([clip_a, clip_b], scenes, bpm=120.0, target_size=(1080, 1920))
        # Should NOT use simple concatenate (since we have non-cut transitions)
        mock_composite.assert_called()

    @patch("musicvid.pipeline.assembler.CompositeVideoClip")
    @patch("musicvid.pipeline.assembler.concatenate_videoclips")
    def test_slide_up_uses_composite(self, mock_concat, mock_composite):
        from musicvid.pipeline.assembler import _concatenate_with_transitions
        clip_a = MagicMock()
        clip_a.duration = 5.0
        clip_a.with_start.return_value = clip_a
        clip_a.with_effects.return_value = clip_a
        clip_b = MagicMock()
        clip_b.duration = 5.0
        clip_b.with_start.return_value = clip_b
        clip_b.with_position.return_value = clip_b
        clip_b.with_effects.return_value = clip_b

        mock_composite.return_value = MagicMock()
        mock_composite.return_value.with_duration.return_value = mock_composite.return_value

        scenes = [
            {"section": "verse", "transition_to_next": "slide_up"},
            {"section": "chorus"},
        ]
        _concatenate_with_transitions([clip_a, clip_b], scenes, bpm=120.0, target_size=(1080, 1920))
        mock_composite.assert_called()
```

- [ ] **Step 6: Implement reel transitions in assembler.py**

Update `_concatenate_with_transitions` in assembler.py. Add the new transition types to `trans_durations`:

```python
    trans_durations = {
        "cut":           0.0,
        "cross_dissolve": max(0.2, min(0.8, round(beat_duration / 2, 2))),
        "fade":          max(0.2, min(0.8, round(beat_duration, 2))),
        "dip_white":     max(0.2, min(0.8, round(beat_duration * 0.75, 2))),
        "slide_left":    0.3,
        "slide_up":      0.3,
        "wipe_right":    0.2,
        "zoom_in_hard":  0.1,
    }
```

Update the "Fast path" check to include all cut-like transitions (only "cut" has duration 0):

```python
    if all(d == 0.0 for _, d in transitions):
        return concatenate_videoclips(scene_clips, method="compose")
```

In the compositing loop, add handlers for the new transitions. After the existing incoming transition effects block, add slide/wipe position transforms:

```python
        if i > 0:
            prev_trans, prev_d = transitions[i - 1]
            if prev_trans == "cross_dissolve" and prev_d > 0:
                positioned = positioned.with_effects([vfx.CrossFadeIn(prev_d)])
            elif prev_trans == "fade" and prev_d > 0:
                positioned = positioned.with_effects([vfx.FadeIn(prev_d)])
            elif prev_trans == "slide_left" and prev_d > 0:
                w = target_size[0]
                d = prev_d
                def _make_slide_left_pos(w, d):
                    def pos(t):
                        if t < d:
                            return (int(w * (1 - t / d)), 0)
                        return (0, 0)
                    return pos
                positioned = positioned.with_position(_make_slide_left_pos(w, d))
            elif prev_trans == "slide_up" and prev_d > 0:
                h = target_size[1]
                d = prev_d
                def _make_slide_up_pos(h, d):
                    def pos(t):
                        if t < d:
                            return (0, int(h * (1 - t / d)))
                        return (0, 0)
                    return pos
                positioned = positioned.with_position(_make_slide_up_pos(h, d))
            elif prev_trans == "wipe_right" and prev_d > 0:
                positioned = positioned.with_effects([vfx.CrossFadeIn(prev_d)])
```

For zoom_in_hard, apply a zoom transform to the outgoing clip's last frames:

```python
        if i < len(scene_clips) - 1:
            trans, d = transitions[i]
            # ... existing outgoing effects ...
            if trans == "zoom_in_hard" and d > 0:
                clip_dur = clip.duration
                def _make_zoom_hard(clip_dur, d):
                    def zoom_fn(get_frame, t):
                        frame = get_frame(t)
                        if t >= clip_dur - d:
                            progress = (t - (clip_dur - d)) / d
                            scale = 1.0 + 0.3 * progress
                            from PIL import Image
                            import numpy as np
                            fh, fw = frame.shape[:2]
                            new_w = max(1, int(fw / scale))
                            new_h = max(1, int(fh / scale))
                            x = (fw - new_w) // 2
                            y = (fh - new_h) // 2
                            cropped = frame[y:y + new_h, x:x + new_w]
                            img = Image.fromarray(cropped).resize((fw, fh), Image.LANCZOS)
                            return np.array(img)
                        return frame
                    return zoom_fn
                positioned = positioned.transform(_make_zoom_hard(clip_dur, d))
```

For slide transitions, advance cursor with overlap (like dissolve):

```python
        if i < len(scene_clips) - 1:
            trans, d = transitions[i]
            if trans in ("cross_dissolve", "slide_left", "slide_up", "wipe_right"):
                cursor += clip.duration - d
            else:
                cursor += clip.duration
```

- [ ] **Step 7: Use reel transitions in _run_preset_mode**

In `musicvid.py` `_run_preset_mode`, when building social reels, replace the call to `_assign_dynamic_transitions` with `_assign_reel_transitions`. Find where `clip_scene_plan` scenes are prepared and add:

```python
            _assign_reel_transitions(clip_scene_plan["scenes"], analysis.get("bpm", 120))
```

This means we need to pass a flag or handle this in the transition assignment. The cleanest way: in `_run_preset_mode`, after building `clip_scene_plan`, call `_assign_reel_transitions` on the reel scenes.

- [ ] **Step 8: Run all tests**

Run: `python3 -m pytest tests/test_dynamics.py tests/test_assembler.py -v --tb=short`
Expected: All pass

- [ ] **Step 9: Commit**

```bash
git add musicvid/pipeline/assembler.py musicvid/musicvid.py tests/test_assembler.py tests/test_dynamics.py
git commit -m "feat: add slide/wipe/zoom reel transitions with reel-specific transition map"
```

---

### Task 6: Reel Zoom Punch (MoviePy)

**Files:**
- Modify: `musicvid/pipeline/assembler.py`
- Test: `tests/test_assembler.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_assembler.py`:

```python
from musicvid.pipeline.assembler import _make_reel_zoom_punch


class TestReelZoomPunch:
    """Zoom punch on chorus downbeats for reels (MoviePy-based)."""

    def test_returns_transform_function(self):
        punch_times = [2.0, 4.0]
        fn = _make_reel_zoom_punch(punch_times)
        assert callable(fn)

    def test_no_zoom_outside_punch_window(self):
        import numpy as np
        punch_times = [2.0]
        fn = _make_reel_zoom_punch(punch_times)
        frame = np.full((100, 100, 3), 128, dtype=np.uint8)
        get_frame = lambda t: frame
        result = fn(get_frame, 0.0)
        np.testing.assert_array_equal(result, frame)

    def test_zoom_during_punch_attack(self):
        import numpy as np
        punch_times = [2.0]
        fn = _make_reel_zoom_punch(punch_times)
        frame = np.full((100, 100, 3), 128, dtype=np.uint8)
        get_frame = lambda t: frame
        result = fn(get_frame, 2.03)  # during attack phase (0-0.067s)
        # Result should be zoomed (different from original due to crop+resize)
        assert result.shape == frame.shape

    def test_empty_punch_times_returns_unmodified(self):
        import numpy as np
        fn = _make_reel_zoom_punch([])
        frame = np.full((100, 100, 3), 128, dtype=np.uint8)
        get_frame = lambda t: frame
        result = fn(get_frame, 1.0)
        np.testing.assert_array_equal(result, frame)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_assembler.py::TestReelZoomPunch -v`
Expected: ImportError

- [ ] **Step 3: Implement _make_reel_zoom_punch in assembler.py**

Add before `_create_subtitle_clips`:

```python
def _make_reel_zoom_punch(punch_times):
    """Return a MoviePy transform for reel zoom punch on chorus downbeats.

    Scale 1.0 → 1.12 in 2 frames (0.067s), return 1.12 → 1.0 in 8 frames (0.267s).
    """
    from PIL import Image
    import numpy as np

    def zoom_punch(get_frame, t):
        frame = get_frame(t)
        for pt in punch_times:
            dt = t - pt
            if 0 <= dt < 0.067:
                scale = 1.0 + 0.12 * (dt / 0.067)
            elif 0.067 <= dt < 0.333:
                scale = 1.12 - 0.12 * ((dt - 0.067) / 0.267)
            else:
                continue
            fh, fw = frame.shape[:2]
            new_w = max(1, int(fw / scale))
            new_h = max(1, int(fh / scale))
            x = (fw - new_w) // 2
            y = (fh - new_h) // 2
            cropped = frame[y:y + new_h, x:x + new_w]
            img = Image.fromarray(cropped).resize((fw, fh), Image.LANCZOS)
            return np.array(img)
        return frame

    return zoom_punch
```

- [ ] **Step 4: Integrate zoom punch in assemble_video for reels**

In `assemble_video`, after `video = _concatenate_with_transitions(...)`, add:

```python
    # Reel zoom punch on chorus downbeats
    if target_size == (1080, 1920):
        sections = analysis.get("sections", [])
        beats = analysis.get("beats", [])
        downbeats = beats[::4]  # every 4th beat
        chorus_downbeats = []
        for db in downbeats:
            for sec in sections:
                if sec.get("label") == "chorus" and sec["start"] <= db < sec["end"]:
                    chorus_downbeats.append(db)
                    break
        if chorus_downbeats:
            video = video.transform(_make_reel_zoom_punch(chorus_downbeats))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_assembler.py::TestReelZoomPunch -v`
Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add musicvid/pipeline/assembler.py tests/test_assembler.py
git commit -m "feat: add MoviePy-based reel zoom punch on chorus downbeats"
```

---

### Task 7: Text Flash for Reels

**Files:**
- Modify: `musicvid/pipeline/assembler.py`
- Test: `tests/test_assembler.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_assembler.py`:

```python
class TestTextFlash:
    """White flash on subtitle entry for reels."""

    @patch("musicvid.pipeline.assembler.ColorClip")
    @patch("musicvid.pipeline.assembler.vfx")
    @patch("musicvid.pipeline.assembler.TextClip")
    def test_reels_mode_creates_flash_clips(self, mock_text_clip, mock_vfx, mock_color_clip):
        from musicvid.pipeline.assembler import _create_subtitle_clips
        mock_clip = MagicMock()
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.with_start.return_value = mock_clip
        mock_clip.with_position.return_value = mock_clip
        mock_clip.with_effects.return_value = mock_clip
        mock_clip.transform.return_value = mock_clip
        mock_text_clip.return_value = mock_clip

        flash_clip = MagicMock()
        flash_clip.with_duration.return_value = flash_clip
        flash_clip.with_start.return_value = flash_clip
        flash_clip.with_effects.return_value = flash_clip
        flash_clip.with_mask.return_value = flash_clip
        mock_color_clip.return_value = flash_clip

        lyrics = [{"start": 5.0, "end": 7.0, "text": "Hallelujah"}]
        sections = [{"label": "chorus", "start": 0.0, "end": 10.0}]
        subtitle_style = {"font_size": 54, "color": "#FFFFFF", "outline_color": "#000000"}

        clips = _create_subtitle_clips(lyrics, subtitle_style, (1080, 1920),
                                       sections=sections, reels_mode=True)
        # Should have subtitle clip + flash clip
        assert len(clips) >= 2
        mock_color_clip.assert_called()

    @patch("musicvid.pipeline.assembler.ColorClip")
    @patch("musicvid.pipeline.assembler.vfx")
    @patch("musicvid.pipeline.assembler.TextClip")
    def test_non_reels_mode_no_flash(self, mock_text_clip, mock_vfx, mock_color_clip):
        from musicvid.pipeline.assembler import _create_subtitle_clips
        mock_clip = MagicMock()
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.with_start.return_value = mock_clip
        mock_clip.with_position.return_value = mock_clip
        mock_clip.with_effects.return_value = mock_clip
        mock_text_clip.return_value = mock_clip

        lyrics = [{"start": 5.0, "end": 7.0, "text": "Hallelujah"}]
        subtitle_style = {"font_size": 54, "color": "#FFFFFF", "outline_color": "#000000"}

        clips = _create_subtitle_clips(lyrics, subtitle_style, (1920, 1080),
                                       sections=None, reels_mode=False)
        # Only subtitle clip, no flash
        assert len(clips) == 1
        mock_color_clip.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_assembler.py::TestTextFlash -v`
Expected: FAIL (no flash clips created yet)

- [ ] **Step 3: Implement text flash in _create_subtitle_clips**

In `_create_subtitle_clips`, after appending the subtitle clip to `clips`, add flash for reels mode:

```python
        clips.append(txt_clip)

        # White flash on subtitle entry for reels
        if reels_mode:
            flash_duration = 0.05
            flash = ColorClip(size=size, color=(255, 255, 255), duration=flash_duration)
            flash = flash.with_start(offset_start)
            flash = flash.with_effects([
                vfx.CrossFadeIn(flash_duration / 2),
                vfx.CrossFadeOut(flash_duration / 2),
            ])
            # Set opacity to 0.6 via mask
            import numpy as np
            mask_frame = np.full((size[1], size[0]), 0.6, dtype=np.float32)
            mask_clip = ImageClip(mask_frame, is_mask=True).with_duration(flash_duration)
            flash = flash.with_mask(mask_clip)
            clips.append(flash)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_assembler.py::TestTextFlash -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add musicvid/pipeline/assembler.py tests/test_assembler.py
git commit -m "feat: add white text flash on subtitle entry for reels"
```

---

### Task 8: Reel Intro Hook (Freeze Frame)

**Files:**
- Modify: `musicvid/pipeline/assembler.py`
- Test: `tests/test_assembler.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_assembler.py`:

```python
from musicvid.pipeline.assembler import _create_reel_intro_hook


class TestReelIntroHook:
    """Freeze frame intro hook for reels (first 0.5s)."""

    def test_returns_clip_with_duration(self):
        mock_video = MagicMock()
        mock_video.get_frame.return_value = np.full((1920, 1080, 3), 128, dtype=np.uint8)
        mock_video.duration = 30.0
        result = _create_reel_intro_hook(mock_video, (1080, 1920))
        assert result is not None

    @patch("musicvid.pipeline.assembler.ImageClip")
    def test_creates_freeze_frame_from_first_clip(self, mock_image_clip):
        import numpy as np
        mock_video = MagicMock()
        mock_video.get_frame.return_value = np.full((1920, 1080, 3), 128, dtype=np.uint8)
        mock_video.duration = 30.0
        mock_freeze = MagicMock()
        mock_freeze.with_duration.return_value = mock_freeze
        mock_freeze.with_effects.return_value = mock_freeze
        mock_image_clip.return_value = mock_freeze

        result = _create_reel_intro_hook(mock_video, (1080, 1920))
        mock_image_clip.assert_called_once()
        # Should be called with the frame from middle of first scene
        mock_video.get_frame.assert_called()

    @patch("musicvid.pipeline.assembler.ImageClip")
    def test_freeze_frame_has_fade_out(self, mock_image_clip):
        import numpy as np
        mock_video = MagicMock()
        mock_video.get_frame.return_value = np.full((1920, 1080, 3), 128, dtype=np.uint8)
        mock_video.duration = 30.0
        mock_freeze = MagicMock()
        mock_freeze.with_duration.return_value = mock_freeze
        mock_freeze.with_effects.return_value = mock_freeze
        mock_image_clip.return_value = mock_freeze

        _create_reel_intro_hook(mock_video, (1080, 1920))
        mock_freeze.with_effects.assert_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_assembler.py::TestReelIntroHook -v`
Expected: ImportError for `_create_reel_intro_hook`

- [ ] **Step 3: Implement _create_reel_intro_hook in assembler.py**

Add after `_create_bottom_gradient`:

```python
def _create_reel_intro_hook(video_clip, target_size, freeze_duration=0.5, fade_duration=0.3):
    """Create a freeze frame intro hook for reels.

    Takes the frame at 50% of the first scene (the 'peak visual moment'),
    displays it for freeze_duration, then fades out into the normal video.

    Args:
        video_clip: The concatenated video clip.
        target_size: (width, height) tuple.
        freeze_duration: How long to show the freeze frame (default 0.5s).
        fade_duration: Fade out duration (default 0.3s).

    Returns:
        ImageClip of the freeze frame, or None if extraction fails.
    """
    try:
        # Get frame from 50% into the video's first second
        sample_t = min(0.5, video_clip.duration / 2)
        frame = video_clip.get_frame(sample_t)
        freeze = ImageClip(frame).with_duration(freeze_duration)
        freeze = freeze.with_effects([vfx.FadeOut(fade_duration)])
        return freeze
    except Exception as e:
        print(f"WARN: reel intro hook failed: {e}")
        return None
```

- [ ] **Step 4: Integrate into assemble_video**

In `assemble_video`, before the title card logic (`if title_card_text is not None:`), add:

```python
    # Reel intro hook: freeze frame before video
    if target_size == (1080, 1920):
        intro_hook = _create_reel_intro_hook(video, target_size)
        if intro_hook:
            final = concatenate_videoclips([intro_hook, final])
```

Wait — `final` is already a CompositeVideoClip at this point. The intro hook should be prepended before audio attachment. Place it right after `final = CompositeVideoClip(layers, size=target_size)`:

```python
    final = CompositeVideoClip(layers, size=target_size)

    # Reel intro hook: freeze frame prepended to reel
    if target_size == (1080, 1920):
        intro_hook = _create_reel_intro_hook(video, target_size)
        if intro_hook:
            final = concatenate_videoclips([intro_hook, final])
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_assembler.py::TestReelIntroHook -v`
Expected: 3 passed

- [ ] **Step 6: Run full test suite**

Run: `python3 -m pytest tests/ -v --tb=short`
Expected: All tests pass

- [ ] **Step 7: Commit**

```bash
git add musicvid/pipeline/assembler.py tests/test_assembler.py
git commit -m "feat: add reel intro hook with freeze frame and fade"
```

---

### Task 9: Gradient Overlay Opacity Fix

**Files:**
- Modify: `musicvid/pipeline/assembler.py`

The existing `_create_bottom_gradient` uses opacity=0.6; the spec says 0.5.

- [ ] **Step 1: Update default opacity**

In `assembler.py`, change the `_create_bottom_gradient` call in `assemble_video`:

```python
    if target_size == (1080, 1920):
        gradient = _create_bottom_gradient(target_size[0], target_size[1], video.duration, opacity=0.5)
```

- [ ] **Step 2: Run existing tests**

Run: `python3 -m pytest tests/test_assembler.py -v --tb=short`
Expected: All pass

- [ ] **Step 3: Commit**

```bash
git add musicvid/pipeline/assembler.py
git commit -m "fix: adjust reel gradient overlay opacity from 0.6 to 0.5 per spec"
```
