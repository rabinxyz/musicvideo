# Fix Subtitle Overflow on Social Reels — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix subtitles on 9:16 social reels that wrap to a second line and overflow below the visible screen area.

**Architecture:** All changes are in `_create_subtitle_clips()` in `assembler.py`. Add a `wrap_for_portrait()` helper, cap font size at 52px for reels, set subtitle width to 900px, compute multiline y-position, and enforce a 10%-85% safe zone. Tests in `test_assembler.py`.

**Tech Stack:** Python, MoviePy 2.x (TextClip with `method="caption"`), unittest.mock

---

### Task 1: Add `wrap_for_portrait` helper and tests

**Files:**
- Modify: `musicvid/pipeline/assembler.py` (add function before `_create_subtitle_clips` at ~line 403)
- Modify: `tests/test_assembler.py` (add new test class)

- [ ] **Step 1: Write the failing tests**

Add at the end of `tests/test_assembler.py`:

```python
class TestWrapForPortrait(unittest.TestCase):
    def test_short_text_no_wrap(self):
        from musicvid.pipeline.assembler import wrap_for_portrait
        result = wrap_for_portrait("Alleluja", max_chars=25)
        assert result == "Alleluja"

    def test_long_text_wraps_to_two_lines(self):
        from musicvid.pipeline.assembler import wrap_for_portrait
        result = wrap_for_portrait("Panie Boże prowadź mnie dalej", max_chars=25)
        lines = result.split("\n")
        assert len(lines) == 2
        for line in lines:
            assert len(line) <= 25

    def test_exact_boundary_no_wrap(self):
        from musicvid.pipeline.assembler import wrap_for_portrait
        # 25 chars exactly
        result = wrap_for_portrait("abcde fghij klmno pqrst", max_chars=25)
        assert "\n" not in result

    def test_single_long_word_not_broken(self):
        from musicvid.pipeline.assembler import wrap_for_portrait
        result = wrap_for_portrait("Superdługiesłowopolskie", max_chars=25)
        assert result == "Superdługiesłowopolskie"

    def test_multiple_wraps(self):
        from musicvid.pipeline.assembler import wrap_for_portrait
        result = wrap_for_portrait("Jeden dwa trzy cztery pięć sześć siedem osiem", max_chars=15)
        lines = result.split("\n")
        assert len(lines) >= 3
        for line in lines:
            assert len(line) <= 15
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_assembler.py::TestWrapForPortrait -v`
Expected: FAIL with `ImportError: cannot import name 'wrap_for_portrait'`

- [ ] **Step 3: Implement `wrap_for_portrait`**

Add in `musicvid/pipeline/assembler.py` right before `def _create_subtitle_clips(` (around line 403):

```python
def wrap_for_portrait(text, max_chars=25):
    """Wrap text for portrait mode — max_chars per line, word-level breaks."""
    words = text.split()
    lines = []
    current = []
    current_len = 0
    for word in words:
        if current_len + len(word) + 1 > max_chars and current:
            lines.append(" ".join(current))
            current = [word]
            current_len = len(word)
        else:
            current.append(word)
            current_len += len(word) + 1
    if current:
        lines.append(" ".join(current))
    return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_assembler.py::TestWrapForPortrait -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add musicvid/pipeline/assembler.py tests/test_assembler.py
git commit -m "feat: add wrap_for_portrait helper for subtitle text wrapping"
```

---

### Task 2: Cap font size at 52px for reels and set subtitle width to 900px

**Files:**
- Modify: `musicvid/pipeline/assembler.py:428-448` (inside `_create_subtitle_clips`)
- Modify: `tests/test_assembler.py` (update existing test, add new tests)

- [ ] **Step 1: Write the failing tests**

Add at the end of `tests/test_assembler.py`:

