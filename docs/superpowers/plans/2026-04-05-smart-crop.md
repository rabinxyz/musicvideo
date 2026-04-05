# Smart Crop for Social Media Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add smart crop functionality that detects face/saliency point-of-interest to intelligently convert 16:9 images to 9:16 portrait format for social media reels, replacing the naive center crop.

**Architecture:** New `musicvid/pipeline/smart_crop.py` module implements POI detection (OpenCV face detection → saliency → center fallback) and image conversion. Assembler integrates via new `reels_style` param in `_load_scene_clip`. CLI gets `--reels-style [crop|blur-bg]`. Image generator gets native 9:16 generation when `platform="reels"`.

**Tech Stack:** OpenCV (cv2) for face detection + saliency, Pillow for image compositing, MoviePy 2.x for assembly.

---

## File Structure

**Create:**
- `musicvid/pipeline/smart_crop.py` — POI detection + smart crop + blur-bg composite + platform converter
- `tests/test_smart_crop.py` — Unit tests for all smart_crop functions (mocking cv2 and PIL)

**Modify:**
- `musicvid/requirements.txt` — Add `opencv-python>=4.8.0`
- `musicvid/pipeline/assembler.py` — Add `reels_style` param to `_load_scene_clip` and `assemble_video`; use `convert_for_platform` for portrait images
- `musicvid/musicvid.py` — Add `--reels-style` CLI option; plumb through `_run_preset_mode`; pass `platform="reels"` to `generate_images` when `preset=="social"`
- `musicvid/pipeline/image_generator.py` — Add `platform=None` param; generate 768×1360 when `platform=="reels"`
- `tests/test_assembler.py` — Add tests for smart crop integration in portrait mode
- `tests/test_cli.py` — Add test for `--reels-style` option
- `tests/test_image_generator.py` — Add test for native 9:16 generation

---

### Task 1: Add opencv-python to requirements.txt

**Files:**
- Modify: `musicvid/requirements.txt`

- [ ] **Step 1: Add opencv-python dependency**

Edit `musicvid/requirements.txt` — add after the `numpy` line:
```
opencv-python>=4.8.0
```

- [ ] **Step 2: Verify requirements file is correct**

Run: `grep opencv musicvid/requirements.txt`
Expected: `opencv-python>=4.8.0`

- [ ] **Step 3: Commit**

```bash
git add musicvid/requirements.txt
git commit -m "chore: add opencv-python dependency for smart crop"
```

---

### Task 2: Create smart_crop.py with all functions + tests

**Files:**
- Create: `musicvid/pipeline/smart_crop.py`
- Create: `tests/test_smart_crop.py`

- [ ] **Step 1: Write failing tests for detect_poi()**

Create `tests/test_smart_crop.py`:

