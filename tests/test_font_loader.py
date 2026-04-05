"""Tests for font_loader module."""

from unittest.mock import patch, MagicMock
from pathlib import Path

import pytest

from musicvid.pipeline.font_loader import get_font_path, _download_montserrat


class TestGetFontPathCustom:
    """Tests for custom font path."""

    def test_custom_path_returned_when_exists(self, tmp_path):
        font_file = tmp_path / "custom.ttf"
        font_file.write_bytes(b"fake font")
        result = get_font_path(custom_path=str(font_file))
        assert result == str(font_file)

    def test_custom_path_raises_when_missing(self):
        with pytest.raises(FileNotFoundError):
            get_font_path(custom_path="/nonexistent/font.ttf")


class TestGetFontPathFallback:
    """Tests for fallback chain."""

    @patch("musicvid.pipeline.font_loader._find_system_fallback")
    @patch("musicvid.pipeline.font_loader._download_montserrat")
    @patch("musicvid.pipeline.font_loader.ASSETS_FONTS_DIR")
    def test_tries_download_when_no_local(self, mock_dir, mock_download, mock_fallback):
        mock_local = MagicMock()
        mock_local.exists.return_value = False
        mock_dir.__truediv__ = MagicMock(return_value=mock_local)

        mock_download.return_value = "/downloaded/Montserrat-Light.ttf"

        result = get_font_path()
        assert result == "/downloaded/Montserrat-Light.ttf"
        mock_download.assert_called_once()

    @patch("musicvid.pipeline.font_loader._find_system_fallback")
    @patch("musicvid.pipeline.font_loader._download_montserrat")
    @patch("musicvid.pipeline.font_loader.ASSETS_FONTS_DIR")
    def test_uses_system_fallback_when_download_fails(self, mock_dir, mock_download, mock_fallback):
        mock_local = MagicMock()
        mock_local.exists.return_value = False
        mock_dir.__truediv__ = MagicMock(return_value=mock_local)

        mock_download.return_value = None
        mock_fallback.return_value = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

        result = get_font_path()
        assert result == "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

    @patch("musicvid.pipeline.font_loader._find_system_fallback", return_value=None)
    @patch("musicvid.pipeline.font_loader._download_montserrat", return_value=None)
    @patch("musicvid.pipeline.font_loader.ASSETS_FONTS_DIR")
    def test_raises_when_nothing_available(self, mock_dir, mock_download, mock_fallback):
        mock_local = MagicMock()
        mock_local.exists.return_value = False
        mock_dir.__truediv__ = MagicMock(return_value=mock_local)

        with pytest.raises(RuntimeError, match="No suitable font found"):
            get_font_path()


class TestDownloadMontserrat:
    """Tests for the download helper."""

    @patch("musicvid.pipeline.font_loader.requests.get")
    def test_downloads_ttf_directly(self, mock_get, tmp_path):
        fake_ttf = b"fake ttf data"
        mock_resp = MagicMock()
        mock_resp.content = fake_ttf
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        with patch("musicvid.pipeline.font_loader.ASSETS_FONTS_DIR", tmp_path):
            result = _download_montserrat()

        assert result is not None
        assert result == str(tmp_path / "Montserrat-Light.ttf")
        assert (tmp_path / "Montserrat-Light.ttf").read_bytes() == fake_ttf
        mock_get.assert_called_once_with(
            "https://github.com/google/fonts/raw/main/ofl/montserrat/Montserrat-Light.ttf",
            timeout=30,
        )

    @patch(
        "musicvid.pipeline.font_loader.requests.get",
        side_effect=Exception("network error"),
    )
    def test_returns_none_on_failure(self, mock_get, tmp_path):
        with patch("musicvid.pipeline.font_loader.ASSETS_FONTS_DIR", tmp_path):
            result = _download_montserrat()

        assert result is None
