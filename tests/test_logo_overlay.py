import numpy as np
from PIL import Image
from unittest.mock import patch, MagicMock
from musicvid.pipeline.logo_overlay import compute_margin, compute_logo_size, get_logo_position, load_logo
from musicvid.pipeline.logo_overlay import apply_logo


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


class TestLoadLogoSvg:
    def _create_test_svg(self, tmp_path):
        """Create a minimal test SVG and return its path."""
        svg_content = '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="50"><rect width="100" height="50" fill="red"/></svg>'
        path = tmp_path / "logo.svg"
        path.write_text(svg_content)
        return str(path)

    @patch("musicvid.pipeline.logo_overlay.cairosvg")
    def test_load_svg_calls_cairosvg(self, mock_cairosvg, tmp_path):
        # cairosvg.svg2png returns a valid PNG bytes
        img = Image.new("RGBA", (200, 100), (255, 0, 0, 255))
        import io
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        mock_cairosvg.svg2png.return_value = buf.getvalue()

        path = self._create_test_svg(tmp_path)
        result = load_logo(path, 200, 100, 1.0)
        assert result.mode == "RGBA"
        assert result.size == (200, 100)
        mock_cairosvg.svg2png.assert_called_once()

    @patch("musicvid.pipeline.logo_overlay.cairosvg")
    def test_svg_renders_at_2x_for_retina(self, mock_cairosvg, tmp_path):
        img = Image.new("RGBA", (400, 200), (255, 0, 0, 255))
        import io
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        mock_cairosvg.svg2png.return_value = buf.getvalue()

        path = self._create_test_svg(tmp_path)
        load_logo(path, 200, 100, 1.0)
        call_kwargs = mock_cairosvg.svg2png.call_args
        # Should render at 2x size for retina sharpness
        assert call_kwargs[1]["output_width"] == 400
        assert call_kwargs[1]["output_height"] == 200

    def test_svg_without_cairosvg_raises(self, tmp_path):
        import pytest
        path = self._create_test_svg(tmp_path)
        with patch("musicvid.pipeline.logo_overlay.cairosvg", None):
            with pytest.raises(ImportError, match="cairosvg"):
                load_logo(path, 200, 100, 1.0)


class TestApplyLogo:
    def _create_test_png(self, tmp_path, width=100, height=50):
        img = Image.new("RGBA", (width, height), (255, 0, 0, 255))
        path = tmp_path / "logo.png"
        img.save(str(path))
        return str(path)

    @patch("musicvid.pipeline.logo_overlay.ImageClip")
    def test_apply_logo_creates_image_clip(self, mock_image_clip, tmp_path):
        logo_path = self._create_test_png(tmp_path)
        mock_clip = MagicMock()
        mock_clip.size = (1920, 1080)
        mock_clip.duration = 30.0

        mock_logo_clip = MagicMock()
        mock_image_clip.return_value = mock_logo_clip
        mock_logo_clip.with_duration.return_value = mock_logo_clip
        mock_logo_clip.with_position.return_value = mock_logo_clip

        result = apply_logo(mock_clip, logo_path, "top-left", None, 0.85)

        mock_image_clip.assert_called_once()
        mock_logo_clip.with_duration.assert_called_once_with(30.0)
        mock_logo_clip.with_position.assert_called_once()

    @patch("musicvid.pipeline.logo_overlay.ImageClip")
    def test_apply_logo_position_top_right(self, mock_image_clip, tmp_path):
        logo_path = self._create_test_png(tmp_path)
        mock_clip = MagicMock()
        mock_clip.size = (1920, 1080)
        mock_clip.duration = 10.0

        mock_logo_clip = MagicMock()
        mock_image_clip.return_value = mock_logo_clip
        mock_logo_clip.with_duration.return_value = mock_logo_clip
        mock_logo_clip.with_position.return_value = mock_logo_clip

        apply_logo(mock_clip, logo_path, "top-right", None, 0.85)

        pos_call = mock_logo_clip.with_position.call_args[0][0]
        # For 1080p with auto-size (12% of 1920 = 230): margin=54, x = 1920-230-54 = 1636
        assert pos_call[0] == 1920 - 230 - 54

    @patch("musicvid.pipeline.logo_overlay.ImageClip")
    def test_apply_logo_explicit_size(self, mock_image_clip, tmp_path):
        logo_path = self._create_test_png(tmp_path)
        mock_clip = MagicMock()
        mock_clip.size = (1920, 1080)
        mock_clip.duration = 10.0

        mock_logo_clip = MagicMock()
        mock_image_clip.return_value = mock_logo_clip
        mock_logo_clip.with_duration.return_value = mock_logo_clip
        mock_logo_clip.with_position.return_value = mock_logo_clip

        apply_logo(mock_clip, logo_path, "top-left", 200, 0.85)

        # Verify ImageClip was created (the numpy array passed should be 200px wide)
        arr = mock_image_clip.call_args[0][0]
        assert arr.shape[1] == 200  # width

    @patch("musicvid.pipeline.logo_overlay.ImageClip")
    def test_apply_logo_returns_logo_clip(self, mock_image_clip, tmp_path):
        logo_path = self._create_test_png(tmp_path)
        mock_clip = MagicMock()
        mock_clip.size = (1920, 1080)
        mock_clip.duration = 10.0

        mock_logo_clip = MagicMock()
        mock_image_clip.return_value = mock_logo_clip
        mock_logo_clip.with_duration.return_value = mock_logo_clip
        mock_logo_clip.with_position.return_value = mock_logo_clip

        result = apply_logo(mock_clip, logo_path, "top-left", None, 0.85)
        assert result is mock_logo_clip