```python
"""Tests for smart_crop pipeline module."""

import unittest
from unittest.mock import MagicMock, patch
import numpy as np


class TestDetectPoi(unittest.TestCase):
    @patch("musicvid.pipeline.smart_crop.cv2")
    def test_detect_poi_returns_face_center_when_face_found(self, mock_cv2):
        mock_img = np.zeros((768, 1024, 3), dtype=np.uint8)
        mock_cv2.imread.return_value = mock_img
        mock_cv2.cvtColor.return_value = np.zeros((768, 1024), dtype=np.uint8)
        mock_cv2.data.haarcascades = "/fake/"
        mock_cascade = MagicMock()
        mock_cv2.CascadeClassifier.return_value = mock_cascade
        # Face at x=100, y=200, w=80, h=80 → center = (140, 240)
        mock_cascade.detectMultiScale.return_value = [(100, 200, 80, 80)]

        from musicvid.pipeline.smart_crop import detect_poi
        result = detect_poi("/fake/image.jpg")

        self.assertEqual(result, (140, 240))

    @patch("musicvid.pipeline.smart_crop.cv2")
    def test_detect_poi_uses_largest_face_when_multiple(self, mock_cv2):
        mock_img = np.zeros((768, 1024, 3), dtype=np.uint8)
        mock_cv2.imread.return_value = mock_img
        mock_cv2.cvtColor.return_value = np.zeros((768, 1024), dtype=np.uint8)
        mock_cv2.data.haarcascades = "/fake/"
        mock_cascade = MagicMock()
        mock_cv2.CascadeClassifier.return_value = mock_cascade
        # Two faces: small (50x50) and large (100x100) → use large face center
        mock_cascade.detectMultiScale.return_value = [
            (10, 10, 50, 50),
            (400, 300, 100, 100),
        ]

        from musicvid.pipeline.smart_crop import detect_poi
        result = detect_poi("/fake/image.jpg")

        # Large face center: (400 + 50, 300 + 50) = (450, 350)
        self.assertEqual(result, (450, 350))

    @patch("musicvid.pipeline.smart_crop.cv2")
    def test_detect_poi_uses_saliency_when_no_face(self, mock_cv2):
        mock_img = np.zeros((768, 1024, 3), dtype=np.uint8)
        mock_cv2.imread.return_value = mock_img
        mock_cv2.cvtColor.return_value = np.zeros((768, 1024), dtype=np.uint8)
        mock_cv2.data.haarcascades = "/fake/"
        mock_cascade = MagicMock()
        mock_cv2.CascadeClassifier.return_value = mock_cascade
        mock_cascade.detectMultiScale.return_value = []  # no faces
        mock_saliency = MagicMock()
        mock_cv2.saliency.StaticSaliencyFineGrained_create.return_value = mock_saliency
        saliency_map = np.zeros((768, 1024), dtype=np.float32)
        mock_saliency.computeSaliency.return_value = (True, saliency_map)
        # minMaxLoc returns (min_val, max_val, min_loc, max_loc)
        mock_cv2.minMaxLoc.return_value = (0.0, 1.0, (0, 0), (300, 400))

        from musicvid.pipeline.smart_crop import detect_poi
        result = detect_poi("/fake/image.jpg")

        self.assertEqual(result, (300, 400))

    @patch("musicvid.pipeline.smart_crop.cv2")
    def test_detect_poi_falls_back_to_center_when_saliency_fails(self, mock_cv2):
        mock_img = np.zeros((768, 1024, 3), dtype=np.uint8)
        mock_cv2.imread.return_value = mock_img
        mock_cv2.cvtColor.return_value = np.zeros((768, 1024), dtype=np.uint8)
        mock_cv2.data.haarcascades = "/fake/"
        mock_cascade = MagicMock()
        mock_cv2.CascadeClassifier.return_value = mock_cascade
        mock_cascade.detectMultiScale.return_value = []  # no faces
        mock_saliency = MagicMock()
        mock_cv2.saliency.StaticSaliencyFineGrained_create.return_value = mock_saliency
        mock_saliency.computeSaliency.return_value = (False, None)  # saliency fails

        from musicvid.pipeline.smart_crop import detect_poi
        result = detect_poi("/fake/image.jpg")

        # Center of 1024x768 image
        self.assertEqual(result, (512, 384))


class TestSmartCrop(unittest.TestCase):
    @patch("musicvid.pipeline.smart_crop.detect_poi")
    @patch("musicvid.pipeline.smart_crop.Image")
    def test_smart_crop_returns_image_with_target_dimensions(self, mock_Image, mock_detect_poi):
        mock_detect_poi.return_value = (512, 384)
        mock_pil_img = MagicMock()
        mock_pil_img.size = (1024, 768)
        mock_pil_img.convert.return_value = mock_pil_img
        mock_cropped = MagicMock()
        mock_resized = MagicMock()
        mock_pil_img.crop.return_value = mock_cropped
        mock_cropped.resize.return_value = mock_resized
        mock_Image.open.return_value.__enter__ = lambda s: mock_pil_img
        mock_Image.open.return_value.__exit__ = MagicMock(return_value=False)
        mock_Image.open.return_value = mock_pil_img
        mock_Image.LANCZOS = 1

        from musicvid.pipeline.smart_crop import smart_crop
        result = smart_crop("/fake/image.jpg", 1080, 1920)

        # Verify crop was called (exact coords depend on logic)
        mock_pil_img.crop.assert_called_once()
        mock_cropped.resize.assert_called_once_with((1080, 1920), 1)
        self.assertEqual(result, mock_resized)

    @patch("musicvid.pipeline.smart_crop.detect_poi")
    @patch("musicvid.pipeline.smart_crop.Image")
    def test_smart_crop_uses_provided_poi_without_calling_detect_poi(self, mock_Image, mock_detect_poi):
        mock_pil_img = MagicMock()
        mock_pil_img.size = (1024, 768)
        mock_pil_img.convert.return_value = mock_pil_img
        mock_cropped = MagicMock()
        mock_pil_img.crop.return_value = mock_cropped
        mock_cropped.resize.return_value = MagicMock()
        mock_Image.open.return_value = mock_pil_img
        mock_Image.LANCZOS = 1

        from musicvid.pipeline.smart_crop import smart_crop
        smart_crop("/fake/image.jpg", 1080, 1920, poi=(300, 200))

        mock_detect_poi.assert_not_called()

    @patch("musicvid.pipeline.smart_crop.detect_poi")
    @patch("musicvid.pipeline.smart_crop.Image")
    def test_smart_crop_clamps_crop_x_to_image_bounds(self, mock_Image, mock_detect_poi):
        # POI near right edge — crop should not go out of bounds
        mock_detect_poi.return_value = (1000, 384)
        mock_pil_img = MagicMock()
        mock_pil_img.size = (1024, 768)
        mock_pil_img.convert.return_value = mock_pil_img
        mock_cropped = MagicMock()
        mock_pil_img.crop.return_value = mock_cropped
        mock_cropped.resize.return_value = MagicMock()
        mock_Image.open.return_value = mock_pil_img
        mock_Image.LANCZOS = 1

        from musicvid.pipeline.smart_crop import smart_crop
        smart_crop("/fake/image.jpg", 1080, 1920)

        crop_args = mock_pil_img.crop.call_args[0][0]
        x1, y1, x2, y2 = crop_args
        # x1 must be >= 0 and x2 must be <= 1024
        self.assertGreaterEqual(x1, 0)
        self.assertLessEqual(x2, 1024)


class TestBlurBgComposite(unittest.TestCase):
    @patch("musicvid.pipeline.smart_crop.smart_crop")
    @patch("musicvid.pipeline.smart_crop.Image")
    @patch("musicvid.pipeline.smart_crop.ImageFilter")
    def test_blur_bg_composite_returns_target_size(self, mock_filter, mock_Image, mock_smart_crop):
        mock_orig = MagicMock()
        mock_orig.size = (1024, 768)
        mock_orig.convert.return_value = mock_orig
        mock_scaled = MagicMock()
        mock_orig.resize.return_value = mock_scaled
        mock_scaled.crop.return_value = mock_scaled
        mock_blurred = MagicMock()
        mock_scaled.filter.return_value = mock_blurred
        mock_result = MagicMock()
        mock_blurred.copy.return_value = mock_result
        mock_sharp = MagicMock()
        mock_smart_crop.return_value = mock_sharp
        mock_Image.open.return_value = mock_orig
        mock_Image.LANCZOS = 1

        from musicvid.pipeline.smart_crop import blur_bg_composite
        result = blur_bg_composite("/fake/image.jpg", 1080, 1920)

        mock_result.paste.assert_called_once_with(mock_sharp, (0, 0))
        self.assertEqual(result, mock_result)


class TestConvertForPlatform(unittest.TestCase):
    @patch("musicvid.pipeline.smart_crop.blur_bg_composite")
    def test_convert_for_platform_reels_blur_bg_calls_blur_composite(self, mock_blur):
        mock_result = MagicMock()
        mock_blur.return_value = mock_result

        from musicvid.pipeline.smart_crop import convert_for_platform
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            tmp_path = f.name
        try:
            convert_for_platform(tmp_path, "reels", style="blur-bg")
            mock_blur.assert_called_once_with(tmp_path, 1080, 1920)
            mock_result.save.assert_called_once()
        finally:
            os.unlink(tmp_path)
            out = tmp_path.replace(
                os.path.basename(tmp_path),
                "smart_" + os.path.splitext(os.path.basename(tmp_path))[0] + ".jpg"
            )
            if os.path.exists(out):
                os.unlink(out)

    @patch("musicvid.pipeline.smart_crop.smart_crop")
    def test_convert_for_platform_reels_crop_calls_smart_crop(self, mock_crop):
        mock_result = MagicMock()
        mock_crop.return_value = mock_result

        from musicvid.pipeline.smart_crop import convert_for_platform
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            tmp_path = f.name
        try:
            convert_for_platform(tmp_path, "reels", style="crop")
            mock_crop.assert_called_once_with(tmp_path, 1080, 1920)
        finally:
            os.unlink(tmp_path)

    @patch("musicvid.pipeline.smart_crop.blur_bg_composite")
    def test_convert_for_platform_returns_output_path_string(self, mock_blur):
        mock_blur.return_value = MagicMock()

        from musicvid.pipeline.smart_crop import convert_for_platform
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            tmp_path = f.name
        try:
            result = convert_for_platform(tmp_path, "reels")
            self.assertIsInstance(result, str)
            self.assertIn("smart_", result)
            self.assertTrue(result.endswith(".jpg"))
        finally:
            os.unlink(tmp_path)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_smart_crop.py -v 2>&1 | head -30`
