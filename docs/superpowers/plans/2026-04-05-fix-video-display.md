# Fix Video Display Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix three video display bugs: cinematic bars shown by default (should be off unless `--effects full`), images not cover-scaled before Ken Burns, and subtitles failing silently.

**Architecture:** All three fixes are isolated to `musicvid/pipeline/assembler.py` and the CLI call-site in `musicvid/musicvid.py`. No new files. Tests are updated in-place in `tests/test_assembler.py`.

**Tech Stack:** Python 3.11+, MoviePy 2.1.2, unittest.mock

---

## File Map

- Modify: `musicvid/pipeline/assembler.py` — three changes: cinematic_bars default, cover scale in `_create_ken_burns_clip`, subtitle try/except
- Modify: `musicvid/musicvid.py` — two call-sites of `assemble_video` gain explicit `cinematic_bars=(effects == "full")`
- Modify: `tests/test_assembler.py` — update broken assertions, add new tests for all three fixes

---

## Task 1: Fix cinematic bars default

**Files:**
- Modify: `musicvid/pipeline/assembler.py:202,237`
- Modify: `musicvid/musicvid.py:336,391`
- Modify: `tests/test_assembler.py:257-268` (update `test_minimal_effects_applied`)
- Test: `tests/test_assembler.py` (add new `test_cinematic_bars_enabled_when_flag_true`)

- [ ] **Step 1: Write the failing tests**

In `tests/test_assembler.py`, in class `TestAssembleVideoEffects`, change `test_minimal_effects_applied` to expect bars NOT called, and add a new test:

```python
# CHANGE: test_minimal_effects_applied — replace mock_bars.assert_called_once() with:
mock_bars.assert_not_called()

# ADD new test method in TestAssembleVideoEffects, after test_none_effects_skip_all:
@patch("musicvid.pipeline.assembler.create_cinematic_bars")
@patch("musicvid.pipeline.assembler.create_light_leak")
@patch("musicvid.pipeline.assembler.apply_effects")
@patch("musicvid.pipeline.assembler.vfx")
@patch("musicvid.pipeline.assembler.VideoFileClip")
@patch("musicvid.pipeline.assembler.ImageClip")
@patch("musicvid.pipeline.assembler.AudioFileClip")
@patch("musicvid.pipeline.assembler.TextClip")
@patch("musicvid.pipeline.assembler.CompositeVideoClip")
@patch("musicvid.pipeline.assembler.concatenate_videoclips")
def test_cinematic_bars_enabled_when_flag_true(
    self, mock_concat, mock_composite, mock_text, mock_audio,
    mock_image, mock_video, mock_vfx, mock_apply_effects,
    mock_light_leak, mock_bars,
    sample_analysis, sample_scene_plan, tmp_output
):
    mock_clip = MagicMock()
    mock_clip.duration = 5.0
    mock_clip.size = (1920, 1080)
    mock_clip.w = 1920
    mock_clip.h = 1080
    mock_clip.resized.return_value = mock_clip
    mock_clip.subclipped.return_value = mock_clip
    mock_clip.with_duration.return_value = mock_clip
    mock_clip.with_position.return_value = mock_clip
    mock_clip.with_start.return_value = mock_clip
    mock_clip.with_effects.return_value = mock_clip
    mock_clip.transform.return_value = mock_clip
    mock_clip.with_audio.return_value = mock_clip
    mock_video.return_value = mock_clip
    mock_image.return_value = mock_clip
    mock_audio.return_value = mock_clip
    mock_text.return_value = mock_clip
    mock_concat.return_value = mock_clip
    mock_composite.return_value = mock_clip
    mock_apply_effects.return_value = mock_clip
    mock_bars.return_value = [mock_clip, mock_clip]

    fetch_manifest = [
        {"scene_index": 0, "video_path": "/fake/scene_000.mp4", "search_query": "test"},
    ]

    assemble_video(
        analysis=sample_analysis,
        scene_plan=sample_scene_plan,
        fetch_manifest=fetch_manifest,
        audio_path="/fake/audio.mp3",
        output_path=str(tmp_output / "output.mp4"),
        resolution="1080p",
        effects_level="full",
        cinematic_bars=True,
    )

    mock_bars.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/s.rzytki/Documents/aiprojects/musicvideo
python3 -m pytest tests/test_assembler.py::TestAssembleVideoEffects -v 2>&1 | tail -20
```

