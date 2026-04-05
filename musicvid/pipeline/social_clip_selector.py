"""Select 3 non-overlapping clips from different song sections for social media reels."""
import json

import anthropic


def select_social_clips(analysis, clip_duration):
    """Ask Claude to select 3 non-overlapping clips from different song sections.

    Args:
        analysis: Audio analysis dict (lyrics, sections, duration, bpm).
        clip_duration: Desired clip duration in seconds (15, 20, 25, 30, 45, or 60).

    Returns:
        dict with key "clips": list of 3 dicts, each with id, start, end, section, reason.
    """
    client = anthropic.Anthropic()

    segments = [
        {"start": seg["start"], "end": seg["end"], "text": seg["text"]}
        for seg in analysis.get("lyrics", [])
    ]
    sections = analysis.get("sections", [])
    duration = analysis.get("duration", 0)

    long_clip_rules = ""
    if clip_duration >= 30:
        long_clip_rules = (
            f"- Pełny refren (priorytet najwyższy) — prefer a complete chorus if available\n"
            f"- Wyraźny hook melodyczny — include the main melodic hook\n"
            f"- Kompletną myśl tekstową — no mid-sentence cuts, full lyrical thought\n"
            f"- Zaczyna się na początku frazy muzycznej — start at a musical phrase boundary\n"
            f"- Kończy na naturalnej pauzie lub końcu frazy — end at a natural pause or phrase end\n"
        )

    user_message = (
        f"You are selecting 3 clips of {clip_duration} seconds each from a song for social media "
        f"(Instagram Reels, YouTube Shorts, TikTok).\n\n"
        f"Song duration: {duration:.1f}s\n"
        f"BPM: {analysis.get('bpm', 'unknown')}\n"
        f"Sections: {json.dumps(sections)}\n"
        f"Lyrics with timestamps:\n{json.dumps(segments, indent=2)}\n\n"
        f"Rules:\n"
        f"- Select exactly 3 clips, each {clip_duration}s long (end - start = {clip_duration} ±2s)\n"
        f"- Clips must NOT overlap and must have at least 5s gap between them\n"
        f"- Each clip must come from a DIFFERENT section (intro/verse/chorus/bridge/outro)\n"
        f"- Prefer fragments with strong lyrics and clear melody\n"
        f"- Each clip must start at the beginning of a phrase — not mid-word\n"
        f"- Each clip must end at the end of a lyric line\n"
        f"{long_clip_rules}"
        f"- Describe briefly why you chose each fragment\n\n"
        f"Return ONLY valid JSON (no markdown, no explanation):\n"
        f'{{"clips": [\n'
        f'  {{"id": "A", "start": <float>, "end": <float>, "section": "<section>", "reason": "<brief>"}},\n'
        f'  {{"id": "B", "start": <float>, "end": <float>, "section": "<section>", "reason": "<brief>"}},\n'
        f'  {{"id": "C", "start": <float>, "end": <float>, "section": "<section>", "reason": "<brief>"}}\n'
        f"]}}"
    )

    for _attempt in range(2):
        try:
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=512,
                messages=[{"role": "user", "content": user_message}],
            )
            result = json.loads(response.content[0].text.strip())
            if "clips" in result and len(result["clips"]) == 3:
                valid = all(
                    "start" in c and "end" in c and "id" in c
                    for c in result["clips"]
                )
                if valid:
                    return result
        except (json.JSONDecodeError, KeyError, IndexError):
            pass

    # Fallback: 3 evenly spaced clips from the song
    spacing = duration / 4
    clips = []
    for i, clip_id in enumerate(["A", "B", "C"]):
        start = spacing * (i + 0.5)
        clips.append({
            "id": clip_id,
            "start": round(start, 1),
            "end": round(start + clip_duration, 1),
            "section": "unknown",
            "reason": "Fallback: evenly spaced",
        })
    return {"clips": clips}
