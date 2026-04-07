"""Tests for musicvid.pipeline.lyrics_aligner."""

import unittest

from musicvid.pipeline.lyrics_aligner import align_lyrics


class TestNoiseFiltering(unittest.TestCase):
    """Noise segments like 'Muzyka' or '♪' should be filtered out."""

    def test_noise_filtered(self):
        """Segment 'Muzyka' at 0.0s is filtered, not in results."""
        segments = [
            {"start": 0.0, "end": 5.0, "text": "Muzyka"},
            {"start": 28.0, "end": 32.0, "text": "Tylko w Bogu moje jest zbawienie"},
        ]
        import tempfile, os
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("Tylko w Bogu moje jest zbawienie\n")
            path = f.name
        try:
            result = align_lyrics(segments, path)
            texts = [r["text"] for r in result]
            self.assertNotIn("Muzyka", " ".join(texts))
            self.assertTrue(len(result) >= 1)
        finally:
            os.unlink(path)

    def test_music_symbols_filtered(self):
        """Segments with only ♪ symbols are filtered."""
        segments = [
            {"start": 0.0, "end": 3.0, "text": "♪♪♪"},
            {"start": 28.0, "end": 32.0, "text": "Pan jest pasterzem moim"},
        ]
        import tempfile, os
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("Pan jest pasterzem moim\n")
            path = f.name
        try:
            result = align_lyrics(segments, path)
            self.assertTrue(len(result) >= 1)
            self.assertNotIn("♪", result[0]["text"])
        finally:
            os.unlink(path)


class TestBracketsIgnored(unittest.TestCase):
    """[Refren:] and similar brackets in lyrics file should be stripped."""

    def test_brackets_removed(self):
        """Lyrics file has '[Refren:]' — it does not appear in results."""
        segments = [
            {"start": 28.0, "end": 32.0, "text": "Tylko w Bogu"},
        ]
        import tempfile, os
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("[Refren:]\nTylko w Bogu moje jest zbawienie\n")
            path = f.name
        try:
            result = align_lyrics(segments, path)
            for r in result:
                self.assertNotIn("[Refren:]", r["text"])
                self.assertNotIn("Refren", r["text"])
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
