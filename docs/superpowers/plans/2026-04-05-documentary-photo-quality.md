# Documentary Photo Quality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace oversaturated AI-magic look with documentary/photojournalism aesthetic in all generated images and effects.

**Architecture:** Three-layer change — (1) BFL prompt construction in `image_generator.py` gets a documentary suffix and wider landscape dimensions, (2) `director_system.txt` gains new photographic banned words and documentary example prompts, (3) `effects.py` gains `apply_subtle_film_look()` (desaturation + subtle grain) wired into `apply_effects()` for minimal/full levels.

**Tech Stack:** Python, numpy (no new deps — cv2 NOT used; pure numpy desaturation instead), existing MoviePy `clip.transform()` pattern.

---

### Task 1: image_generator.py — documentary suffix + 1360×768 dimensions

**Files:**
- Modify: `musicvid/pipeline/image_generator.py`
- Modify: `tests/test_image_generator.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_image_generator.py` — three new test methods inside the existing classes:

```python
# Add inside class TestBFLFlowSubmitPollDownload:

@patch.dict(os.environ, {"BFL_API_KEY": "test-key"})
@patch("musicvid.pipeline.image_generator.requests")
def test_landscape_dimensions_are_1360x768(self, mock_requests, tmp_path):
    from musicvid.pipeline.image_generator import generate_images

    mock_requests.post.return_value = _make_post_response()
    mock_requests.get.side_effect = [
        _make_poll_response(),
        _make_download_response(),
    ]

    generate_images(ONE_SCENE_PLAN, str(tmp_path), provider="flux-dev")

    payload = mock_requests.post.call_args[1]["json"]
    assert payload["width"] == 1360
    assert payload["height"] == 768

@patch.dict(os.environ, {"BFL_API_KEY": "test-key"})
@patch("musicvid.pipeline.image_generator.requests")
def test_prompt_contains_documentary_suffix(self, mock_requests, tmp_path):
    from musicvid.pipeline.image_generator import generate_images

    mock_requests.post.return_value = _make_post_response()
    mock_requests.get.side_effect = [
        _make_poll_response(),
        _make_download_response(),
    ]

    generate_images(ONE_SCENE_PLAN, str(tmp_path))

    payload = mock_requests.post.call_args[1]["json"]
    assert "documentary photography style" in payload["prompt"]

@patch.dict(os.environ, {"BFL_API_KEY": "test-key"})
@patch("musicvid.pipeline.image_generator.requests")
def test_prompt_contains_negative_context(self, mock_requests, tmp_path):
    from musicvid.pipeline.image_generator import generate_images

    mock_requests.post.return_value = _make_post_response()
    mock_requests.get.side_effect = [
        _make_poll_response(),
        _make_download_response(),
    ]

    generate_images(ONE_SCENE_PLAN, str(tmp_path))

    payload = mock_requests.post.call_args[1]["json"]
    assert "natural light not artificial" in payload["prompt"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/s.rzytki/Documents/aiprojects/musicvideo && python3 -m pytest tests/test_image_generator.py::TestBFLFlowSubmitPollDownload::test_landscape_dimensions_are_1360x768 tests/test_image_generator.py::TestBFLFlowSubmitPollDownload::test_prompt_contains_documentary_suffix tests/test_image_generator.py::TestBFLFlowSubmitPollDownload::test_prompt_contains_negative_context -v
```

Expected: FAIL (dimensions still 1024, no documentary suffix in prompt)

- [ ] **Step 3: Also update the existing dimensions test that currently asserts 1024**

In `tests/test_image_generator.py`, the test `test_submit_uses_correct_model_and_params` asserts:
```python
assert payload["width"] == 1024
assert payload["height"] == 768
```

Change those two assertions to:
```python
assert payload["width"] == 1360
assert payload["height"] == 768
```

- [ ] **Step 4: Implement the changes in image_generator.py**

In `musicvid/pipeline/image_generator.py`, add two module-level constants after the existing constants block (after `POLL_TIMEOUT = 120`):

