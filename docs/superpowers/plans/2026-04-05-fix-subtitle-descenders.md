# Fix Subtitle Descender Clipping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add bottom padding to subtitle TextClips so descender letters (j, g, y, p, q, ą, ę) are never clipped at the bottom edge.

**Architecture:** Modify `_create_subtitle_clips` in `assembler.py` to explicitly set TextClip height to `font_size + 35%` and adjust the `y_pos` calculation so the padded clip's bottom edge sits at `margin_bottom` pixels from the frame bottom.

**Tech Stack:** Python 3.11, MoviePy 2.1.2, ImageMagick (via TextClip)

---

### Task 1: Fix descender clipping in `_create_subtitle_clips`

**Files:**
- Modify: `musicvid/pipeline/assembler.py:138-206`
- Test: `tests/test_assembler.py` (add tests to `TestCreateSubtitleClips`)

**Context:**
- `_create_subtitle_clips` is defined at line 138 of `musicvid/pipeline/assembler.py`
- It creates MoviePy `TextClip` objects for each lyric segment
- Current issue: `size=(size[0] - 100, None)` — height is auto-calculated by ImageMagick which omits descender space
- Current `y_pos = size[1] - margin_bottom - font_size` positions top of clip so baseline sits at `margin_bottom` from bottom
- Fix: set explicit height `font_size + int(font_size * 0.35)` and adjust `y_pos` accordingly
- Both the primary `TextClip` call (line 164) and the fallback `TextClip` call (line 178) must be updated
- Test file imports `_create_subtitle_clips` directly — tests go in `class TestCreateSubtitleClips`
- Tests mock `TextClip` with `@patch("musicvid.pipeline.assembler.TextClip")` and `vfx` with `@patch("musicvid.pipeline.assembler.vfx")`
- `sample_analysis` fixture has `lyrics` with at least 2 segments; `sample_scene_plan` fixture has `subtitle_style` dict with `font_size: 58`

- [ ] **Step 1: Write the failing tests**

Add these two tests to `class TestCreateSubtitleClips` in `tests/test_assembler.py`:

```python
@patch("musicvid.pipeline.assembler.vfx")
@patch("musicvid.pipeline.assembler.TextClip")
def test_textclip_height_includes_descender_padding(self, mock_text_clip, mock_vfx, sample_analysis, sample_scene_plan):
    """TextClip height must be font_size + 35% to accommodate descenders."""
    mock_clip = MagicMock()
    mock_clip.with_duration.return_value = mock_clip
    mock_clip.with_start.return_value = mock_clip
    mock_clip.with_position.return_value = mock_clip
    mock_clip.with_effects.return_value = mock_clip
    mock_text_clip.return_value = mock_clip

    subtitle_style = {"font_size": 58, "color": "#FFFFFF", "outline_color": "#000000"}
    _create_subtitle_clips(
        sample_analysis["lyrics"],
        subtitle_style,
        (1920, 1080),
    )

    call_kwargs = mock_text_clip.call_args_list[0][1]
    w, h = call_kwargs["size"]
    font_size = 58
    expected_h = font_size + int(font_size * 0.35)
    assert h == expected_h, f"Expected TextClip height={expected_h}, got {h}"

@patch("musicvid.pipeline.assembler.vfx")
@patch("musicvid.pipeline.assembler.TextClip")
def test_subtitle_y_pos_accounts_for_descender_padding(self, mock_text_clip, mock_vfx, sample_analysis, sample_scene_plan):
    """Subtitle bottom edge (y_pos + padded_height) equals frame_h - margin_bottom."""
    mock_clip = MagicMock()
    mock_clip.with_duration.return_value = mock_clip
    mock_clip.with_start.return_value = mock_clip
    mock_clip.with_position.return_value = mock_clip
    mock_clip.with_effects.return_value = mock_clip
    mock_text_clip.return_value = mock_clip

    font_size = 58
    frame_h = 1080
    margin_bottom = 80
    subtitle_style = {"font_size": font_size, "color": "#FFFFFF", "outline_color": "#000000"}
    _create_subtitle_clips(
        sample_analysis["lyrics"],
        subtitle_style,
        (1920, frame_h),
        subtitle_margin_bottom=margin_bottom,
    )

    pos_call = mock_clip.with_position.call_args_list[0]
    args, _ = pos_call
    y_pos = args[0][1]
    padded_h = font_size + int(font_size * 0.35)
    assert y_pos + padded_h == frame_h - margin_bottom, (
        f"Expected y_pos + padded_h = {frame_h - margin_bottom}, got {y_pos + padded_h}"
    )
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/s.rzytki/Documents/aiprojects/musicvideo
python3 -m pytest tests/test_assembler.py::TestCreateSubtitleClips::test_textclip_height_includes_descender_padding tests/test_assembler.py::TestCreateSubtitleClips::test_subtitle_y_pos_accounts_for_descender_padding -v
```

