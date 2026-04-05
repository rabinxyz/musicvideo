"""Stage 2: Scene direction using Claude API."""

import json
from pathlib import Path

import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential


PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def _load_system_prompt():
    """Load the director system prompt from file."""
    prompt_file = PROMPTS_DIR / "director_system.txt"
    return prompt_file.read_text()


def _build_user_message(analysis, style_override=None):
    """Build the user message for Claude with analysis data."""
    duration = analysis.get("duration", 0)
    bpm = analysis.get("bpm", 120.0)
    beats = analysis.get("beats", [])

    bar_duration = 4 * (60.0 / bpm)
    suggested_scene_count = max(4, int(duration / (bar_duration * 4)))

    # Downbeats: every 4th beat starting from index 0
    downbeats = beats[::4] if beats else []
    downbeats_preview = [round(d, 2) for d in downbeats[:20]]

    msg = f"Here is the audio analysis for the music video:\n\n{json.dumps(analysis, indent=2)}"
    msg += f"\n\nBPM: {bpm:.0f}"
    msg += f"\nBar duration (4 beats): {bar_duration:.2f}s"
    msg += f"\nOptimal scene duration (4 bars): {bar_duration * 4:.2f}s"
    msg += f"\nSuggested scene count for this song: {suggested_scene_count}"
    msg += f"\nDownbeats (every 4th beat, first 20): {downbeats_preview}"
    msg += f"\n\nSCENE LENGTH RULES:"
    msg += f"\n- Minimum scene: 2 bars = {bar_duration * 2:.2f}s"
    msg += f"\n- Optimal scene: 4 bars = {bar_duration * 4:.2f}s"
    msg += f"\n- Maximum scene: 8 bars = {bar_duration * 8:.2f}s"
    msg += f"\n- Target: {suggested_scene_count} scenes of ~{bar_duration * 4:.1f}s each"
    msg += f"\n- Each scene start/end should align with a downbeat from the list above"
    msg += f"\n\nGenerate approximately {suggested_scene_count} scenes (maximum {suggested_scene_count + 4})."

    # Section-based length guidance
    bar_duration_val = bar_duration
    section_lengths = {
        "intro":  (6 * bar_duration_val, 8 * bar_duration_val),
        "verse":  (4 * bar_duration_val, 6 * bar_duration_val),
        "chorus": (2 * bar_duration_val, 3 * bar_duration_val),
        "bridge": (4 * bar_duration_val, 8 * bar_duration_val),
        "outro":  (6 * bar_duration_val, 10 * bar_duration_val),
    }
    msg += f"\n\nDŁUGOŚCI SCEN (KRYTYCZNE — stosuj się dokładnie):"
    msg += f"\nBPM={bpm:.0f}, jeden takt = {bar_duration_val:.2f}s"
    msg += f"\n- intro:  {section_lengths['intro'][0]:.1f}s - {section_lengths['intro'][1]:.1f}s"
    msg += f"\n- verse:  {section_lengths['verse'][0]:.1f}s - {section_lengths['verse'][1]:.1f}s"
    msg += f"\n- chorus: {section_lengths['chorus'][0]:.1f}s - {section_lengths['chorus'][1]:.1f}s (KRÓTKIE = ENERGIA)"
    msg += f"\n- bridge: {section_lengths['bridge'][0]:.1f}s - {section_lengths['bridge'][1]:.1f}s"
    msg += f"\n- outro:  {section_lengths['outro'][0]:.1f}s - {section_lengths['outro'][1]:.1f}s"
    msg += f"\nNIE rób równych odcinków. Refren MUSI być krótszy niż zwrotka."

    if style_override and style_override != "auto":
        msg += f"\n\nIMPORTANT: Override the style to be '{style_override}' regardless of the mood detected in the audio."
    return msg


