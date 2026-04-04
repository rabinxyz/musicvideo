import numpy as np
from PIL import Image
from unittest.mock import patch, MagicMock
from musicvid.pipeline.logo_overlay import compute_margin, compute_logo_size, get_logo_position, load_logo


class TestComputeMargin:
    def test_1920x1080(self):
        assert compute_margin(1920, 1080) == 54

    def test_1080x1920_portrait(self):
        assert compute_margin(1080, 1920) == 54

    def test_1080x1080_square(self):
        assert compute_margin(1080, 1080) == 54

    def test_3840x2160_4k(self):
        assert compute_margin(3840, 2160) == 108


class TestComputeLogoSize:
    def test_auto_1920x1080(self):
        w, h = compute_logo_size(1920, 1080, 100, 50)
        assert w == 230
        # height scaled proportionally: 50 * (230/100) = 115
        assert h == 115

    def test_auto_1080x1920_portrait(self):
        w, h = compute_logo_size(1080, 1920, 100, 50)
        assert w == 129
        assert h == 64

    def test_explicit_size(self):
        w, h = compute_logo_size(1920, 1080, 100, 50, requested_size=200)
        assert w == 200
        assert h == 100

    def test_auto_1080x1080_square(self):
        w, h = compute_logo_size(1080, 1080, 100, 50)
        assert w == 129
        assert h == 64


class TestGetLogoPosition:
    def test_top_left_1080p(self):
        x, y = get_logo_position("top-left", (200, 100), (1920, 1080))
        assert x == 54
        assert y == 54

    def test_top_right_1080p(self):
        x, y = get_logo_position("top-right", (200, 100), (1920, 1080))
        assert x == 1920 - 200 - 54
        assert y == 54

    def test_bottom_left_1080p(self):
        x, y = get_logo_position("bottom-left", (200, 100), (1920, 1080))
        assert x == 54
        assert y == 1080 - 100 - 54

    def test_bottom_right_1080p(self):
        x, y = get_logo_position("bottom-right", (200, 100), (1920, 1080))
        assert x == 1920 - 200 - 54
        assert y == 1080 - 100 - 54

    def test_portrait(self):
        x, y = get_logo_position("top-left", (130, 65), (1080, 1920))
        assert x == 54
        assert y == 54

    def test_4k(self):
        x, y = get_logo_position("top-left", (400, 200), (3840, 2160))
        assert x == 108
        assert y == 108


class TestLoadLogo:
    def _create_test_png(self, tmp_path, width=100, height=50, mode="RGBA"):
        """Create a test PNG file and return its path."""
        img = Image.new(mode, (width, height), (255, 0, 0, 255) if mode == "RGBA" else (255, 0, 0))
        path = tmp_path / "logo.png"
        img.save(str(path))
        return str(path)

    def test_load_png_returns_rgba(self, tmp_path):
        path = self._create_test_png(tmp_path)
        result = load_logo(path, 200, 100, 0.85)
        assert result.mode == "RGBA"

    def test_load_png_correct_size(self, tmp_path):
        path = self._create_test_png(tmp_path)
        result = load_logo(path, 200, 100, 0.85)
        assert result.size == (200, 100)

    def test_load_png_opacity(self, tmp_path):
        path = self._create_test_png(tmp_path)
        result = load_logo(path, 200, 100, 0.85)
        alpha = np.array(result.getchannel("A"))
        assert alpha.max() == 216  # int(255 * 0.85)

    def test_load_png_full_opacity(self, tmp_path):
        path = self._create_test_png(tmp_path)
        result = load_logo(path, 200, 100, 1.0)
        alpha = np.array(result.getchannel("A"))
        assert alpha.max() == 255

    def test_load_rgb_png_converts_to_rgba(self, tmp_path):
        path = self._create_test_png(tmp_path, mode="RGB")
        result = load_logo(path, 200, 100, 0.85)
        assert result.mode == "RGBA"

    def test_file_not_found(self):
        import pytest
        with pytest.raises(FileNotFoundError):
            load_logo("/nonexistent/logo.png", 200, 100, 0.85)
