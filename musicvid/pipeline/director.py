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
    msg = f"Here is the audio analysis for the music video:\n\n{json.dumps(analysis, indent=2)}"
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
        lines = text.split("\n")
        text = "\n".join(lines[1:-1])

    plan = json.loads(text)
    plan = _validate_scene_plan(plan, analysis["duration"])

    if output_dir:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        with open(output_path / "scene_plan.json", "w") as f:
            json.dump(plan, f, indent=2)

    return plan
