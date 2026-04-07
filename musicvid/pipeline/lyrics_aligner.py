"""Lyrics aligner — fuzzy-match Whisper segments to lyrics file text."""

import re

from rapidfuzz import fuzz

NON_VOCAL = {"muzyka", "music", "instrumental", "muzyk", "intro"}

MAX_WORDS_PER_SUBTITLE = 7

MIN_RATIO = 45


def _is_vocal(seg):
    """Return True if segment contains actual vocals (not noise/music)."""
    text = seg["text"].strip().lower()
    text_clean = re.sub(r"[\[\]()♪♫ ]", "", text)
    if text_clean in NON_VOCAL:
        return False
    if text_clean.startswith("muzy"):
        return False
    if len(text_clean) < 3:
        return False
    if len(text.split()) == 1 and len(text_clean) < 8:
        return False
    return True


def _prepare_lyrics(lyrics_path):
    """Read lyrics file, strip brackets, return (all_words, word_string).

    all_words: list of original-case words from the file.
    word_string: lowercase joined string for fuzzy matching.
    """
    with open(lyrics_path, encoding="utf-8") as f:
        raw = f.read()

    # Remove stage directions in brackets: [Refren:], [x2], [Bridge], etc.
    raw = re.sub(r"\[.*?\]", "", raw, flags=re.DOTALL)

    # Split into words — ignore line breaks
    all_words = re.findall(r"\b\w+\b", raw, re.UNICODE)

    # Continuous lowercase string for fuzzy matching
    word_string = " ".join(w.lower() for w in all_words)

    return all_words, word_string


def _split_segment(seg):
    """Split a segment with >MAX_WORDS_PER_SUBTITLE words into shorter subtitles."""
    words = seg["text"].split()
    if len(words) <= MAX_WORDS_PER_SUBTITLE:
        return [seg]

    groups = []
    for i in range(0, len(words), MAX_WORDS_PER_SUBTITLE):
        groups.append(" ".join(words[i : i + MAX_WORDS_PER_SUBTITLE]))

    duration = seg["end"] - seg["start"]
    time_per = duration / len(groups)

    result = []
    for i, group in enumerate(groups):
        result.append(
            {
                "start": round(seg["start"] + i * time_per, 2),
                "end": round(seg["start"] + (i + 1) * time_per - 0.1, 2),
                "text": group,
                "words": [],
                "match_ratio": seg.get("match_ratio", 0),
            }
        )
    return result


def align_lyrics(whisper_segments, lyrics_path):
    """Align Whisper segments to lyrics file using fuzzy sliding-cursor match.

    Args:
        whisper_segments: list of dicts with start/end/text from Whisper.
        lyrics_path: path to .txt lyrics file.

    Returns:
        list[dict] with keys: start, end, text, match_ratio, words.
    """
    all_words, word_string = _prepare_lyrics(lyrics_path)

    if not all_words:
        return []

    vocal_segments = [s for s in whisper_segments if _is_vocal(s)]

    cursor = 0  # character position in word_string
    result_lyrics = []

    for seg in vocal_segments:
        whisper_raw = seg["text"].strip()
        whisper_clean = " ".join(re.findall(r"\b\w+\b", whisper_raw.lower()))

        if not whisper_clean or len(whisper_clean) < 3:
            continue

        # Search window: from cursor forward
        max_window = max(300, len(whisper_clean) * 6)
        search_text = word_string[cursor : cursor + max_window]

        if not search_text.strip():
            break  # end of lyrics text

        # Sliding window — find best matching substring
        target_len = len(whisper_clean)
        best_ratio = 0
        best_pos = 0

        step = max(1, target_len // 8)

        for i in range(0, max(1, len(search_text) - target_len + 1), step):
            window = search_text[i : i + int(target_len * 1.5)]
            ratio = fuzz.partial_ratio(whisper_clean, window)
            if ratio > best_ratio:
                best_ratio = ratio
                best_pos = i

        if best_ratio >= MIN_RATIO:
            abs_pos = cursor + best_pos
            matched_len = int(target_len * 1.3)

            # Convert character position to word index
            words_before = word_string[:abs_pos].split()
            word_idx = len(words_before)

            n_words = max(1, len(whisper_clean.split()))
            original_words = all_words[word_idx : word_idx + n_words]
            matched_text = " ".join(original_words)

            result_lyrics.append(
                {
                    "start": seg["start"],
                    "end": seg["end"],
                    "text": matched_text,
                    "match_ratio": best_ratio,
                    "words": [],
                }
            )

            new_cursor = abs_pos + matched_len
            cursor = min(new_cursor, len(word_string))

            print(f"  {seg['start']:.1f}s: '{matched_text}' (ratio={best_ratio})")
        else:
            # Weak match — use Whisper text as fallback
            print(
                f"  WARN {seg['start']:.1f}s: weak match ({best_ratio}) — Whisper: '{whisper_raw}'"
            )
            result_lyrics.append(
                {
                    "start": seg["start"],
                    "end": seg["end"],
                    "text": whisper_raw,
                    "match_ratio": best_ratio,
                    "words": [],
                }
            )
            cursor += max(50, len(whisper_clean))

    # Split long segments into shorter subtitles
    final = []
    for seg in result_lyrics:
        final.extend(_split_segment(seg))

    return final