Expected: FAIL — both tests fail because current code uses `None` for height and doesn't include descender padding.

- [ ] **Step 3: Implement the fix in `assembler.py`**

In `_create_subtitle_clips` (line 138), make these changes:

1. After `margin_bottom = subtitle_margin_bottom` (line 144), add:
   ```python
   descender_pad = int(font_size * 0.35)
   padded_height = font_size + descender_pad
   ```

2. Change the `y_pos` calculation (line 157) from:
   ```python
   y_pos = size[1] - margin_bottom - font_size
   ```
   to:
   ```python
   y_pos = size[1] - margin_bottom - padded_height
   ```

3. Change the primary `TextClip` call `size` argument (line 172) from:
   ```python
   size=(size[0] - 100, None),
   ```
   to:
   ```python
   size=(size[0] - 100, padded_height),
   ```

4. Change the fallback `TextClip` call `size` argument (line 186) from:
   ```python
   size=(size[0] - 100, None),
   ```
   to:
   ```python
   size=(size[0] - 100, padded_height),
   ```

The resulting `_create_subtitle_clips` function from line 138 to 206 should look like:

```python
def _create_subtitle_clips(lyrics, subtitle_style, size, font_path=None, subtitle_margin_bottom=80):
    """Create subtitle TextClips from lyrics with word-level timing."""
    clips = []
    font_size = subtitle_style.get("font_size", 58)
    color = subtitle_style.get("color", "#FFFFFF")
    outline_color = subtitle_style.get("outline_color", "#000000")
    margin_bottom = subtitle_margin_bottom
    descender_pad = int(font_size * 0.35)
    padded_height = font_size + descender_pad

    if not lyrics:
        print("Warning: no lyrics segments — subtitles skipped")
        return clips

    for segment in lyrics:
        duration = segment["end"] - segment["start"]
        if duration <= 0:
            continue

        print(f"Napis: '{segment['text']}' start={segment['start']:.1f}s end={segment['end']:.1f}s")

        y_pos = size[1] - margin_bottom - padded_height
        if y_pos >= size[1]:
            print(f"Warning: subtitle y={y_pos} is outside frame height={size[1]}, clamping")
            y_pos = size[1] - padded_height - 10

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
                size=(size[0] - 100, padded_height),
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
                        size=(size[0] - 100, padded_height),
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

- [ ] **Step 4: Run the new tests to verify they pass**

```bash
python3 -m pytest tests/test_assembler.py::TestCreateSubtitleClips::test_textclip_height_includes_descender_padding tests/test_assembler.py::TestCreateSubtitleClips::test_subtitle_y_pos_accounts_for_descender_padding -v
```

Expected: PASS

- [ ] **Step 5: Run the full test suite to verify no regressions**

```bash
python3 -m pytest tests/ -v
```

Expected: All tests pass (was ~297 tests before this change).

- [ ] **Step 6: Commit**

```bash
git add musicvid/pipeline/assembler.py tests/test_assembler.py
git commit -m "fix: add descender padding to subtitle TextClips to prevent j/g/y/p/q clipping"
```
