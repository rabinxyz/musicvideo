"""Stage 1.5: AI clip selection for social media clips."""
import json

import anthropic


def select_clip(analysis, clip_duration):
    """Ask Claude to select the best fragment of the song for a social media clip.

    Args:
        analysis: Audio analysis dict (lyrics, sections, duration, bpm).
        clip_duration: Desired clip duration in seconds (15, 20, 25, or 30).

    Returns:
        dict with keys: start (float), end (float), reason (str).
    """
    client = anthropic.Anthropic()

    segments = [
        {"start": seg["start"], "end": seg["end"], "text": seg["text"]}
        for seg in analysis.get("lyrics", [])
    ]
    sections = analysis.get("sections", [])
    duration = analysis.get("duration", 0)

    user_message = (
        f"You are selecting a {clip_duration}-second clip from a song for social media "
        f"(Instagram Reels, YouTube Shorts, TikTok).\n\n"
        f"Song duration: {duration:.1f}s\n"
        f"BPM: {analysis.get('bpm', 'unknown')}\n"
        f"Sections: {json.dumps(sections)}\n"
        f"Lyrics with timestamps:\n{json.dumps(segments, indent=2)}\n\n"
        f"Rules:\n"
        f"- Prefer the chorus (most recognizable part)\n"
        f"- Avoid the first 5 seconds unless no other option\n"
        f"- Do not cut in the middle of a word or lyric line\n"
        f"- Start on a musical phrase boundary if possible\n"
        f"- End at the end of a lyric line, not mid-word\n"
        f"- The clip length (end - start) must be exactly {clip_duration}s \u00b12s\n\n"
        f"Return ONLY valid JSON (no markdown, no explanation):\n"
        f'{{"start": <float seconds>, "end": <float seconds>, "reason": "<brief>"}}'
    )

    for _attempt in range(2):
        try:
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=256,
                messages=[{"role": "user", "content": user_message}],
            )
            result = json.loads(response.content[0].text.strip())
            if "start" in result and "end" in result:
                return result
        except (json.JSONDecodeError, KeyError, IndexError):
            pass

    # Fallback: center of song
    fallback_start = max(0.0, (duration - clip_duration) / 2)
    return {
        "start": fallback_start,
        "end": fallback_start + clip_duration,
        "reason": "Fallback: center of song",
    }
