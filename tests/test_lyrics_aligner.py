"""Tests for musicvid.pipeline.lyrics_aligner."""

import unittest

from musicvid.pipeline.lyrics_aligner import align_lyrics, MIN_RATIO


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


class TestCursorAdvances(unittest.TestCase):
    """After matching segment 1, cursor advances so segment 2 searches forward."""

    def test_cursor_advances(self):
        """Two segments should match sequential parts of lyrics."""
        segments = [
            {"start": 28.0, "end": 32.0, "text": "Tylko w Bogu"},
            {"start": 33.0, "end": 37.0, "text": "moje jest zbawienie"},
        ]
        import tempfile, os
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("Tylko w Bogu moje jest zbawienie od Niego\n")
            path = f.name
        try:
            result = align_lyrics(segments, path)
            self.assertTrue(len(result) >= 2)
            # Second result should NOT re-match first words
            self.assertNotEqual(result[0]["text"], result[1]["text"])
        finally:
            os.unlink(path)


class TestFuzzyTypos(unittest.TestCase):
    """Whisper typos should still fuzzy-match to correct lyrics text."""

    def test_fuzzy_match_typos(self):
        """whisper 'tolko w bogu mojest' matches 'Tylko w Bogu moje jest'."""
        segments = [
            {"start": 28.0, "end": 35.0, "text": "tolko w bogu mojest zbawienie"},
        ]
        import tempfile, os
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("Tylko w Bogu moje jest zbawienie\n")
            path = f.name
        try:
            result = align_lyrics(segments, path)
            self.assertTrue(len(result) >= 1)
            self.assertGreaterEqual(result[0]["match_ratio"], MIN_RATIO)
            # Text should come from file, not Whisper
            self.assertIn("Bogu", result[0]["text"])
        finally:
            os.unlink(path)


class TestSequentialOrder(unittest.TestCase):
    """Results should be sorted chronologically."""

    def test_sequential(self):
        """lyrics[i]['start'] < lyrics[i+1]['start'] always."""
        segments = [
            {"start": 28.0, "end": 32.0, "text": "Tylko w Bogu"},
            {"start": 33.0, "end": 37.0, "text": "moje jest zbawienie"},
            {"start": 38.0, "end": 42.0, "text": "od Niego pochodzi"},
        ]
        import tempfile, os
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("Tylko w Bogu moje jest zbawienie od Niego pochodzi moc\n")
            path = f.name
        try:
            result = align_lyrics(segments, path)
            for i in range(len(result) - 1):
                self.assertLess(result[i]["start"], result[i + 1]["start"])
        finally:
            os.unlink(path)


class TestSplitLong(unittest.TestCase):
    """Long segments should be split into <=7-word subtitles."""

    def test_split_14_words(self):
        """Segment with 14 words splits into 2 subtitles of 7 words."""
        segments = [
            {
                "start": 28.0,
                "end": 40.0,
                "text": "Tylko w Bogu moje jest zbawienie od Niego pochodzi moc i chwala na wieki",
            },
        ]
        import tempfile, os
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("Tylko w Bogu moje jest zbawienie od Niego pochodzi moc i chwala na wieki\n")
            path = f.name
        try:
            result = align_lyrics(segments, path)
            self.assertTrue(len(result) >= 2)
            for r in result:
                self.assertLessEqual(len(r["text"].split()), 7)
            # Timing distributed evenly
            self.assertAlmostEqual(result[0]["start"], 28.0, places=1)
            self.assertGreater(result[1]["start"], result[0]["start"])
        finally:
            os.unlink(path)


class TestFirstSubtitleTiming(unittest.TestCase):
    """First subtitle should start at the Whisper segment time, not 0.0s."""

    def test_first_subtitle_timing(self):
        """lyrics[0]['start'] >= 28.0 (not 0.0s)."""
        segments = [
            {"start": 0.0, "end": 5.0, "text": "Muzyka"},
            {"start": 28.0, "end": 32.0, "text": "Tylko w Bogu moje"},
        ]
        import tempfile, os
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("Tylko w Bogu moje jest zbawienie\n")
            path = f.name
        try:
            result = align_lyrics(segments, path)
            self.assertTrue(len(result) >= 1)
            self.assertGreaterEqual(result[0]["start"], 28.0)
        finally:
            os.unlink(path)


class TestEnhancedVocalFiltering(unittest.TestCase):
    """Enhanced _is_vocal() filtering for noise tokens and Polish variants."""

    def _is_vocal(self, text):
        from musicvid.pipeline.lyrics_aligner import _is_vocal
        return _is_vocal({"text": text})

    def test_muzyk_in_non_vocal(self):
        """'muzyk' is in NON_VOCAL set and filtered out."""
        self.assertFalse(self._is_vocal("muzyk"))

    def test_intro_in_non_vocal(self):
        """'intro' is in NON_VOCAL set and filtered out."""
        self.assertFalse(self._is_vocal("intro"))

    def test_muzyka_still_filtered(self):
        """Original 'muzyka' still filtered."""
        self.assertFalse(self._is_vocal("Muzyka"))

    def test_startswith_muzy_catches_variants(self):
        """Polish variants like 'Muzykę', 'Muzykalny' caught by startswith."""
        self.assertFalse(self._is_vocal("Muzykę"))
        self.assertFalse(self._is_vocal("Muzykalny"))
        self.assertFalse(self._is_vocal("muzycy"))

    def test_single_short_word_filtered(self):
        """Single short words (< 8 chars) are filtered as noise tokens."""
        self.assertFalse(self._is_vocal("hmm"))
        self.assertFalse(self._is_vocal("Tak"))
        self.assertFalse(self._is_vocal("Oooo"))

    def test_single_long_word_passes(self):
        """Single word >= 8 chars passes the filter."""
        self.assertTrue(self._is_vocal("zbawienie"))
        self.assertTrue(self._is_vocal("Alleluja!"))

    def test_multi_word_short_passes(self):
        """Multi-word segments pass even if individual words are short."""
        self.assertTrue(self._is_vocal("Bogu moje"))
        self.assertTrue(self._is_vocal("Pan jest"))

    def test_real_lyrics_pass(self):
        """Real Polish Christian lyrics pass the filter."""
        self.assertTrue(self._is_vocal("Tylko w Bogu moje jest zbawienie"))
        self.assertTrue(self._is_vocal("Pan jest pasterzem moim"))

    def test_instrumental_still_filtered(self):
        """Original 'instrumental' still filtered."""
        self.assertFalse(self._is_vocal("instrumental"))

    def test_intro_with_alignment(self):
        """'Intro' segment at start is filtered during alignment."""
        import tempfile, os
        segments = [
            {"start": 0.0, "end": 10.0, "text": "Intro"},
            {"start": 28.0, "end": 32.0, "text": "Tylko w Bogu moje jest zbawienie"},
        ]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("Tylko w Bogu moje jest zbawienie\n")
            path = f.name
        try:
            result = align_lyrics(segments, path)
            texts = " ".join(r["text"] for r in result)
            self.assertNotIn("Intro", texts)
            self.assertTrue(len(result) >= 1)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