```python
DOCUMENTARY_SUFFIX = (
    "documentary photography style, authentic and unposed, "
    "natural available light only, film grain, natural color grading, "
    "real location feel, photojournalism aesthetic"
)

NEGATIVE_CONTEXT = (
    "no Catholic imagery, no religious figures, no rosary, no crucifix, "
    "no saints, natural light not artificial, authentic not staged, "
    "film grain not oversaturated"
)
```

In `generate_images()`, change the landscape dimensions line from:
```python
img_w, img_h = (768, 1360) if is_portrait else (1024, 768)
```
to:
```python
img_w, img_h = (768, 1360) if is_portrait else (1360, 768)
```

Change the prompt construction block from:
```python
        if master_style:
            full_prompt = f"{visual_prompt}, {master_style}, {orientation_hint}, photorealistic, high quality"
        else:
            full_prompt = f"{visual_prompt}, {orientation_hint}, photorealistic, high quality"
```
to:
```python
        if master_style:
            full_prompt = f"{visual_prompt}, {master_style}, {orientation_hint}, {DOCUMENTARY_SUFFIX}, {NEGATIVE_CONTEXT}"
        else:
            full_prompt = f"{visual_prompt}, {orientation_hint}, {DOCUMENTARY_SUFFIX}, {NEGATIVE_CONTEXT}"
```

- [ ] **Step 5: Run all image_generator tests to verify they pass**

```bash
cd /Users/s.rzytki/Documents/aiprojects/musicvideo && python3 -m pytest tests/test_image_generator.py -v
```

Expected: All tests PASS (the old 1024 dimension test now expects 1360)

- [ ] **Step 6: Commit**

```bash
cd /Users/s.rzytki/Documents/aiprojects/musicvideo && git add tests/test_image_generator.py musicvid/pipeline/image_generator.py && git commit -m "feat: add documentary suffix and 1360x768 dimensions to BFL image generator"
```

---

### Task 2: director_system.txt — photographic banned words + documentary examples

**Files:**
- Modify: `musicvid/prompts/director_system.txt`

