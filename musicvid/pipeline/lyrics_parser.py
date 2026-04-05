"""Lyrics file parser — reads .txt files and returns timed lyrics segments."""

import json
import re

import anthropic


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


def align_with_claude(whisper_segments, file_lines):
    """Align correct lyrics text to Whisper timing using Claude API.

    Args:
        whisper_segments: list of dicts with start/end/text from Whisper.
        file_lines: list of correct lyrics strings (already filtered).

    Returns:
        list[dict] with keys: start (float), end (float), text (str).

    Raises:
        ValueError: If Claude returns invalid JSON after 2 attempts,
                    or if response items are missing required keys.
    """
    # Filter empty Whisper segments
    filtered_segments = [
        {"start": s["start"], "end": s["end"], "text": s["text"]}
        for s in whisper_segments if s["text"].strip()
    ]

    system_prompt = (
        "Jesteś asystentem do synchronizacji tekstu piosenek.\n"
        "Zwracaj WYŁĄCZNIE czysty JSON, bez markdown, bez komentarzy."
    )

    user_prompt = (
        "Mam transkrypcję Whisper (niedokładną) i poprawny tekst piosenki.\n"
        "Dopasuj każdą linię poprawnego tekstu do segmentu Whisper który\n"
        "najbardziej jej odpowiada — na podstawie podobieństwa brzmienia,\n"
        "kolejności w piosence i kontekstu.\n\n"
        "Zasady:\n"
        "- Zachowaj kolejność — linie z pliku pojawiają się w tej samej kolejności co w piosence\n"
        "- Każda linia z pliku musi być przypisana do dokładnie jednego segmentu Whisper\n"
        "- Jeśli jest więcej segmentów Whisper niż linii w pliku — scal sąsiednie segmenty\n"
        "  (użyj start pierwszego i end ostatniego segmentu w grupie)\n"
        "- Jeśli jest więcej linii w pliku niż segmentów Whisper — podziel dostępny\n"
        "  czas równomiernie dla nadmiarowych linii po ostatnim segmencie\n"
        "- Puste linie w pliku są już usunięte — ignoruj je\n\n"
        f"Segmenty Whisper (z niedokładnym tekstem):\n{json.dumps(filtered_segments, ensure_ascii=False)}\n\n"
        f"Poprawne linie z pliku:\n{json.dumps(file_lines, ensure_ascii=False)}\n\n"
        'Zwróć JSON:\n[{"start": float, "end": float, "text": "poprawna linia z pliku"}]'
    )

    last_error = None
    for attempt in range(2):
        client = anthropic.Anthropic()
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        text = response.content[0].text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1])

        try:
            result = json.loads(text)
        except json.JSONDecodeError as e:
            last_error = e
            continue

        # Validate structure
        for item in result:
            for key in ("start", "end", "text"):
                if key not in item:
                    raise ValueError(f"Alignment result missing required key: {key}")

        return result

    raise ValueError(f"Failed to parse Claude alignment response after 2 attempts: {last_error}")


def merge_whisper_with_lyrics_file(whisper_segments, lyrics_lines, audio_duration):
    """Deterministically align lyrics file lines to Whisper timing.

    Uses proportional grouping: maps N Whisper segments to M lyrics lines
    handling N==M, N>M, and N<M cases. Timing corrections applied after.

    Args:
        whisper_segments: list of dicts with start/end/text from Whisper.
        lyrics_lines: list of non-empty lyrics strings from the .txt file.
        audio_duration: total audio duration in seconds.

    Returns:
        list[dict] with keys: start (float), end (float), text (str),
        sorted chronologically.

    Raises:
        ValueError: If lyrics_lines is empty.
    """
    if not lyrics_lines:
        raise ValueError("lyrics_lines is empty — no lines to align")

    # Filter empty Whisper segments
    segments = [s for s in whisper_segments if s["text"].strip()]

    if not segments:
        count = len(lyrics_lines)
        seg_dur = audio_duration / count
        result = [
            {"start": i * seg_dur, "end": (i + 1) * seg_dur, "text": lyrics_lines[i]}
            for i in range(count)
        ]
        return _apply_timing_corrections(result, audio_duration)

    n_seg = len(segments)
    n_lines = len(lyrics_lines)

    if n_seg == n_lines:
        result = [
            {"start": segments[i]["start"], "end": segments[i]["end"], "text": lyrics_lines[i]}
            for i in range(n_lines)
        ]
    elif n_seg > n_lines:
        segments_per_line = n_seg / n_lines
        result = []
        for i, line in enumerate(lyrics_lines):
            seg_start_idx = round(i * segments_per_line)
            seg_end_idx = min(round((i + 1) * segments_per_line), n_seg)
            group = segments[seg_start_idx:seg_end_idx]
            if not group:
                continue
            result.append({"start": group[0]["start"], "end": group[-1]["end"], "text": line})
    else:
        lines_per_seg = n_lines / n_seg
        result = []
        for i, seg in enumerate(segments):
            line_start_idx = round(i * lines_per_seg)
            line_end_idx = min(round((i + 1) * lines_per_seg), n_lines)
            group_lines = lyrics_lines[line_start_idx:line_end_idx]
            if not group_lines:
                continue
            seg_duration = seg["end"] - seg["start"]
            time_per_line = seg_duration / len(group_lines)
            for j, line in enumerate(group_lines):
                result.append({
                    "start": seg["start"] + j * time_per_line,
                    "end": seg["start"] + (j + 1) * time_per_line,
                    "text": line,
                })

    return _apply_timing_corrections(result, audio_duration)


def _apply_timing_corrections(result, audio_duration):
    """Apply timing corrections to aligned subtitle list.

    Order per spec:
    1. Extend subtitles shorter than 0.8s
    2. Cap subtitles longer than 8s
    3. Enforce minimum 0.15s gap between consecutive subtitles
    4. Apply -0.05s pre-display offset (clamped to 0)
    5. Clamp all end times to audio_duration
    """
    # Step 1 & 2: min/max duration
    for item in result:
        duration = item["end"] - item["start"]
        if duration < 0.8:
            item["end"] = item["start"] + 0.8
        elif duration > 8.0:
            item["end"] = item["start"] + 8.0

    # Step 3: enforce minimum 0.15s gap (process in order)
    for i in range(len(result) - 1):
        if result[i]["end"] > result[i + 1]["start"] - 0.15:
            result[i]["end"] = result[i + 1]["start"] - 0.15

    # Step 4: pre-display offset (-0.05s, clamped to 0)
    for item in result:
        item["start"] = max(0.0, item["start"] - 0.05)

    # Step 5: clamp end to audio_duration
    for item in result:
        item["end"] = min(item["end"], audio_duration)

    result.sort(key=lambda x: x["start"])
    return result