```python
class TestReelsSubtitleWidth(unittest.TestCase):
    @patch("musicvid.pipeline.assembler.vfx")
    @patch("musicvid.pipeline.assembler.TextClip")
    def test_reels_subtitle_width_900(self, mock_textclip, mock_vfx):
        from musicvid.pipeline.assembler import _create_subtitle_clips

        mock_clip = MagicMock()
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.with_start.return_value = mock_clip
        mock_clip.with_position.return_value = mock_clip
        mock_clip.with_effects.return_value = mock_clip
        mock_clip.transform.return_value = mock_clip
        mock_textclip.return_value = mock_clip

        lyrics = [{"start": 1.0, "end": 3.0, "text": "Test", "words": []}]
        style = {"color": "#FFFFFF", "outline_color": "#000000"}

        _create_subtitle_clips(lyrics, style, (1080, 1920), reels_mode=True)

        call_kwargs = mock_textclip.call_args[1]
        width = call_kwargs["size"][0]
        assert width == 900, f"Expected 900, got {width}"

    @patch("musicvid.pipeline.assembler.vfx")
    @patch("musicvid.pipeline.assembler.TextClip")
    def test_landscape_subtitle_width_unchanged(self, mock_textclip, mock_vfx):
        from musicvid.pipeline.assembler import _create_subtitle_clips

        mock_clip = MagicMock()
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.with_start.return_value = mock_clip
        mock_clip.with_position.return_value = mock_clip
        mock_clip.with_effects.return_value = mock_clip
        mock_textclip.return_value = mock_clip

        lyrics = [{"start": 1.0, "end": 3.0, "text": "Test", "words": []}]
        style = {"color": "#FFFFFF", "outline_color": "#000000"}

        _create_subtitle_clips(lyrics, style, (1920, 1080), reels_mode=False)

        call_kwargs = mock_textclip.call_args[1]
        width = call_kwargs["size"][0]
        assert width == 1920 - 100, f"Expected 1820, got {width}"


class TestReelsFontSizeCap(unittest.TestCase):
    @patch("musicvid.pipeline.assembler.vfx")
    @patch("musicvid.pipeline.assembler.TextClip")
    def test_chorus_font_capped_at_52_in_reels(self, mock_textclip, mock_vfx):
        from musicvid.pipeline.assembler import _create_subtitle_clips

        mock_clip = MagicMock()
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.with_start.return_value = mock_clip
        mock_clip.with_position.return_value = mock_clip
        mock_clip.with_effects.return_value = mock_clip
        mock_clip.transform.return_value = mock_clip
        mock_textclip.return_value = mock_clip

        lyrics = [{"start": 10.0, "end": 12.0, "text": "Alleluja", "words": []}]
        style = {"color": "#FFFFFF", "outline_color": "#000000"}
        sections = [{"label": "chorus", "start": 8.0, "end": 20.0}]

        _create_subtitle_clips(lyrics, style, (1080, 1920),
                               sections=sections, reels_mode=True)

        call_kwargs = mock_textclip.call_args[1]
        assert call_kwargs["font_size"] <= 52, f"Expected <=52, got {call_kwargs['font_size']}"

    @patch("musicvid.pipeline.assembler.vfx")
    @patch("musicvid.pipeline.assembler.TextClip")
    def test_verse_font_capped_at_52_in_reels(self, mock_textclip, mock_vfx):
        from musicvid.pipeline.assembler import _create_subtitle_clips

        mock_clip = MagicMock()
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.with_start.return_value = mock_clip
        mock_clip.with_position.return_value = mock_clip
        mock_clip.with_effects.return_value = mock_clip
        mock_textclip.return_value = mock_clip

        lyrics = [{"start": 1.0, "end": 3.0, "text": "Test", "words": []}]
        style = {"color": "#FFFFFF", "outline_color": "#000000"}
        sections = [{"label": "verse", "start": 0.0, "end": 10.0}]

        _create_subtitle_clips(lyrics, style, (1080, 1920),
                               sections=sections, reels_mode=True)

        call_kwargs = mock_textclip.call_args[1]
        assert call_kwargs["font_size"] <= 52, f"Expected <=52, got {call_kwargs['font_size']}"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_assembler.py::TestReelsSubtitleWidth tests/test_assembler.py::TestReelsFontSizeCap -v`