Expected: ModuleNotFoundError or ImportError — `smart_crop` module not found.

- [ ] **Step 3: Create musicvid/pipeline/smart_crop.py**

```python
"""Smart crop utilities for social media portrait format conversion."""

import numpy as np
import cv2
from PIL import Image, ImageFilter
from pathlib import Path


PLATFORM_SIZES = {
    "reels": (1080, 1920),
    "shorts": (1080, 1920),
    "square": (1080, 1080),
}


def detect_poi(image_path):
    """Detect point of interest in image via face detection or saliency.

    Returns (x, y) coordinates in original image.
    Fallback: image center (w//2, h//2).
    """
    img = cv2.imread(str(image_path))
    if img is None:
        raise ValueError(f"Could not open image: {image_path}")

    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Method 1: Face detection via Haar cascade
    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    faces = face_cascade.detectMultiScale(gray, 1.1, 4)
    if len(faces) > 0:
        fx, fy, fw, fh = max(faces, key=lambda f: f[2] * f[3])
        return fx + fw // 2, fy + fh // 2

    # Method 2: Saliency map
    saliency = cv2.saliency.StaticSaliencyFineGrained_create()
    success, saliency_map = saliency.computeSaliency(img)
    if success:
        saliency_8u = (saliency_map * 255).astype(np.uint8)
        _, _, _, max_loc = cv2.minMaxLoc(saliency_8u)
        return max_loc[0], max_loc[1]

    # Method 3: Center fallback
    return w // 2, h // 2


def smart_crop(image_path, target_w, target_h, poi=None):
    """Crop image to target_w x target_h centered on point of interest.

    Args:
        image_path: Path to source image.
        target_w: Target width in pixels.
        target_h: Target height in pixels.
        poi: Optional (x, y) tuple; calls detect_poi() when None.

    Returns:
        PIL.Image resized to (target_w, target_h).
    """
    if poi is None:
        poi = detect_poi(image_path)

    img = Image.open(str(image_path)).convert("RGB")
    orig_w, orig_h = img.size
    target_ratio = target_w / target_h

    if orig_w / orig_h > target_ratio:
        # Original wider than target: crop width, keep full height
        crop_h = orig_h
        crop_w = int(orig_h * target_ratio)
    else:
        # Original taller or same ratio: crop height, keep full width
        crop_w = orig_w
        crop_h = int(orig_w / target_ratio)

    poi_x, poi_y = poi
    crop_x = poi_x - crop_w // 2
    crop_x = max(0, min(crop_x, orig_w - crop_w))
    crop_y = poi_y - crop_h // 2
    crop_y = max(0, min(crop_y, orig_h - crop_h))

    cropped = img.crop((crop_x, crop_y, crop_x + crop_w, crop_y + crop_h))
    return cropped.resize((target_w, target_h), Image.LANCZOS)


def blur_bg_composite(image_path, target_w, target_h):
    """Create portrait composite: blurred background + sharp smart crop overlay.

    Scales original to fill target height as blurred background, then
    pastes sharp smart-cropped version on top.

    Returns:
        PIL.Image sized (target_w, target_h).
    """
    img = Image.open(str(image_path)).convert("RGB")
    orig_w, orig_h = img.size

    # Scale to fill target height (background layer)
    scale = target_h / orig_h
    bg_w = int(orig_w * scale)
    bg = img.resize((bg_w, target_h), Image.LANCZOS)

    # Center-crop background to target width
    bg_x = max(0, (bg_w - target_w) // 2)
    bg = bg.crop((bg_x, 0, bg_x + target_w, target_h))

    # Heavy Gaussian blur on background
    bg = bg.filter(ImageFilter.GaussianBlur(radius=30))

    # Sharp smart crop centered on POI
    sharp = smart_crop(image_path, target_w, target_h)

    result = bg.copy()
    result.paste(sharp, (0, 0))
    return result


def convert_for_platform(image_path, platform, style="blur-bg"):
    """Convert image for social media platform format.

    Args:
        image_path: Path to source image.
        platform: "reels" | "shorts" | "square"
        style: "blur-bg" (recommended) | "crop"

    Returns:
        Path string to converted image (saved alongside source with smart_ prefix).
    """
    target_w, target_h = PLATFORM_SIZES.get(platform, (1080, 1920))

    if style == "blur-bg":
        result = blur_bg_composite(image_path, target_w, target_h)
    else:
        result = smart_crop(image_path, target_w, target_h)

    src = Path(image_path)
    out_path = src.parent / f"smart_{src.stem}.jpg"
    result.save(str(out_path), "JPEG", quality=95)
    return str(out_path)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_smart_crop.py -v`
