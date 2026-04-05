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
    if duration > 300:  # over 5 minutes
        max_scenes = 15
    elif duration > 180:  # 3-5 minutes
        max_scenes = 12
    else:  # under 3 minutes
        max_scenes = 10

    msg = f"Here is the audio analysis for the music video:\n\n{json.dumps(analysis, indent=2)}"
    msg += f"\n\nGenerate a maximum of {max_scenes} scenes."
    if style_override and style_override != "auto":
        msg += f"\n\nIMPORTANT: Override the style to be '{style_override}' regardless of the mood detected in the audio."
    return msg


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

    # Default animate/motion_prompt fields if Claude omitted them
    for scene in plan["scenes"]:
        if "animate" not in scene:
            scene["animate"] = False
        if "motion_prompt" not in scene:
            scene["motion_prompt"] = ""

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

    text = response_text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()

    try:
        plan = json.loads(text)
    except json.JSONDecodeError:
        basic = _repair_truncated_json(text)
        if basic is not None and json.loads(basic).get("scenes"):
            repaired = basic
        else:
            repaired = _repair_truncated_json_aggressive(text)
        if repaired is not None:
            plan = json.loads(repaired)
        else:
            retry_message = user_message + "\n\nIMPORTANT: Your previous response was truncated. Be more concise: keep visual_prompt under 100 characters and limit to 8 scenes maximum."
            response_text = _call_claude(system_prompt, retry_message)
            text = response_text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            text = text.strip()
            plan = json.loads(text)
    plan = _validate_scene_plan(plan, analysis["duration"])

    if output_dir:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        with open(output_path / "scene_plan.json", "w") as f:
            json.dump(plan, f, indent=2)

    return plan