Expected: FAIL — width is 980 instead of 900, font_size is 72 instead of <=52

- [ ] **Step 3: Implement font size cap and width changes**

In `musicvid/pipeline/assembler.py`, modify `_create_subtitle_clips`. Replace lines 428-429:

```python
        if reels_mode and section == "chorus":
            font_size = 72
```

With:

```python
        if reels_mode:
            font_size = min(font_size, 52)
```

Then replace line 448 (`size=(size[0] - 100, padded_height),`) and line 462 (same pattern in fallback) — change the TextClip `size` parameter. Replace the width calculation. Before the first `try:` block (around line 438), add:

```python
        subtitle_width = 900 if reels_mode else size[0] - 100
```

Then change both TextClip calls to use `size=(subtitle_width, padded_height)` instead of `size=(size[0] - 100, padded_height)`.

- [ ] **Step 4: Update the existing test that expects font_size=72**

In `tests/test_assembler.py`, class `TestReelsSubtitleFontSize`, method `test_chorus_font_size_72_in_reels_mode`: change the assertion from `self.assertEqual(call_kwargs.get("font_size"), 72)` to `self.assertEqual(call_kwargs.get("font_size"), 52)`. Also rename the method to `test_chorus_font_size_52_in_reels_mode`.

- [ ] **Step 5: Run all tests to verify they pass**

Run: `python3 -m pytest tests/test_assembler.py::TestReelsSubtitleWidth tests/test_assembler.py::TestReelsFontSizeCap tests/test_assembler.py::TestReelsSubtitleFontSize -v`
Expected: All passed

- [ ] **Step 6: Commit**

```bash
git add musicvid/pipeline/assembler.py tests/test_assembler.py
git commit -m "fix: cap reels font size at 52px and set subtitle width to 900px"
```

---

### Task 3: Add text wrapping and multiline position calculation for reels

**Files:**
- Modify: `musicvid/pipeline/assembler.py:415-474` (inside `_create_subtitle_clips` loop)
- Modify: `tests/test_assembler.py` (add new test class)

- [ ] **Step 1: Write the failing tests**

Add at the end of `tests/test_assembler.py`:

```python
class TestReelsSubtitleWrapping(unittest.TestCase):
    @patch("musicvid.pipeline.assembler.vfx")
    @patch("musicvid.pipeline.assembler.TextClip")
    def test_long_text_wrapped_in_reels(self, mock_textclip, mock_vfx):
        from musicvid.pipeline.assembler import _create_subtitle_clips

        mock_clip = MagicMock()
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.with_start.return_value = mock_clip
        mock_clip.with_position.return_value = mock_clip
        mock_clip.with_effects.return_value = mock_clip
        mock_textclip.return_value = mock_clip

        lyrics = [{"start": 1.0, "end": 3.0,
                    "text": "Panie Boże prowadź mnie dalej", "words": []}]
        style = {"color": "#FFFFFF", "outline_color": "#000000"}

        _create_subtitle_clips(lyrics, style, (1080, 1920), reels_mode=True)

        call_kwargs = mock_textclip.call_args[1]
        assert "\n" in call_kwargs["text"], "Long text should be wrapped in reels mode"

    @patch("musicvid.pipeline.assembler.vfx")
    @patch("musicvid.pipeline.assembler.TextClip")
    def test_short_text_not_wrapped_in_reels(self, mock_textclip, mock_vfx):
        from musicvid.pipeline.assembler import _create_subtitle_clips

        mock_clip = MagicMock()
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.with_start.return_value = mock_clip
        mock_clip.with_position.return_value = mock_clip
        mock_clip.with_effects.return_value = mock_clip
        mock_textclip.return_value = mock_clip

        lyrics = [{"start": 1.0, "end": 3.0, "text": "Alleluja", "words": []}]
        style = {"color": "#FFFFFF", "outline_color": "#000000"}

        _create_subtitle_clips(lyrics, style, (1080, 1920), reels_mode=True)

        call_kwargs = mock_textclip.call_args[1]
        assert "\n" not in call_kwargs["text"]

    @patch("musicvid.pipeline.assembler.vfx")
    @patch("musicvid.pipeline.assembler.TextClip")
    def test_text_not_wrapped_in_landscape(self, mock_textclip, mock_vfx):
        from musicvid.pipeline.assembler import _create_subtitle_clips

        mock_clip = MagicMock()
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.with_start.return_value = mock_clip
        mock_clip.with_position.return_value = mock_clip
        mock_clip.with_effects.return_value = mock_clip
        mock_textclip.return_value = mock_clip

        lyrics = [{"start": 1.0, "end": 3.0,
                    "text": "Panie Boże prowadź mnie dalej", "words": []}]
        style = {"color": "#FFFFFF", "outline_color": "#000000"}

        _create_subtitle_clips(lyrics, style, (1920, 1080), reels_mode=False)

        call_kwargs = mock_textclip.call_args[1]
        assert "\n" not in call_kwargs["text"]


class TestReelsMultilinePosition(unittest.TestCase):
    @patch("musicvid.pipeline.assembler.vfx")
    @patch("musicvid.pipeline.assembler.TextClip")
    def test_two_line_subtitle_position_higher(self, mock_textclip, mock_vfx):
        from musicvid.pipeline.assembler import _create_subtitle_clips

        mock_clip = MagicMock()
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.with_start.return_value = mock_clip
        mock_clip.with_position.return_value = mock_clip
        mock_clip.with_effects.return_value = mock_clip
        mock_textclip.return_value = mock_clip

        # Long text that will wrap to 2 lines
        long_text = "Panie Boże prowadź mnie dalej"
        lyrics = [{"start": 1.0, "end": 3.0, "text": long_text, "words": []}]
        style = {"color": "#FFFFFF", "outline_color": "#000000"}

        _create_subtitle_clips(lyrics, style, (1080, 1920),
                               reels_mode=True, subtitle_margin_bottom=200)

        pos_call = mock_clip.with_position.call_args[0][0]
        y_pos = pos_call[1]
        # With 2 lines at 52px font, total height = 2 * 52 * 1.4 = 145.6
        # y = 1920 - 145.6 - 200 = 1574.4
        # Must be above single-line y = 1920 - 72.8 - 200 = 1647.2
        assert y_pos < 1920 - 200, f"y_pos {y_pos} should be well above bottom margin"

    @patch("musicvid.pipeline.assembler.vfx")
    @patch("musicvid.pipeline.assembler.TextClip")
    def test_multiline_textclip_height_accounts_for_lines(self, mock_textclip, mock_vfx):
        from musicvid.pipeline.assembler import _create_subtitle_clips

        mock_clip = MagicMock()
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.with_start.return_value = mock_clip
        mock_clip.with_position.return_value = mock_clip
        mock_clip.with_effects.return_value = mock_clip
        mock_textclip.return_value = mock_clip

        long_text = "Panie Boże prowadź mnie dalej"
        lyrics = [{"start": 1.0, "end": 3.0, "text": long_text, "words": []}]
        style = {"color": "#FFFFFF", "outline_color": "#000000"}

        _create_subtitle_clips(lyrics, style, (1080, 1920), reels_mode=True)

        call_kwargs = mock_textclip.call_args[1]
        height = call_kwargs["size"][1]
        # 2 lines: height should be > single-line padded height
        single_line_height = 52 + int(52 * 0.35)  # 70
        assert height > single_line_height, f"Height {height} should account for 2 lines"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_assembler.py::TestReelsSubtitleWrapping tests/test_assembler.py::TestReelsMultilinePosition -v`
Expected: FAIL — text not wrapped, position not adjusted

- [ ] **Step 3: Implement wrapping and multiline position in `_create_subtitle_clips`**

In `musicvid/pipeline/assembler.py`, inside the `for segment in lyrics:` loop in `_create_subtitle_clips`, after the font size cap (`if reels_mode: font_size = min(font_size, 52)`) and before the descender pad calculation, add text wrapping:

```python
        lyric_text = segment["text"]
        if reels_mode:
            lyric_text = wrap_for_portrait(lyric_text, max_chars=25)
```

Then change the height/position calculation. Replace the `descender_pad` and `padded_height` and `y_pos` lines with:

```python
        lines_count = lyric_text.count("\n") + 1
        line_height = int(font_size * 1.4)
        total_height = lines_count * line_height
        padded_height = total_height

        y_pos = size[1] - total_height - margin_bottom
```

Update both `TextClip` calls to use `text=lyric_text` instead of `text=segment["text"]`, and `size=(subtitle_width, padded_height)`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_assembler.py::TestReelsSubtitleWrapping tests/test_assembler.py::TestReelsMultilinePosition tests/test_assembler.py::TestWrapForPortrait -v`
Expected: All passed

- [ ] **Step 5: Commit**

```bash
git add musicvid/pipeline/assembler.py tests/test_assembler.py
git commit -m "fix: wrap long subtitles and adjust multiline position for reels"
```

---

### Task 4: Enforce safe zone (10%-85%) for reels subtitles

**Files:**
- Modify: `musicvid/pipeline/assembler.py` (inside `_create_subtitle_clips` loop, after position calc)
- Modify: `tests/test_assembler.py` (add new test class)

- [ ] **Step 1: Write the failing tests**

Add at the end of `tests/test_assembler.py`:

```python
class TestReelsSafeZone(unittest.TestCase):
    @patch("musicvid.pipeline.assembler.vfx")
    @patch("musicvid.pipeline.assembler.TextClip")
    def test_subtitle_within_safe_zone(self, mock_textclip, mock_vfx):
        from musicvid.pipeline.assembler import _create_subtitle_clips

        mock_clip = MagicMock()
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.with_start.return_value = mock_clip
        mock_clip.with_position.return_value = mock_clip
        mock_clip.with_effects.return_value = mock_clip
        mock_textclip.return_value = mock_clip

        lyrics = [{"start": 1.0, "end": 3.0,
                    "text": "Panie Boże prowadź mnie dalej", "words": []}]
        style = {"color": "#FFFFFF", "outline_color": "#000000"}
        frame_h = 1920

        _create_subtitle_clips(lyrics, style, (1080, frame_h),
                               reels_mode=True, subtitle_margin_bottom=200)

        pos_call = mock_clip.with_position.call_args[0][0]
        y_pos = pos_call[1]
        safe_top = frame_h * 0.10   # 192
        safe_bottom = frame_h * 0.85  # 1632

        assert y_pos >= safe_top, f"y={y_pos} above safe top {safe_top}"
        # bottom of text = y_pos + total_height; check y_pos is inside zone
        assert y_pos <= safe_bottom, f"y={y_pos} below safe bottom {safe_bottom}"

    @patch("musicvid.pipeline.assembler.vfx")
    @patch("musicvid.pipeline.assembler.TextClip")
    def test_font_shrinks_if_outside_safe_zone(self, mock_textclip, mock_vfx):
        from musicvid.pipeline.assembler import _create_subtitle_clips

        mock_clip = MagicMock()
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.with_start.return_value = mock_clip
        mock_clip.with_position.return_value = mock_clip
        mock_clip.with_effects.return_value = mock_clip
        mock_textclip.return_value = mock_clip

        # Very long text that wraps to many lines
        long_text = " ".join(["słowo"] * 20)
        lyrics = [{"start": 1.0, "end": 3.0, "text": long_text, "words": []}]
        style = {"color": "#FFFFFF", "outline_color": "#000000"}

        _create_subtitle_clips(lyrics, style, (1080, 1920),
                               reels_mode=True, subtitle_margin_bottom=200)

        pos_call = mock_clip.with_position.call_args[0][0]
        y_pos = pos_call[1]
        safe_top = 1920 * 0.10

        assert y_pos >= safe_top, f"y={y_pos} should be >= safe_top={safe_top}"

    @patch("musicvid.pipeline.assembler.vfx")
    @patch("musicvid.pipeline.assembler.TextClip")
    def test_landscape_no_safe_zone_enforcement(self, mock_textclip, mock_vfx):
        from musicvid.pipeline.assembler import _create_subtitle_clips

        mock_clip = MagicMock()
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.with_start.return_value = mock_clip
        mock_clip.with_position.return_value = mock_clip
        mock_clip.with_effects.return_value = mock_clip
        mock_textclip.return_value = mock_clip

        lyrics = [{"start": 1.0, "end": 3.0, "text": "Test text", "words": []}]
        style = {"color": "#FFFFFF", "outline_color": "#000000"}

        # Landscape mode — no safe zone enforcement, no font cap
        _create_subtitle_clips(lyrics, style, (1920, 1080), reels_mode=False)

        call_kwargs = mock_textclip.call_args[1]
        # Font should NOT be capped (no reels_mode)
        assert call_kwargs["font_size"] == 54  # default
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_assembler.py::TestReelsSafeZone -v`
Expected: FAIL — safe zone not enforced

- [ ] **Step 3: Implement safe zone enforcement**

In `musicvid/pipeline/assembler.py`, inside `_create_subtitle_clips`, after the `y_pos` calculation and before the `try:` block for TextClip creation, add safe zone enforcement for reels:

```python
        if reels_mode:
            safe_top = size[1] * 0.10
            safe_bottom = size[1] * 0.85
            while y_pos < safe_top and font_size > 28:
                font_size -= 4
                lyric_text = wrap_for_portrait(segment["text"], max_chars=25)
                lines_count = lyric_text.count("\n") + 1
                line_height = int(font_size * 1.4)
                total_height = lines_count * line_height
                padded_height = total_height
                y_pos = size[1] - total_height - margin_bottom
            y_pos = max(y_pos, safe_top)