Expected: All tests pass (approximately 10 tests).

- [ ] **Step 5: Commit**

```bash
git add musicvid/pipeline/smart_crop.py tests/test_smart_crop.py
git commit -m "feat: add smart_crop module with POI detection and portrait conversion"
```

---

### Task 3: Integrate smart crop into assembler.py + tests

**Files:**
- Modify: `musicvid/pipeline/assembler.py` — `_load_scene_clip` + `assemble_video`
- Modify: `tests/test_assembler.py` — add portrait smart crop tests

- [ ] **Step 1: Write failing tests for assembler smart crop integration**

Open `tests/test_assembler.py` and add a new test class near the `TestLoadSceneClipAnimated` class. Find the end of that class and append:

```python
class TestLoadSceneClipSmartCrop(unittest.TestCase):
    """Tests that _load_scene_clip uses smart crop for portrait images."""

    def setUp(self):
        self.scene = {
            "start": 0.0,
            "end": 5.0,
            "motion": "pan_up",
            "animate": False,
            "transition": "crossfade",
        }
        self.portrait_size = (1080, 1920)

    @patch("musicvid.pipeline.assembler.convert_for_platform")
    @patch("musicvid.pipeline.assembler.ImageClip")
    def test_portrait_image_calls_convert_for_platform(self, mock_ImageClip, mock_convert):
        mock_convert.return_value = "/fake/smart_scene.jpg"
        mock_clip = MagicMock()
        mock_clip.size = (1080, 1920)
        mock_clip.w = 1080
        mock_clip.h = 1920
        mock_clip.cropped.return_value = mock_clip
        mock_ImageClip.return_value = mock_clip

        from musicvid.pipeline.assembler import _load_scene_clip
        _load_scene_clip("/fake/scene.jpg", self.scene, self.portrait_size, reels_style="blur-bg")

        mock_convert.assert_called_once_with("/fake/scene.jpg", "reels", style="blur-bg")
        mock_ImageClip.assert_called_once_with("/fake/smart_scene.jpg")

    @patch("musicvid.pipeline.assembler.convert_for_platform")
    @patch("musicvid.pipeline.assembler.ImageClip")
    def test_portrait_image_uses_crop_style_when_specified(self, mock_ImageClip, mock_convert):
        mock_convert.return_value = "/fake/smart_scene.jpg"
        mock_clip = MagicMock()
        mock_clip.size = (1080, 1920)
        mock_clip.w = 1080
        mock_clip.h = 1920
        mock_clip.cropped.return_value = mock_clip
        mock_ImageClip.return_value = mock_clip

        from musicvid.pipeline.assembler import _load_scene_clip
        _load_scene_clip("/fake/scene.jpg", self.scene, self.portrait_size, reels_style="crop")

        mock_convert.assert_called_once_with("/fake/scene.jpg", "reels", style="crop")

    @patch("musicvid.pipeline.assembler.convert_for_platform")
    @patch("musicvid.pipeline.assembler.ImageClip")
    def test_landscape_image_does_not_call_convert_for_platform(self, mock_ImageClip, mock_convert):
        mock_clip = MagicMock()
        mock_clip.size = (1920, 1080)
        mock_clip.w = 1920
        mock_clip.h = 1080
        mock_clip.cropped.return_value = mock_clip
        mock_ImageClip.return_value = mock_clip

        from musicvid.pipeline.assembler import _load_scene_clip
        _load_scene_clip("/fake/scene.jpg", self.scene, (1920, 1080), reels_style="blur-bg")

        mock_convert.assert_not_called()
```

