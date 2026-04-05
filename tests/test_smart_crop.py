"""Tests for smart_crop pipeline module."""

import os
import tempfile
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
        # Two faces: small (50x50=2500) and large (100x100=10000) → use large face center
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
    def test_smart_crop_calls_resize_with_target_dimensions(self, mock_Image, mock_detect_poi):
        mock_detect_poi.return_value = (512, 384)
        mock_pil_img = MagicMock()
        mock_pil_img.size = (1024, 768)
        mock_pil_img.convert.return_value = mock_pil_img
        mock_cropped = MagicMock()
        mock_resized = MagicMock()
        mock_pil_img.crop.return_value = mock_cropped
        mock_cropped.resize.return_value = mock_resized
        mock_Image.open.return_value = mock_pil_img
        mock_Image.LANCZOS = 1

        from musicvid.pipeline.smart_crop import smart_crop
        result = smart_crop("/fake/image.jpg", 1080, 1920)

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
        self.assertGreaterEqual(x1, 0)
        self.assertLessEqual(x2, 1024)


class TestBlurBgComposite(unittest.TestCase):
    @patch("musicvid.pipeline.smart_crop.smart_crop")
    @patch("musicvid.pipeline.smart_crop.Image")
    @patch("musicvid.pipeline.smart_crop.ImageFilter")
    def test_blur_bg_composite_pastes_sharp_on_blurred_bg(self, mock_filter, mock_Image, mock_smart_crop):
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
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            tmp_path = f.name
        try:
            convert_for_platform(tmp_path, "reels", style="blur-bg")
            mock_blur.assert_called_once_with(tmp_path, 1080, 1920)
            mock_result.save.assert_called_once()
        finally:
            os.unlink(tmp_path)
            stem = os.path.splitext(os.path.basename(tmp_path))[0]
            out = os.path.join(os.path.dirname(tmp_path), f"smart_{stem}.jpg")
            if os.path.exists(out):
                os.unlink(out)

    @patch("musicvid.pipeline.smart_crop.smart_crop")
    def test_convert_for_platform_reels_crop_calls_smart_crop(self, mock_crop):
        mock_result = MagicMock()
        mock_crop.return_value = mock_result

        from musicvid.pipeline.smart_crop import convert_for_platform
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