def _strip_markdown(text):
    """Strip markdown code fence from text if present."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return text.strip()


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=30))
def _call_claude(system_prompt, user_message):
    """Call Claude API with retry logic."""
    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=8192,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    return response.content[0].text


def _validate_scene_plan(plan, duration):
    """Validate and fix the scene plan to ensure it covers the full duration."""
    if not plan.get("scenes"):
        raise ValueError("Scene plan has no scenes")

    # Default master_style if Claude omitted it
    if "master_style" not in plan:
        plan["master_style"] = ""

    # Default animate/motion_prompt/lyrics_in_scene fields if Claude omitted them
    for scene in plan["scenes"]:
        if "animate" not in scene:
            scene["animate"] = False
        if "motion_prompt" not in scene:
            scene["motion_prompt"] = ""
        if "lyrics_in_scene" not in scene:
            scene["lyrics_in_scene"] = []

    plan["scenes"].sort(key=lambda s: s["start"])
    plan["scenes"][0]["start"] = 0.0
    plan["scenes"][-1]["end"] = duration

    return plan


def _repair_truncated_json(text):
    """Try to repair truncated JSON by finding the last complete scene object.

    Returns fixed JSON string or None if unreparable.
    """
    last_brace = text.rfind("}")
    if last_brace == -1:
        return None
    candidate = text[: last_brace + 1]
    open_braces = candidate.count("{") - candidate.count("}")
    open_brackets = candidate.count("[") - candidate.count("]")
    closing = "]" * open_brackets + "}" * open_braces
    if closing:
        candidate = candidate + closing
    try:
        json.loads(candidate)
        return candidate
    except json.JSONDecodeError:
        return None


def _repair_truncated_json_aggressive(text):
    """More aggressive repair: handle incomplete key-value pairs using a stack-based closer.

    Drops any trailing incomplete key-value pair, then closes open structures in correct order.
    Returns fixed JSON string or None if unreparable.
    """

    def _stack_closing(s):
        """Return the correct closing chars for all open structures in s."""
        stack = []
        in_string = False
        escape = False
        for c in s:
            if escape:
                escape = False
                continue
            if c == "\\":
                if in_string:
                    escape = True
                continue
            if c == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if c == "{":
                stack.append("}")
            elif c == "[":
                stack.append("]")
            elif c in "]}":
                if stack and stack[-1] == c:
                    stack.pop()
        return "".join(reversed(stack))

    # If the text ends inside an open string, find the start of that string
    # and check if it's an incomplete key. If so, drop back to the last comma.
    candidate = text
    in_string = False
    escape = False
    last_string_start = -1
    for i, c in enumerate(candidate):
        if escape:
            escape = False
            continue
        if c == "\\":
            if in_string:
                escape = True
            continue
        if c == '"':
            if not in_string:
                last_string_start = i
            in_string = not in_string

    if in_string:
        # We're inside an open string — check if it's a key (no colon after it)
        after_start = candidate[last_string_start + 1 :]
        is_key = ":" not in after_start
        if is_key:
            # Drop the incomplete key by cutting at the last comma before it
            last_comma = candidate.rfind(",", 0, last_string_start)
            if last_comma == -1:
                return None
            candidate = candidate[:last_comma]
        else:
            # It's a value string — close it
            candidate = candidate + '"'

    closing = _stack_closing(candidate)
    repaired = candidate + closing
    try:
        result = json.loads(repaired)
        scenes = result.get("scenes")
        if scenes and any("start" in s for s in scenes):
            return repaired
    except json.JSONDecodeError:
        pass
    return None


def create_scene_plan(analysis, style_override=None, output_dir=None):
    """Create a scene plan using Claude API.

    Args:
        analysis: Audio analysis dict from Stage 1.
        style_override: Optional style override (contemplative/joyful/worship/powerful).
        output_dir: Optional directory to save scene_plan.json.

    Returns:
        dict with keys: overall_style, color_palette, subtitle_style, scenes
    """
    system_prompt = _load_system_prompt()
    user_message = _build_user_message(analysis, style_override)

    response_text = _call_claude(system_prompt, user_message)

    text = _strip_markdown(response_text)

    try:
        plan = json.loads(text)
    except json.JSONDecodeError:
        plan = None
        basic = _repair_truncated_json(text)
        if basic is not None:
            parsed = json.loads(basic)
            if parsed.get("scenes"):
                plan = parsed
        if plan is None:
            aggressive = _repair_truncated_json_aggressive(text)
            if aggressive is not None:
                plan = json.loads(aggressive)
        if plan is None:
            retry_message = user_message + "\n\nIMPORTANT: Your previous response was truncated. Be more concise: keep visual_prompt under 100 characters and limit to 8 scenes maximum."
            response_text = _call_claude(system_prompt, retry_message)
            text = _strip_markdown(response_text)
            plan = json.loads(text)
    plan = _validate_scene_plan(plan, analysis["duration"])

    if output_dir:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        with open(output_path / "scene_plan.json", "w") as f:
            json.dump(plan, f, indent=2)

    return plan