Run: `python3 -m pytest tests/test_assembler.py::TestLoadSceneClipSmartCrop -v`
Expected: FAIL — `_load_scene_clip` doesn't accept `reels_style` yet.

- [ ] **Step 2: Update _load_scene_clip in assembler.py**

Edit `musicvid/pipeline/assembler.py` — update the imports and `_load_scene_clip` function:

At the top of the file, add the import after the existing imports:
```python
from musicvid.pipeline.smart_crop import convert_for_platform
```

Replace the `_load_scene_clip` function (lines 222–240) with:
```python
def _load_scene_clip(video_path, scene, target_size, reels_style="blur-bg"):
    """Load a video or image clip for a scene."""
    path = Path(video_path)
    duration = scene["end"] - scene["start"]
    is_portrait = target_size == (1080, 1920)

    if path.suffix.lower() in (".png", ".jpg", ".jpeg", ".bmp"):
        if is_portrait:
            processed_path = convert_for_platform(str(path), "reels", style=reels_style)
            clip = ImageClip(processed_path)
        else:
            clip = ImageClip(str(path))
    else:
        clip = VideoFileClip(str(path))
        if clip.duration < duration:
            loops = int(duration / clip.duration) + 1
            clip = concatenate_videoclips([clip] * loops)
        clip = clip.subclipped(0, duration)

    # Animated clips from Runway Gen-4: resize only, skip Ken Burns
    if scene.get("animate", False) and path.suffix.lower() == ".mp4":
        return clip.resized(new_size=target_size)

    return _create_ken_burns_clip(clip, duration, scene.get("motion", "static"), target_size)
```

- [ ] **Step 3: Update assemble_video signature to accept reels_style**

In `assembler.py`, update `assemble_video` function signature (line 243). Find:
```python
def assemble_video(analysis, scene_plan, fetch_manifest, audio_path, output_path, resolution="1080p", font_path=None, effects_level="minimal", clip_start=None, clip_end=None, title_card_text=None, audio_fade_out=1.0, subtitle_margin_bottom=80, cinematic_bars=False, logo_path=None, logo_position="top-left", logo_size=None, logo_opacity=0.85, lut_path=None, lut_style=None, lut_intensity=0.85):
```

Replace with:
```python
def assemble_video(analysis, scene_plan, fetch_manifest, audio_path, output_path, resolution="1080p", font_path=None, effects_level="minimal", clip_start=None, clip_end=None, title_card_text=None, audio_fade_out=1.0, subtitle_margin_bottom=80, cinematic_bars=False, logo_path=None, logo_position="top-left", logo_size=None, logo_opacity=0.85, lut_path=None, lut_style=None, lut_intensity=0.85, reels_style="blur-bg"):
```

Then find where `_load_scene_clip` is called inside `assemble_video`. It will look like:
```python
scene_clip = _load_scene_clip(entry["video_path"], scene, target_size)
```

Replace with:
```python
scene_clip = _load_scene_clip(entry["video_path"], scene, target_size, reels_style=reels_style)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_assembler.py::TestLoadSceneClipSmartCrop -v`
Expected: All 3 tests pass.