There are no automated tests for the director system prompt content (it's a text file used as a system prompt). The verification is visual inspection and the test from the spec is covered at the image_generator level (prompts sent to BFL must contain documentary style — already covered in Task 1). No test file changes needed for this task.

- [ ] **Step 1: Add photographic banned words to the BANNED WORDS section**

In `musicvid/prompts/director_system.txt`, after the existing BANNED WORDS section (after `shrine, altar, candle altar, sacred heart, IHS`), add:

Replace the entire BANNED WORDS block:
```
BANNED WORDS (never use these in any visual_prompt):
Catholic, rosary, Madonna, saint, cross with figure, stained glass,
church interior, religious, icon, Byzantine, papal, crucifix,
prayer beads, Maria, monastery, monk, nun, cathedral, chapel,
shrine, altar, candle altar, sacred heart, IHS
```

With:
```
BANNED WORDS (never use these in any visual_prompt):
Catholic, rosary, Madonna, saint, cross with figure, stained glass,
church interior, religious, icon, Byzantine, papal, crucifix,
prayer beads, Maria, monastery, monk, nun, cathedral, chapel,
shrine, altar, candle altar, sacred heart, IHS,
magical, mystical, ethereal, dreamy, fantasy, otherworldly,
glowing, radiant glow, divine light rays, heavenly glow,
surreal, cinematic fantasy, epic, majestic,
bokeh everywhere, heavy bokeh, extreme bokeh,
oversaturated, vivid colors, vibrant, ultra sharp,
perfect lighting, studio lighting, professional lighting,
HDR, ultra-realistic, 8K, ultra HD, hyper-detailed
```

- [ ] **Step 2: Update the MASTER STYLE section**

Replace the existing MASTER STYLE example in the prompt:
```
Example: "Consistent warm cinematic color grade, golden amber tones, soft atmospheric
haze, photorealistic photography style." Include it as the master_style field in your JSON output.
```

With:
```
Example: "Documentary worship photography aesthetic. Natural available light, film grain present, colors slightly desaturated and warm, authentic unposed moments, Sony A7III 35mm feel, no artificial enhancements, real and human." Include it as the master_style field in your JSON output.
```

- [ ] **Step 3: Replace the EXAMPLE PROMPTS section with documentary-style examples**

Replace the two existing examples:
```
EXAMPLE PROMPTS (follow this style):
- "A lone silhouette stands on a vast rocky cliff overlooking an infinite ocean at golden hour, arms raised toward dramatic storm clouds breaking into light. Wide shot, warm amber light from below the horizon, shallow depth of field with the figure sharp against a blurred sky, conveying human smallness before the divine. Warm cinematic grade, golden tones, photorealistic, cinematic 16:9, high quality"
- "Golden wheat field stretching to the horizon at sunrise, a narrow dirt path leads into the distance. Medium wide shot, soft warm light rakes across the field casting long shadows, morning mist lingers in the background valleys, peaceful and full of hope. Warm cinematic grade, golden tones, photorealistic, cinematic 16:9, high quality"
```

With:
```
EXAMPLE PROMPTS (follow this style — documentary realism, not AI fantasy):
- "Person sitting alone on wooden dock overlooking misty lake at dawn, back to camera, legs over water, complete stillness. Documentary style, natural morning light, slight mist on water, authentic solitude and trust. Sony A7III 35mm, film grain"
- "Vast open meadow at golden hour, single figure walking in distance, long grass in wind. Wide establishing shot, natural colors, documentary landscape photography, real weather, no filters"
- "Rocky mountain path at dusk, dramatic but real clouds, lone figure on path seen from behind. Photojournalism style, available light only, natural shadows"
- "Outdoor worship gathering at sunset, people with hands raised, wide shot showing community. Documentary photography, warm natural backlight, authentic emotion, no staging"
```

- [ ] **Step 4: Update the PROMPT BUILDING RULES section**

Replace:
```
Every visual_prompt ends with the master_style condensed + "cinematic 16:9, photorealistic, high quality"
```

With:
```
Every visual_prompt ends with the master_style condensed + "documentary photography style, cinematic 16:9"
Avoid: magical, mystical, ethereal, glowing, bokeh everywhere, HDR, 8K, oversaturated, perfect lighting
Use: documentary style, natural light, authentic, candid, photojournalism aesthetic
```

- [ ] **Step 5: Commit**

```bash
cd /Users/s.rzytki/Documents/aiprojects/musicvideo && git add musicvid/prompts/director_system.txt && git commit -m "feat: update director prompt with documentary style and photographic banned words"
```

---

### Task 3: effects.py — apply_subtle_film_look()

**Files:**
- Modify: `musicvid/pipeline/effects.py`
- Modify: `tests/test_effects.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_effects.py`:

```python
# At the top, add import:
from musicvid.pipeline.effects import apply_subtle_film_look

# Add new test class at the end of the file:

class TestApplySubtleFilmLook:
    """Tests for subtle film look (desaturation + grain)."""

    def test_reduces_saturation(self):
        """Output should have lower saturation than fully saturated input."""
        # Create a purely red frame (max saturation)
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        frame[:, :, 0] = 200  # R
        frame[:, :, 1] = 50   # G
        frame[:, :, 2] = 50   # B

        mock_clip = MagicMock()
        mock_clip.transform.return_value = mock_clip

        apply_subtle_film_look(mock_clip)

        transform_fn = mock_clip.transform.call_args[0][0]
        get_frame = lambda t: frame.copy()

        np.random.seed(42)
        output = transform_fn(get_frame, 0)

        # Saturation = chroma / max. After desaturation, R-G gap should shrink
        orig_chroma = int(frame[0, 0, 0]) - int(frame[0, 0, 1])  # 150
        out_chroma = int(output[0, 0, 0]) - int(output[0, 0, 1])
        assert out_chroma < orig_chroma, (
            f"Output chroma {out_chroma} should be less than input chroma {orig_chroma}"
        )

    def test_desaturation_is_subtle(self):
        """Only ~8% saturation reduction — channels should stay close to original."""
        frame = np.full((100, 100, 3), 128, dtype=np.uint8)
        frame[:, :, 0] = 200  # skew red channel

        mock_clip = MagicMock()
        mock_clip.transform.return_value = mock_clip

        apply_subtle_film_look(mock_clip)

        transform_fn = mock_clip.transform.call_args[0][0]
        get_frame = lambda t: frame.copy()

        np.random.seed(42)
        output = transform_fn(get_frame, 0)

        # Mean pixel value should be close to original (within 15 per channel)
        diff = np.abs(output.astype(int) - frame.astype(int))
        assert diff.mean() < 15, f"Film look too aggressive: mean diff {diff.mean()}"

    def test_returns_clip(self):
        """apply_subtle_film_look returns a clip (result of clip.transform)."""
        mock_clip = MagicMock()
        mock_clip.transform.return_value = mock_clip

        result = apply_subtle_film_look(mock_clip)

        assert result is mock_clip
        mock_clip.transform.assert_called_once()


class TestApplyEffectsWithFilmLook:
    """Tests that apply_effects includes subtle_film_look for minimal and full."""

    @patch("musicvid.pipeline.effects.apply_subtle_film_look")
    @patch("musicvid.pipeline.effects.apply_vignette")
    @patch("musicvid.pipeline.effects.apply_warm_grade")
    def test_minimal_applies_film_look(self, mock_warm, mock_vignette, mock_film):
        """Level 'minimal' applies warm grade, vignette, and subtle film look."""
        mock_clip = MagicMock()
        mock_warm.return_value = mock_clip
        mock_vignette.return_value = mock_clip
        mock_film.return_value = mock_clip

        apply_effects(mock_clip, level="minimal")

        mock_warm.assert_called_once()
        mock_vignette.assert_called_once()
        mock_film.assert_called_once()

    @patch("musicvid.pipeline.effects.apply_film_grain")
    @patch("musicvid.pipeline.effects.apply_subtle_film_look")
    @patch("musicvid.pipeline.effects.apply_vignette")
    @patch("musicvid.pipeline.effects.apply_warm_grade")
    def test_full_applies_film_look_and_grain(self, mock_warm, mock_vignette, mock_film, mock_grain):
        """Level 'full' applies all including subtle film look and film grain."""
        mock_clip = MagicMock()
        mock_warm.return_value = mock_clip
        mock_vignette.return_value = mock_clip
        mock_film.return_value = mock_clip
        mock_grain.return_value = mock_clip

        apply_effects(mock_clip, level="full")

        mock_warm.assert_called_once()
        mock_vignette.assert_called_once()
        mock_film.assert_called_once()
        mock_grain.assert_called_once()

    @patch("musicvid.pipeline.effects.apply_subtle_film_look")
    @patch("musicvid.pipeline.effects.apply_vignette")
    @patch("musicvid.pipeline.effects.apply_warm_grade")
    def test_none_skips_film_look(self, mock_warm, mock_vignette, mock_film):
        """Level 'none' does not apply subtle film look."""
        mock_clip = MagicMock()

        apply_effects(mock_clip, level="none")

        mock_film.assert_not_called()
        mock_warm.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/s.rzytki/Documents/aiprojects/musicvideo && python3 -m pytest tests/test_effects.py::TestApplySubtleFilmLook tests/test_effects.py::TestApplyEffectsWithFilmLook -v
```

Expected: FAIL (`apply_subtle_film_look` not defined, existing TestApplyEffects tests about minimal will also fail)

- [ ] **Step 3: Update existing tests that will break due to minimal now including film look**

In `tests/test_effects.py`, the existing `test_minimal_applies_warm_and_vignette` test will now be incomplete (minimal also calls subtle_film_look). Update it to also expect `apply_subtle_film_look`:

Replace:
```python
    @patch("musicvid.pipeline.effects.apply_vignette")
    @patch("musicvid.pipeline.effects.apply_warm_grade")
    def test_minimal_applies_warm_and_vignette(self, mock_warm, mock_vignette):
        """Level 'minimal' should apply warm grade and vignette."""
        mock_clip = MagicMock()
        mock_warm.return_value = mock_clip
        mock_vignette.return_value = mock_clip

        apply_effects(mock_clip, level="minimal")

        mock_warm.assert_called_once_with(mock_clip)
        mock_vignette.assert_called_once()
```

With:
```python
    @patch("musicvid.pipeline.effects.apply_subtle_film_look")
    @patch("musicvid.pipeline.effects.apply_vignette")
    @patch("musicvid.pipeline.effects.apply_warm_grade")
    def test_minimal_applies_warm_and_vignette(self, mock_warm, mock_vignette, mock_film):
        """Level 'minimal' should apply warm grade, vignette, and subtle film look."""
        mock_clip = MagicMock()
        mock_warm.return_value = mock_clip
        mock_vignette.return_value = mock_clip
        mock_film.return_value = mock_clip

        apply_effects(mock_clip, level="minimal")

        mock_warm.assert_called_once_with(mock_clip)
        mock_vignette.assert_called_once()
        mock_film.assert_called_once()
```

Also update `test_full_applies_all_frame_effects` to include subtle_film_look:

Replace:
```python
    @patch("musicvid.pipeline.effects.apply_film_grain")
    @patch("musicvid.pipeline.effects.apply_vignette")
    @patch("musicvid.pipeline.effects.apply_warm_grade")
    def test_full_applies_all_frame_effects(self, mock_warm, mock_vignette, mock_grain):
        """Level 'full' should apply warm grade, vignette, and film grain."""
        mock_clip = MagicMock()
        mock_warm.return_value = mock_clip
        mock_vignette.return_value = mock_clip
        mock_grain.return_value = mock_clip

        apply_effects(mock_clip, level="full")

        mock_warm.assert_called_once()
        mock_vignette.assert_called_once()
        mock_grain.assert_called_once()
```

With:
```python
    @patch("musicvid.pipeline.effects.apply_film_grain")
    @patch("musicvid.pipeline.effects.apply_subtle_film_look")
    @patch("musicvid.pipeline.effects.apply_vignette")
    @patch("musicvid.pipeline.effects.apply_warm_grade")
    def test_full_applies_all_frame_effects(self, mock_warm, mock_vignette, mock_film, mock_grain):
        """Level 'full' should apply warm grade, vignette, subtle film look, and film grain."""
        mock_clip = MagicMock()
        mock_warm.return_value = mock_clip
        mock_vignette.return_value = mock_clip
        mock_film.return_value = mock_clip
        mock_grain.return_value = mock_clip

        apply_effects(mock_clip, level="full")

        mock_warm.assert_called_once()
        mock_vignette.assert_called_once()
        mock_film.assert_called_once()
        mock_grain.assert_called_once()
```

Also update `test_default_level_is_minimal` to also mock `apply_subtle_film_look`:

Replace:
```python
    def test_default_level_is_minimal(self):
        """Default level should be 'minimal'."""
        mock_clip = MagicMock()
        mock_clip.transform.return_value = mock_clip

        with patch("musicvid.pipeline.effects.apply_warm_grade", return_value=mock_clip) as mock_warm, \
             patch("musicvid.pipeline.effects.apply_vignette", return_value=mock_clip):
            apply_effects(mock_clip)
            mock_warm.assert_called_once()
```

With:
```python
    def test_default_level_is_minimal(self):
        """Default level should be 'minimal'."""
        mock_clip = MagicMock()
        mock_clip.transform.return_value = mock_clip

        with patch("musicvid.pipeline.effects.apply_warm_grade", return_value=mock_clip) as mock_warm, \
             patch("musicvid.pipeline.effects.apply_vignette", return_value=mock_clip), \
             patch("musicvid.pipeline.effects.apply_subtle_film_look", return_value=mock_clip):
            apply_effects(mock_clip)
            mock_warm.assert_called_once()
```

- [ ] **Step 4: Implement apply_subtle_film_look in effects.py**

In `musicvid/pipeline/effects.py`, add after `apply_film_grain` (before `create_light_leak`):

```python
def apply_subtle_film_look(clip):
    """Apply subtle film look: -8% saturation desaturation + very subtle grain (sigma=4, opacity=0.08).

    Uses luminance-weighted desaturation (no cv2 required).
    """
    def _film_look(get_frame, t):
        frame = get_frame(t).astype(np.float32)
        # Luminance channel (grayscale) for desaturation blend
        gray = (
            0.299 * frame[:, :, 0]
            + 0.587 * frame[:, :, 1]
            + 0.114 * frame[:, :, 2]
        )[:, :, np.newaxis]
        # -8% saturation: blend 92% original + 8% gray
        result = 0.92 * frame + 0.08 * gray
        # Very subtle grain: sigma=4, opacity=0.08
        noise = np.random.normal(0, 4, frame.shape).astype(np.float32)
        result = result + noise * 0.08
        return np.clip(result, 0, 255).astype(np.uint8)
    return clip.transform(_film_look)
```

In `apply_effects()`, add the call after `apply_vignette` for both minimal and full:

Replace the entire `apply_effects` function body:
```python
def apply_effects(clip, level="minimal"):
    """Apply visual effects based on level.

    Args:
        clip: MoviePy clip (after Ken Burns, before subtitles).
        level: "none" | "minimal" | "full"

    Returns:
        Processed clip.
    """
    if level == "none":
        return clip

    clip = apply_warm_grade(clip)
    clip = apply_vignette(clip)

    if level == "full":
        clip = apply_film_grain(clip)

    return clip
```

With:
```python
def apply_effects(clip, level="minimal"):
    """Apply visual effects based on level.

    Args:
        clip: MoviePy clip (after Ken Burns, before subtitles).
        level: "none" | "minimal" | "full"

    Returns:
        Processed clip.
    """
    if level == "none":
        return clip

    clip = apply_warm_grade(clip)
    clip = apply_vignette(clip)
    clip = apply_subtle_film_look(clip)

    if level == "full":
        clip = apply_film_grain(clip)

    return clip
```

- [ ] **Step 5: Run all effects tests to verify they pass**

```bash
cd /Users/s.rzytki/Documents/aiprojects/musicvideo && python3 -m pytest tests/test_effects.py -v
```

Expected: All tests PASS

- [ ] **Step 6: Run the full test suite to confirm nothing is broken**

```bash
cd /Users/s.rzytki/Documents/aiprojects/musicvideo && python3 -m pytest tests/ -v
```

Expected: All tests PASS (check total count is consistent with prior run)

- [ ] **Step 7: Commit**

```bash
cd /Users/s.rzytki/Documents/aiprojects/musicvideo && git add musicvid/pipeline/effects.py tests/test_effects.py && git commit -m "feat: add apply_subtle_film_look for documentary desaturation and grain"
```

---

## Self-Review

### Spec Coverage Check

| Spec requirement | Task |
|---|---|
| Change dimensions 1024×768 → 1360×768 | Task 1 |
| Add documentary suffix to every BFL prompt | Task 1 |
| Add negative context (no Catholic imagery, natural light, etc.) | Task 1 |
| Add photographic banned words to director prompt | Task 2 |
| Update director example prompts to documentary style | Task 2 |
| Update master_style to documentary aesthetic | Task 2 |
| `subtle_film_look()` in effects.py (desaturation + subtle grain) | Task 3 |
| `apply_effects()` calls it for minimal and full (not none) | Task 3 |
| `test_documentary_suffix` — prompt contains "documentary photography style" | Task 1 |
| `test_dimensions` — BFL request has width=1360, height=768 | Task 1 |
| `test_film_look` — subtle_film_look() reduces saturation | Task 3 |
| `test_no_banned_words` — for photographic words at director level | Task 2 (documented; enforced at director level via system prompt, not code) |

### Notes

- `visual_bible.py` does not exist in the codebase — its content (master_style) lives in `director_system.txt`, updated in Task 2.
- The `--effects none` path is untouched — `subtle_film_look` is NOT called when effects=none.
- Portrait dimensions (768×1360 for reels) are unchanged — only landscape changed from 1024→1360.
- cv2 is NOT used in effects.py — pure numpy luminance desaturation is equivalent and avoids dependency issues.
- Existing `test_submit_uses_correct_model_and_params` must be updated (1024→1360) in Task 1 Step 3.
