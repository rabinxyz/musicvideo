"""Lyrics file parser — reads .txt files and returns timed lyrics segments."""

import re


_TIMESTAMP_RE = re.compile(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?\s+(.+)$")


def _parse_timestamp(match):
    """Convert regex match to seconds."""
    groups = match.groups()
    if groups[2] is not None:
        # HH:MM:SS
        return int(groups[0]) * 3600 + int(groups[1]) * 60 + int(groups[2])
    else:
        # MM:SS
        return int(groups[0]) * 60 + int(groups[1])


def parse(lyrics_path, audio_duration):
    """Parse a lyrics .txt file and return timed segments.

    Args:
        lyrics_path: Path to the .txt lyrics file.
        audio_duration: Total audio duration in seconds.

    Returns:
        list[dict] with keys: start (float), end (float), text (str).

    Raises:
        ValueError: If the file is empty or contains only whitespace.
    """
    with open(lyrics_path, "r", encoding="utf-8") as f:
        raw_lines = f.readlines()

    lines = [line.strip() for line in raw_lines if line.strip()]

    if not lines:
        raise ValueError(f"Lyrics file is empty: {lyrics_path}")

    # Detect variant from first non-empty line
    first_match = _TIMESTAMP_RE.match(lines[0])
    if first_match:
        return _parse_variant_b(lines, audio_duration)
    else:
        return _parse_variant_a(lines, audio_duration)


def _parse_variant_a(lines, audio_duration):
    """Variant A: no timestamps — distribute evenly across audio duration."""
    count = len(lines)
    segment = audio_duration / count
    result = []
    for i, text in enumerate(lines):
        start = round(i * segment, 1)
        end = round((i + 1) * segment - 0.3, 1)
        result.append({"start": start, "end": end, "text": text})
    return result


def _parse_variant_b(lines, audio_duration):
    """Variant B: lines prefixed with MM:SS or HH:MM:SS timestamps."""
    entries = []
    for line in lines:
        match = _TIMESTAMP_RE.match(line)
        if not match:
            continue
        timestamp = float(_parse_timestamp(match))
        text = match.group(4).strip()
        entries.append({"timestamp": timestamp, "text": text})

    result = []
    for i, entry in enumerate(entries):
        start = entry["timestamp"]
        if i + 1 < len(entries):
            end = round(entries[i + 1]["timestamp"] - 0.3, 1)
        else:
            end = round(audio_duration - 1.0, 1)
        result.append({"start": start, "end": end, "text": entry["text"]})
    return result