Run: `python3 -m pytest tests/test_assembler.py -v 2>&1 | tail -20`
Expected: All existing tests still pass.

- [ ] **Step 5: Commit**

```bash
git add musicvid/pipeline/assembler.py tests/test_assembler.py
git commit -m "feat: integrate smart crop into assembler for portrait images"
```

---

### Task 4: Add --reels-style CLI option and plumb through musicvid.py

**Files:**
- Modify: `musicvid/musicvid.py` — add `--reels-style` option; pass to `_run_preset_mode` and `assemble_video`
- Modify: `tests/test_cli.py` — add test for `--reels-style`

- [ ] **Step 1: Write failing test**

Open `tests/test_cli.py` and find the section with `test_clip_mode_with_platform_uses_portrait_resolution` or a similar CLI test. Add a new test:

```python
def test_reels_style_blur_bg_passed_to_assemble_video(self):
    """--reels-style blur-bg is passed to assemble_video as reels_style."""
    with patch("musicvid.musicvid.analyze_audio") as mock_analyze, \
         patch("musicvid.musicvid.create_scene_plan") as mock_plan, \
         patch("musicvid.musicvid.fetch_videos") as mock_fetch, \
         patch("musicvid.musicvid.assemble_video") as mock_assemble, \
         patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf"), \
         patch.dict(os.environ, {}, clear=False):
        mock_analyze.return_value = {
            "duration": 30.0, "bpm": 120, "mood_energy": "joyful",
            "lyrics": [], "beats": [], "sections": [{"start": 0.0, "end": 30.0, "type": "verse"}],
        }
        mock_plan.return_value = {
            "overall_style": "joyful", "master_style": "", "scenes": [
                {"start": 0.0, "end": 30.0, "visual_prompt": "test", "motion": "static",
                 "transition": "cut", "overlay": "none", "animate": False, "motion_prompt": ""}
            ], "subtitle_style": {"font_size": 58, "color": "#FFFFFF", "outline_color": "#000000", "animation": "karaoke"},
        }
        mock_fetch.return_value = [{"scene_index": 0, "video_path": "/fake/video.mp4", "search_query": "test"}]

        runner = CliRunner()
        result = runner.invoke(cli, [
            "/fake/song.mp3", "--mode", "stock", "--preset", "full",
            "--reels-style", "blur-bg", "--yes"
        ])

        call_kwargs = mock_assemble.call_args[1]
        self.assertEqual(call_kwargs.get("reels_style"), "blur-bg")
```

Run: `python3 -m pytest tests/test_cli.py -k "test_reels_style" -v`
Expected: FAIL — `--reels-style` option not found.

- [ ] **Step 2: Add --reels-style option to CLI**

In `musicvid/musicvid.py`, find the `@click.option("--sequential-assembly", ...)` decorator and add immediately after it (before the `def cli(...)` line):

```python
@click.option("--reels-style", "reels_style", type=click.Choice(["crop", "blur-bg"]), default="blur-bg", help="Portrait conversion style for social reels: blur-bg (blurred background) or crop (smart crop).")
```

- [ ] **Step 3: Add reels_style to cli() function signature**

Find the `def cli(...)` function signature and add `reels_style` to the parameter list:

```python
def cli(audio_file, mode, provider, style, output, resolution, lang, new, font_path, lyrics_path,
        effects, clip_duration, platform, title_card, animate_mode, preset, reel_duration,
        logo_path, logo_position, logo_size, logo_opacity,
        lut_style, lut_intensity, subtitle_style_override, transitions_mode, beat_sync,
        skip_confirm, quick_mode, economy_mode, sequential_assembly, reels_style):
```

- [ ] **Step 4: Pass reels_style to _run_preset_mode and assemble_video in cli()**

Find the `_run_preset_mode(...)` call block (around line 465) and add `reels_style=reels_style,` to the kwargs:

```python
        _run_preset_mode(
            preset=preset,
            reel_duration=int(reel_duration),
            analysis=analysis,
            scene_plan=scene_plan,
            fetch_manifest=fetch_manifest,
            audio_path=str(audio_path),
            output_dir=output_dir,
            stem=audio_path.stem,
            font=font,
            effects=effects,
            cache_dir=cache_dir,
            new=new,
            logo_path=logo_path,
            logo_position=logo_position,
            logo_size=logo_size,
            logo_opacity=logo_opacity,
            lut_style=lut_style,
            lut_intensity=lut_intensity,
            sequential_assembly=sequential_assembly,
            reels_style=reels_style,
        )
```

Find the standalone `assemble_video(...)` call (around line 504) and add `reels_style=reels_style,`:

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
        lut_style=lut_style,
        lut_intensity=lut_intensity,
        reels_style=reels_style,
    )