Expected: `test_minimal_effects_applied` FAILS (bars called when shouldn't), `test_cinematic_bars_enabled_when_flag_true` may not exist yet.

- [ ] **Step 3: Fix assembler.py — change default and condition**

In `musicvid/pipeline/assembler.py`:

Change line 202 (function signature): `cinematic_bars=True` → `cinematic_bars=False`

Change lines 237-239 from:
```python
    if cinematic_bars and effects_level in ("minimal", "full"):
        bars = create_cinematic_bars(target_size[0], target_size[1], video.duration)
        layers.extend(bars)
```
To:
```python
    if cinematic_bars:
        bars = create_cinematic_bars(target_size[0], target_size[1], video.duration)
        layers.extend(bars)
```

- [ ] **Step 4: Fix musicvid.py — standard mode call-site**

In `musicvid/musicvid.py`, in the standard mode `assemble_video(...)` call at line ~336, add `cinematic_bars` kwarg:

```python
    assemble_video(
        analysis=analysis,
        scene_plan=scene_plan,
        fetch_manifest=fetch_manifest,
        audio_path=str(audio_path),
        output_path=output_path,
        resolution=effective_resolution,
        font_path=font,
        effects_level=effects,
        clip_start=clip_start,
        clip_end=clip_end,
        title_card_text=title_card_text,
        logo_path=logo_path,
        logo_position=logo_position,
        logo_size=logo_size,
        logo_opacity=logo_opacity,
        cinematic_bars=(effects == "full"),
    )
```

- [ ] **Step 5: Fix musicvid.py — preset full mode call-site**

In `musicvid/musicvid.py`, in `_run_preset_mode`, in the full YouTube `assemble_video(...)` call at line ~391, add `cinematic_bars` kwarg:

```python
        assemble_video(
            analysis=analysis,
            scene_plan=scene_plan,
            fetch_manifest=fetch_manifest,
            audio_path=audio_path,
            output_path=full_output,
            resolution="1080p",
            font_path=font,
            effects_level=effects,
            logo_path=logo_path,
            logo_position=logo_position,
            logo_size=logo_size,
            logo_opacity=logo_opacity,
            cinematic_bars=(effects == "full"),
        )
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_assembler.py::TestAssembleVideoEffects -v 2>&1 | tail -20
```

Expected: All `TestAssembleVideoEffects` tests PASS.

- [ ] **Step 7: Run full test suite to check for regressions**

```bash
python3 -m pytest tests/ -v 2>&1 | tail -30
```

Expected: All tests pass.

- [ ] **Step 8: Commit**

```bash
git add musicvid/pipeline/assembler.py musicvid/musicvid.py tests/test_assembler.py
git commit -m "fix(assembler): disable cinematic bars by default, only on --effects full"
```

---

## Task 2: Fix image cover scaling in Ken Burns

**Files:**
- Modify: `musicvid/pipeline/assembler.py:35-38` (start of `_create_ken_burns_clip`)
- Modify: `tests/test_assembler.py` — update 4 existing tests, add 1 new test

- [ ] **Step 1: Write the failing test for cover scaling**

Add new test class `TestKenBurnsCoverScale` in `tests/test_assembler.py`:

```python
class TestKenBurnsCoverScale:
    """Tests that _create_ken_burns_clip uses cover scaling (not stretch)."""

    def test_cover_scale_fills_frame_preserving_aspect_ratio(self):
        """4:3 image into 16:9 frame: must scale up and crop, not stretch."""
        from musicvid.pipeline.assembler import _create_ken_burns_clip
        from unittest.mock import MagicMock, call

        # Simulate a 1024x768 BFL image (4:3 ratio)
        mock_clip = MagicMock()
        mock_clip.size = (1024, 768)
        mock_clip.w = 1024
        mock_clip.h = 768
        mock_clip.resized.return_value = mock_clip
        mock_clip.cropped.return_value = mock_clip
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.transform.return_value = mock_clip

        target_size = (1920, 1080)
        _create_ken_burns_clip(mock_clip, 5.0, "slow_zoom_in", target_size)

        # Cover scale: scale factor is a float (not a tuple)
        resized_call = mock_clip.resized.call_args
        assert resized_call is not None
        # resized should be called with a scalar, not new_size tuple
        # (scalar means proportional resize for cover scaling)
        args, kwargs = resized_call
        if args:
            scale_arg = args[0]
        else:
            scale_arg = kwargs.get("new_size", None)
        # Must be a float/int scalar (cover scale), NOT a tuple (stretch)
        assert not isinstance(scale_arg, tuple), (
            f"resized() was called with tuple {scale_arg!r} (stretch), "
            "expected scalar (cover scale)"
        )

        # cropped must be called to trim the overflow
        mock_clip.cropped.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m pytest tests/test_assembler.py::TestKenBurnsCoverScale -v 2>&1 | tail -20
```

Expected: FAIL — `resized()` called with a tuple.

- [ ] **Step 3: Fix `_create_ken_burns_clip` in assembler.py**

Replace the first two lines of `_create_ken_burns_clip` (currently):
```python
    w, h = target_size
    clip = clip.resized(new_size=(int(w * 1.15), int(h * 1.15)))
    clip = clip.with_duration(duration)
```

With:
```python
    w, h = target_size
    kb_w, kb_h = int(w * 1.15), int(h * 1.15)

    # Cover scale: expand to fill kb_w × kb_h preserving aspect ratio, then center-crop
    img_w, img_h = clip.size
    scale = max(kb_w / img_w, kb_h / img_h)
    clip = clip.resized(scale)
    x1 = (clip.w - kb_w) // 2
    y1 = (clip.h - kb_h) // 2
    clip = clip.cropped(x1=x1, y1=y1, x2=x1 + kb_w, y2=y1 + kb_h)
    clip = clip.with_duration(duration)
```

- [ ] **Step 4: Update `test_non_animated_image_uses_ken_burns` to add missing mock attrs**

The test at `tests/test_assembler.py` class `TestLoadSceneClipAnimated.test_non_animated_image_uses_ken_burns` currently does not set `mock_clip.size`, `mock_clip.w`, `mock_clip.h`, or `mock_clip.cropped`. After the fix, `_create_ken_burns_clip` reads `clip.size` and calls `clip.cropped(...)`. Because `mock_clip.cropped` is not configured to return `mock_clip`, the subsequent `.with_duration()` and `.transform()` calls land on a different MagicMock, breaking `mock_clip.transform.assert_called()`.

Update the test setup to add:
```python
        mock_clip.size = (1920, 1080)
        mock_clip.w = 1920
        mock_clip.h = 1080
        mock_clip.cropped.return_value = mock_clip
```

Full updated test:
```python
    @patch("musicvid.pipeline.assembler.ImageClip")
    def test_non_animated_image_uses_ken_burns(self, mock_ic, tmp_path):
        from musicvid.pipeline.assembler import _load_scene_clip

        fake_jpg = tmp_path / "scene.jpg"
        fake_jpg.write_bytes(b"fake jpeg")

        mock_clip = MagicMock()
        mock_clip.duration = None
        mock_clip.size = (1920, 1080)
        mock_clip.w = 1920
        mock_clip.h = 1080
        mock_ic.return_value = mock_clip
        mock_clip.resized.return_value = mock_clip
        mock_clip.cropped.return_value = mock_clip
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.transform.return_value = mock_clip

        scene = {"start": 0.0, "end": 5.0, "motion": "slow_zoom_in", "animate": False}
        _load_scene_clip(str(fake_jpg), scene, (1920, 1080))

        # transform (Ken Burns) SHOULD be called
        mock_clip.transform.assert_called()
```

- [ ] **Step 5: Update `test_non_animated_mp4_uses_ken_burns` to add missing mock attrs**

Same fix — add `size`, `w`, `h`, `cropped` to mock:

```python
    @patch("musicvid.pipeline.assembler.VideoFileClip")
    def test_non_animated_mp4_uses_ken_burns(self, mock_vfc, tmp_path):
        """Non-animated .mp4 (stock video) should still get Ken Burns."""
        from musicvid.pipeline.assembler import _load_scene_clip

        fake_mp4 = tmp_path / "stock.mp4"
        fake_mp4.write_bytes(b"fake video")

        mock_clip = MagicMock()
        mock_clip.duration = 5.0
        mock_clip.size = (1920, 1080)
        mock_clip.w = 1920
        mock_clip.h = 1080
        mock_vfc.return_value = mock_clip
        mock_clip.subclipped.return_value = mock_clip
        mock_clip.resized.return_value = mock_clip
        mock_clip.cropped.return_value = mock_clip
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.transform.return_value = mock_clip

        scene = {"start": 0.0, "end": 5.0, "motion": "slow_zoom_in", "animate": False}
        _load_scene_clip(str(fake_mp4), scene, (1920, 1080))

        # transform (Ken Burns) SHOULD be called for non-animated video
        mock_clip.transform.assert_called()
```

- [ ] **Step 6: Update `TestPortraitKenBurns.test_pan_up_calls_transform` and `test_pan_down_calls_transform`**

Both tests call `_create_ken_burns_clip` directly without `size`, `w`, `h`, or `cropped` set. Update both:

```python
    def test_pan_up_calls_transform(self):
        from musicvid.pipeline.assembler import _create_ken_burns_clip
        from unittest.mock import MagicMock

        mock_clip = MagicMock()
        mock_clip.size = (1080, 1920)
        mock_clip.w = 1080
        mock_clip.h = 1920
        mock_clip.resized.return_value = mock_clip
        mock_clip.cropped.return_value = mock_clip
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.transform.return_value = mock_clip

        result = _create_ken_burns_clip(mock_clip, 5.0, "pan_up", (1080, 1920))

        mock_clip.transform.assert_called_once()

    def test_pan_down_calls_transform(self):
        from musicvid.pipeline.assembler import _create_ken_burns_clip
        from unittest.mock import MagicMock

        mock_clip = MagicMock()
        mock_clip.size = (1080, 1920)
        mock_clip.w = 1080
        mock_clip.h = 1920
        mock_clip.resized.return_value = mock_clip
        mock_clip.cropped.return_value = mock_clip
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.transform.return_value = mock_clip

        result = _create_ken_burns_clip(mock_clip, 5.0, "pan_down", (1080, 1920))

        mock_clip.transform.assert_called_once()
```

- [ ] **Step 7: Run cover scale tests to verify they pass**

```bash
python3 -m pytest tests/test_assembler.py::TestKenBurnsCoverScale tests/test_assembler.py::TestLoadSceneClipAnimated tests/test_assembler.py::TestPortraitKenBurns -v 2>&1 | tail -20
```

Expected: All PASS.

- [ ] **Step 8: Run full test suite to check for regressions**

```bash
python3 -m pytest tests/ -v 2>&1 | tail -30
```

Expected: All tests pass.

- [ ] **Step 9: Commit**

```bash
git add musicvid/pipeline/assembler.py tests/test_assembler.py
git commit -m "fix(assembler): cover-scale images in Ken Burns to fill frame without stretching"
```

---

## Task 3: Fix subtitle error handling

**Files:**
- Modify: `musicvid/pipeline/assembler.py:129-164` (`_create_subtitle_clips`)
- Test: `tests/test_assembler.py` (add new `TestSubtitleErrorHandling` class)

- [ ] **Step 1: Write the failing tests**

Add new test class at the end of `tests/test_assembler.py`:

```python
class TestSubtitleErrorHandling:
    """Tests for subtitle creation error handling."""

    @patch("musicvid.pipeline.assembler.vfx")
    @patch("musicvid.pipeline.assembler.TextClip")
    def test_textclip_error_skips_segment_without_crash(self, mock_text_clip, mock_vfx, sample_analysis, sample_scene_plan):
        """If TextClip raises, the segment is skipped and other segments still render."""
        mock_good_clip = MagicMock()
        mock_good_clip.with_duration.return_value = mock_good_clip
        mock_good_clip.with_start.return_value = mock_good_clip
        mock_good_clip.with_position.return_value = mock_good_clip
        mock_good_clip.with_effects.return_value = mock_good_clip

        # First segment raises, second succeeds
        mock_text_clip.side_effect = [Exception("ImageMagick failed"), mock_good_clip]

        subtitle_style = sample_scene_plan["subtitle_style"]
        clips = _create_subtitle_clips(
            sample_analysis["lyrics"],
            subtitle_style,
            (1920, 1080),
        )
        # Should get 1 clip (second segment), not crash
        assert len(clips) == 1

    @patch("musicvid.pipeline.assembler.vfx")
    @patch("musicvid.pipeline.assembler.TextClip")
    def test_empty_lyrics_returns_no_clips(self, mock_text_clip, mock_vfx, sample_scene_plan):
        """Empty lyrics list produces no clips and does not crash."""
        subtitle_style = sample_scene_plan["subtitle_style"]
        clips = _create_subtitle_clips([], subtitle_style, (1920, 1080))
        assert len(clips) == 0
        mock_text_clip.assert_not_called()

    @patch("musicvid.pipeline.assembler.vfx")
    @patch("musicvid.pipeline.assembler.TextClip")
    def test_subtitle_position_within_frame(self, mock_text_clip, mock_vfx, sample_analysis, sample_scene_plan):
        """Subtitle y-position must be less than frame height."""
        mock_clip = MagicMock()
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.with_start.return_value = mock_clip
        mock_clip.with_position.return_value = mock_clip
        mock_clip.with_effects.return_value = mock_clip
        mock_text_clip.return_value = mock_clip

        subtitle_style = sample_scene_plan["subtitle_style"]
        frame_h = 1080
        margin_bottom = 80
        font_size = subtitle_style.get("font_size", 58)
        _create_subtitle_clips(
            sample_analysis["lyrics"],
            subtitle_style,
            (1920, frame_h),
            subtitle_margin_bottom=margin_bottom,
        )

        # Check with_position was called with y < frame_h
        pos_call = mock_clip.with_position.call_args
        assert pos_call is not None
        args, kwargs = pos_call
        # Position is ("center", y_value)
        y_value = args[0][1]
        assert y_value < frame_h, f"Subtitle y={y_value} is outside frame height={frame_h}"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_assembler.py::TestSubtitleErrorHandling -v 2>&1 | tail -20
```

Expected: `test_textclip_error_skips_segment_without_crash` FAILS (exception propagates).

- [ ] **Step 3: Fix `_create_subtitle_clips` in assembler.py**

Replace the current implementation with:

```python
def _create_subtitle_clips(lyrics, subtitle_style, size, font_path=None, subtitle_margin_bottom=80):
    """Create subtitle TextClips from lyrics with word-level timing."""
    clips = []
    font_size = subtitle_style.get("font_size", 58)
    color = subtitle_style.get("color", "#FFFFFF")
    outline_color = subtitle_style.get("outline_color", "#000000")
    margin_bottom = subtitle_margin_bottom

    if not lyrics:
        print("Warning: no lyrics segments — subtitles skipped")
        return clips

    for segment in lyrics:
        duration = segment["end"] - segment["start"]
        if duration <= 0:
            continue

        print(f"Napis: '{segment['text']}' start={segment['start']:.1f}s end={segment['end']:.1f}s")

        y_pos = size[1] - margin_bottom - font_size
        if y_pos >= size[1]:
            print(f"Warning: subtitle y={y_pos} is outside frame height={size[1]}, clamping")
            y_pos = size[1] - font_size - 10

        effective_font = font_path
        try:
            txt_clip = TextClip(
                text=segment["text"],
                font_size=font_size,
                color=color,
                stroke_color=outline_color,
                stroke_width=2,
                font=effective_font,
                method="caption",
                size=(size[0] - 100, None),
            )
        except Exception as e:
            print(f"Warning: subtitle failed for '{segment['text']}' with font {effective_font!r}: {e}")
            if effective_font is not None:
                try:
                    txt_clip = TextClip(
                        text=segment["text"],
                        font_size=font_size,
                        color=color,
                        stroke_color=outline_color,
                        stroke_width=2,
                        font=None,
                        method="caption",
                        size=(size[0] - 100, None),
                    )
                except Exception as e2:
                    print(f"Warning: subtitle fallback also failed: {e2}")
                    continue
            else:
                continue

        txt_clip = txt_clip.with_duration(duration)
        txt_clip = txt_clip.with_start(segment["start"])
        txt_clip = txt_clip.with_position(("center", y_pos))

        fade_duration = min(0.3, duration / 3)
        txt_clip = txt_clip.with_effects([
            vfx.CrossFadeIn(fade_duration),
            vfx.CrossFadeOut(fade_duration),
        ])

        clips.append(txt_clip)

    return clips
```

- [ ] **Step 4: Run subtitle tests to verify they pass**

```bash
python3 -m pytest tests/test_assembler.py::TestSubtitleErrorHandling tests/test_assembler.py::TestCreateSubtitleClips -v 2>&1 | tail -20
```

Expected: All PASS.

- [ ] **Step 5: Run full test suite**

```bash
python3 -m pytest tests/ -v 2>&1 | tail -30
```

Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add musicvid/pipeline/assembler.py tests/test_assembler.py
git commit -m "fix(assembler): add subtitle try/except, logging, and font fallback"
```

---

## Self-Review

**Spec coverage:**
- Problem 1 (cinematic bars default off): ✅ Task 1 — default changed, CLI call-sites updated, tests verify bars off by default and on when `cinematic_bars=True`
- Problem 2 (cover scaling): ✅ Task 2 — `_create_ken_burns_clip` uses cover scale+crop; tests verify scalar `resized()` call and `cropped()` call
- Problem 3 (subtitle errors): ✅ Task 3 — try/except added, logging added, font fallback added, tests verify no crash on error
- Acceptance criteria `--effects minimal` and `--effects full` no bars by default: ✅ Task 1
- `python3 -m pytest tests/ -v` passes: ✅ each task ends with full suite run

**Placeholder scan:** No placeholders found — all steps have complete code.

**Type consistency:** `_create_subtitle_clips` signature unchanged; `assemble_video` signature changes only the default value of `cinematic_bars`; `_create_ken_burns_clip` signature unchanged.