```

Also update the `subtitle_width` variable to use the current `font_size` for height calc (it's already set).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_assembler.py::TestReelsSafeZone -v`
Expected: All passed

- [ ] **Step 5: Run the full test suite to check for regressions**

Run: `python3 -m pytest tests/test_assembler.py -v`
Expected: All tests pass (existing + new). The `TestReelsSubtitleFontSize` tests should pass with the updated assertion from Task 2.

- [ ] **Step 6: Commit**

```bash
git add musicvid/pipeline/assembler.py tests/test_assembler.py
git commit -m "fix: enforce 10%-85% safe zone for reels subtitles"
```

---

### Task 5: Run full test suite and fix any regressions

**Files:**
- Possibly modify: `musicvid/pipeline/assembler.py`, `tests/test_assembler.py`

- [ ] **Step 1: Run the complete test suite**

Run: `python3 -m pytest tests/ -v`
Expected: All ~790+ tests pass

- [ ] **Step 2: Fix any failures**

If any tests fail due to the changes (e.g., tests that assert old font_size=72 or old width=980), update them to match the new behavior. The known test to update is `TestReelsSubtitleFontSize.test_chorus_font_size_72_in_reels_mode` (already updated in Task 2).

Also check:
- `TestCreateSubtitleClips` — may reference old height calculations
- `TestTextFlash` — reels_mode tests may be affected by wrapping
- Any test asserting `size=(size[0] - 100, ...)` in reels mode

- [ ] **Step 3: Commit if fixes were needed**

```bash
git add -A
git commit -m "fix: update tests for new reels subtitle behavior"
```

---

### Task 6: Move spec to done

**Files:**
- Move: `docs/superpowers/specs/fix-subtitle-overflow-social.md` → `docs/superpowers/specs/done/fix-subtitle-overflow-social.md`

- [ ] **Step 1: Move spec file**

```bash
mv docs/superpowers/specs/fix-subtitle-overflow-social.md docs/superpowers/specs/done/fix-subtitle-overflow-social.md
```

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/specs/fix-subtitle-overflow-social.md docs/superpowers/specs/done/fix-subtitle-overflow-social.md
git commit -m "docs: move subtitle overflow spec to done"
```