```

- [ ] **Step 5: Update _run_preset_mode to accept and use reels_style**

Find the `def _run_preset_mode(...)` function signature (around line 527). Update it:

```python
def _run_preset_mode(preset, reel_duration, analysis, scene_plan, fetch_manifest,
                     audio_path, output_dir, stem, font, effects, cache_dir, new,
                     logo_path=None, logo_position="top-left", logo_size=None, logo_opacity=0.85,
                     lut_style=None, lut_intensity=0.85, sequential_assembly=False,
                     reels_style="blur-bg"):
```

Find the social `AssemblyJob` kwargs dict (inside the `for clip_info in social_clips["clips"]:` loop, around line 596) and add `reels_style=reels_style,`:

```python
            jobs.append(AssemblyJob(
                name=f"rolka_{clip_id}_{section}",
                kwargs=dict(
                    analysis=clip_analysis,
                    scene_plan=clip_scene_plan,
                    fetch_manifest=clip_manifest,
                    audio_path=audio_path,
                    output_path=reel_output,
                    resolution="portrait",
                    font_path=font,
                    effects_level=effects,
                    clip_start=clip_start,
                    clip_end=clip_end,
                    audio_fade_out=1.5,
                    subtitle_margin_bottom=200,
                    cinematic_bars=False,
                    logo_path=logo_path,
                    logo_position=logo_position,
                    logo_size=logo_size,
                    logo_opacity=logo_opacity,
                    lut_style=lut_style,
                    lut_intensity=lut_intensity,
                    reels_style=reels_style,
                ),
            ))
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_cli.py -k "test_reels_style" -v`
Expected: PASS.

Run: `python3 -m pytest tests/test_cli.py -v 2>&1 | tail -20`
Expected: All existing tests still pass.

- [ ] **Step 7: Commit**

```bash
git add musicvid/musicvid.py tests/test_cli.py
git commit -m "feat: add --reels-style CLI option for portrait conversion style"
```

---

### Task 5: Native 9:16 image generation for reels in image_generator.py

**Files:**
- Modify: `musicvid/pipeline/image_generator.py` — add `platform=None` param to `generate_images()`
- Modify: `musicvid/musicvid.py` — pass `platform="reels"` when `preset=="social"` and `mode=="ai"`
- Modify: `tests/test_image_generator.py` — add test for native 9:16 generation

- [ ] **Step 1: Write failing test for native 9:16 generation**

Open `tests/test_image_generator.py` and find an existing test class (e.g. `TestGenerateImages`). Add a new test method:

```python
@patch.dict(os.environ, {"BFL_API_KEY": "fake-key"})
@patch("musicvid.pipeline.image_generator.requests")
@patch("musicvid.pipeline.image_generator.time")
def test_generate_images_uses_portrait_dimensions_for_reels_platform(self, mock_time, mock_requests):
    mock_time.monotonic.side_effect = [0, 1, 2, 3, 4, 5]
    mock_time.sleep = MagicMock()
    submit_resp = MagicMock()
    submit_resp.json.return_value = {"id": "task-1", "polling_url": "http://poll/1"}
    poll_resp = MagicMock()
    poll_resp.json.return_value = {"status": "Ready", "result": {"sample": "http://img/1.jpg"}}
    download_resp = MagicMock()
    download_resp.content = b"fake-image-bytes"
    mock_requests.post.return_value = submit_resp
    mock_requests.get.side_effect = [poll_resp, download_resp]

    scene_plan = {
        "master_style": "cinematic",
        "scenes": [{"visual_prompt": "portrait scene"}],
    }
    with tempfile.TemporaryDirectory() as tmpdir:
        from musicvid.pipeline.image_generator import generate_images
        generate_images(scene_plan, tmpdir, provider="flux-pro", platform="reels")

        post_call = mock_requests.post.call_args
        payload = post_call[1]["json"]
        self.assertEqual(payload["width"], 768)
        self.assertEqual(payload["height"], 1360)
        self.assertIn("portrait 9:16", payload["prompt"])
```

Run: `python3 -m pytest tests/test_image_generator.py -k "test_generate_images_uses_portrait" -v`
Expected: FAIL — `generate_images` doesn't have `platform` param yet.

- [ ] **Step 2: Update generate_images() in image_generator.py**

In `musicvid/pipeline/image_generator.py`, update `_submit_task` to accept width and height parameters:

Replace:
```python
def _submit_task(model_name, prompt):
    """Submit an image generation task to BFL API. Returns (task_id, polling_url)."""
    url = f"{BFL_BASE_URL}/v1/{model_name}"
    payload = {
        "prompt": prompt,
        "width": 1024,
        "height": 768,
    }
    resp = requests.post(url, json=payload, headers=_get_headers())
    resp.raise_for_status()
    data = resp.json()
    return data["id"], data["polling_url"]
```

With:
```python
def _submit_task(model_name, prompt, width=1024, height=768):
    """Submit an image generation task to BFL API. Returns (task_id, polling_url)."""
    url = f"{BFL_BASE_URL}/v1/{model_name}"
    payload = {
        "prompt": prompt,
        "width": width,
        "height": height,
    }
    resp = requests.post(url, json=payload, headers=_get_headers())
    resp.raise_for_status()
    data = resp.json()
    return data["id"], data["polling_url"]
```

Update `generate_images` function signature and prompt construction:

Replace:
```python
def generate_images(scene_plan, output_dir, provider="flux-pro"):
    """Generate one image per scene using BFL API.

    Args:
        scene_plan: Scene plan dict from Stage 2.
        output_dir: Directory to save generated images.
        provider: One of flux-dev, flux-pro, flux-schnell. Default: flux-pro (flux-pro-1.1).

    Returns:
        list of image file paths in scene order.
    """
    _detect_provider(provider)

    model_name = BFL_MODELS[provider]
    scenes = scene_plan.get("scenes", [])
    master_style = scene_plan.get("master_style", "")
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    image_paths = []
    total = len(scenes)

    for i, scene in enumerate(scenes):
        visual_prompt = scene.get("visual_prompt", "nature landscape")
        if master_style:
            full_prompt = f"{visual_prompt}, {master_style}, cinematic 16:9, photorealistic, high quality"
        else:
            full_prompt = f"{visual_prompt}, cinematic 16:9, photorealistic, high quality"

        task_id, polling_url = _submit_task(model_name, full_prompt)
```

With:
```python
def generate_images(scene_plan, output_dir, provider="flux-pro", platform=None):
    """Generate one image per scene using BFL API.

    Args:
        scene_plan: Scene plan dict from Stage 2.
        output_dir: Directory to save generated images.
        provider: One of flux-dev, flux-pro, flux-schnell. Default: flux-pro (flux-pro-1.1).
        platform: Optional platform hint — "reels" generates native 9:16 (768x1360).

    Returns:
        list of image file paths in scene order.
    """
    _detect_provider(provider)

    model_name = BFL_MODELS[provider]
    scenes = scene_plan.get("scenes", [])
    master_style = scene_plan.get("master_style", "")
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    is_portrait = platform in ("reels", "shorts")
    img_w, img_h = (768, 1360) if is_portrait else (1024, 768)
    orientation_hint = "portrait 9:16" if is_portrait else "cinematic 16:9"

    image_paths = []
    total = len(scenes)

    for i, scene in enumerate(scenes):
        visual_prompt = scene.get("visual_prompt", "nature landscape")
        if master_style:
            full_prompt = f"{visual_prompt}, {master_style}, {orientation_hint}, photorealistic, high quality"
        else:
            full_prompt = f"{visual_prompt}, {orientation_hint}, photorealistic, high quality"

        task_id, polling_url = _submit_task(model_name, full_prompt, width=img_w, height=img_h)
```

- [ ] **Step 3: Update musicvid.py to pass platform="reels" for social-only preset**

In `musicvid/musicvid.py`, find the Stage 3 block where `generate_images` is called (around line 403):

```python
            image_paths = generate_images(scene_plan, str(cache_dir), provider=provider)
```

Replace with:
```python
            gen_platform = "reels" if preset == "social" else None
            image_paths = generate_images(scene_plan, str(cache_dir), provider=provider, platform=gen_platform)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_image_generator.py -k "test_generate_images_uses_portrait" -v`
Expected: PASS.

Run: `python3 -m pytest tests/test_image_generator.py -v 2>&1 | tail -20`
Expected: All existing tests still pass.

- [ ] **Step 5: Run full test suite**

Run: `python3 -m pytest tests/ -v 2>&1 | tail -30`
Expected: All tests pass (or only pre-existing failures).

- [ ] **Step 6: Commit**

```bash
git add musicvid/pipeline/image_generator.py musicvid/musicvid.py tests/test_image_generator.py
git commit -m "feat: native 9:16 image generation for reels platform"
```

---

## Self-Review Checklist

**Spec coverage:**
- [x] `detect_poi` via face detection (Method 1) → Task 2
- [x] `detect_poi` via saliency (Method 2) → Task 2
- [x] `detect_poi` center fallback (Method 3) → Task 2
- [x] `smart_crop(image_path, target_w, target_h, poi=None)` → Task 2
- [x] `blur_bg_composite(image_path, target_w, target_h)` → Task 2
- [x] `convert_for_platform(image_path, platform, style)` → Task 2
- [x] Assembler uses smart crop for portrait images → Task 3
- [x] `--reels-style [crop|blur-bg]` CLI option (default: blur-bg) → Task 4
- [x] `reels_style` passed through `_run_preset_mode` to social AssemblyJob → Task 4
- [x] Native 9:16 (768×1360) image generation when platform=="reels" → Task 5
- [x] opencv-python added to requirements.txt → Task 1
- [x] Ken Burns on reels uses vertical motions only — already handled by existing `_remap_motion_for_portrait` in musicvid.py
- [x] Smart crop acceptance criteria in spec → covered by tests

**Spec items NOT implemented (out of scope for this plan):**
- Director system prompt changes to request portrait compositions — director already produces prompts; the orientation hint in the BFL prompt is sufficient for basic portrait guidance
