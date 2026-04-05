# Fix Director JSON Truncation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix JSONDecodeError in director.py caused by Claude generating scene plans that exceed max_tokens, producing truncated JSON.

**Architecture:** Five fixes applied to director.py and director_system.txt: increase max_tokens to 8192, improve markdown stripping, add scene count limits by duration, add visual_prompt length constraint in system prompt, and add truncated JSON repair with retry logic.

**Tech Stack:** Python 3.11+, anthropic SDK, unittest.mock, pytest

---

## File Map

- Modify: `musicvid/pipeline/director.py` — all runtime fixes
- Modify: `musicvid/prompts/director_system.txt` — add prompt constraints
- Modify: `tests/test_director.py` — add tests for new behavior

---

### Task 1: Increase max_tokens to 8192

**Files:**
- Modify: `musicvid/pipeline/director.py:31-36`
- Modify: `tests/test_director.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_director.py` inside `TestCreateScenePlan`:

```python
@patch("musicvid.pipeline.director.anthropic")
def test_calls_claude_with_8192_max_tokens(self, mock_anthropic, sample_analysis):
    mock_client = self._make_mock_client(mock_anthropic, self._base_plan())
    create_scene_plan(sample_analysis)
    call_kwargs = mock_client.messages.create.call_args[1]
    assert call_kwargs["max_tokens"] == 8192
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m pytest tests/test_director.py::TestCreateScenePlan::test_calls_claude_with_8192_max_tokens -v
```

Expected: FAIL — `assert 4096 == 8192`

- [ ] **Step 3: Change max_tokens in director.py**

In `musicvid/pipeline/director.py`, change line 35:

```python
# Before
        max_tokens=4096,
# After
        max_tokens=8192,
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python3 -m pytest tests/test_director.py::TestCreateScenePlan::test_calls_claude_with_8192_max_tokens -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add musicvid/pipeline/director.py tests/test_director.py
git commit -m "fix(director): increase max_tokens to 8192 to prevent JSON truncation"
```

---

### Task 2: Fix markdown stripping logic

The current code splits on newlines and joins `lines[1:-1]`, which breaks if Claude returns ```` ```json\n...\n``` ```` with content on the same line as the fence. Replace with a character-based approach.

**Files:**
- Modify: `musicvid/pipeline/director.py:79-84`
- Modify: `tests/test_director.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_director.py` inside `TestCreateScenePlan`:

```python
@patch("musicvid.pipeline.director.anthropic")
def test_strips_json_markdown_fence(self, mock_anthropic, sample_analysis):
    plan = self._base_plan()
    wrapped = "```json\n" + json.dumps(plan) + "\n```"
    mock_response = MagicMock()
    mock_response.content = [MagicMock()]
    mock_response.content[0].text = wrapped
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response
    mock_anthropic.Anthropic.return_value = mock_client
    result = create_scene_plan(sample_analysis)
    assert "overall_style" in result

@patch("musicvid.pipeline.director.anthropic")
def test_strips_plain_markdown_fence(self, mock_anthropic, sample_analysis):
    plan = self._base_plan()
    wrapped = "```\n" + json.dumps(plan) + "\n```"
    mock_response = MagicMock()
    mock_response.content = [MagicMock()]
    mock_response.content[0].text = wrapped
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response
    mock_anthropic.Anthropic.return_value = mock_client
    result = create_scene_plan(sample_analysis)
    assert "overall_style" in result
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_director.py::TestCreateScenePlan::test_strips_json_markdown_fence tests/test_director.py::TestCreateScenePlan::test_strips_plain_markdown_fence -v
```

Expected: FAIL (at least one, depending on edge case)

- [ ] **Step 3: Replace markdown stripping in create_scene_plan**

In `musicvid/pipeline/director.py`, replace:

```python
    text = response_text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1])
```

With:

```python
    text = response_text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_director.py::TestCreateScenePlan::test_strips_json_markdown_fence tests/test_director.py::TestCreateScenePlan::test_strips_plain_markdown_fence -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add musicvid/pipeline/director.py tests/test_director.py
git commit -m "fix(director): robust markdown fence stripping before JSON parse"
```

---

### Task 3: Add truncated JSON repair with retry

When `json.loads()` raises `JSONDecodeError`, attempt to repair by finding the last complete scene object. If repair fails, retry the Claude call once with a shorter-prompt instruction.

**Files:**
- Modify: `musicvid/pipeline/director.py`
- Modify: `tests/test_director.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_director.py` inside `TestCreateScenePlan`:

```python
@patch("musicvid.pipeline.director.anthropic")
def test_repairs_truncated_json(self, mock_anthropic, sample_analysis):
    """Should repair JSON truncated mid-string by finding last complete scene."""
    plan = self._base_plan()
    complete_json = json.dumps(plan)
    # Truncate in the middle — cut off last 20 chars
    truncated = complete_json[:-20]
    mock_response = MagicMock()
    mock_response.content = [MagicMock()]
    mock_response.content[0].text = truncated
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response
    mock_anthropic.Anthropic.return_value = mock_client
    result = create_scene_plan(sample_analysis)
    assert "scenes" in result
    assert len(result["scenes"]) > 0

@patch("musicvid.pipeline.director.anthropic")
def test_retries_when_json_unreperable(self, mock_anthropic, sample_analysis):
    """Should retry Claude call when truncated JSON is unreperable."""
    plan = self._base_plan()
    good_json = json.dumps(plan)
    # First call returns garbage, second returns valid JSON
    bad_response = MagicMock()
    bad_response.content = [MagicMock()]
    bad_response.content[0].text = '{"scenes": [{'  # unreperable
    good_response = MagicMock()
    good_response.content = [MagicMock()]
    good_response.content[0].text = good_json
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = [bad_response, good_response]
    mock_anthropic.Anthropic.return_value = mock_client
    result = create_scene_plan(sample_analysis)
    assert "scenes" in result
    assert mock_client.messages.create.call_count == 2
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_director.py::TestCreateScenePlan::test_repairs_truncated_json tests/test_director.py::TestCreateScenePlan::test_retries_when_json_unreperable -v
```

Expected: FAIL with JSONDecodeError

- [ ] **Step 3: Add `_repair_truncated_json` helper and update `create_scene_plan`**

In `musicvid/pipeline/director.py`, add after `_validate_scene_plan`:

```python
def _repair_truncated_json(text):
    """Try to repair truncated JSON by finding the last complete scene object.

    Returns fixed JSON string or None if unreperable.
    """
    # Find last complete scene: last '}' followed eventually by ']' closing scenes array
    # Strategy: find last '}' that is followed by optional whitespace then ']' or ','
    last_brace = text.rfind("}")
    if last_brace == -1:
        return None
    # Attempt to close the JSON after the last complete object
    candidate = text[: last_brace + 1]
    # Close scenes array and root object if not already closed
    if not candidate.rstrip().endswith("}"):
        return None
    # Count unclosed brackets/braces to determine what to close
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
```

Then replace the JSON parsing block in `create_scene_plan` (after `text = text.strip()`):

```python
    try:
        plan = json.loads(text)
    except json.JSONDecodeError:
        repaired = _repair_truncated_json(text)
        if repaired is not None:
            plan = json.loads(repaired)
        else:
            # Retry Claude with explicit brevity instruction
            retry_message = user_message + "\n\nIMPORTANT: Your previous response was truncated. Be more concise: keep visual_prompt under 100 characters and limit to 8 scenes maximum."
            response_text = _call_claude(system_prompt, retry_message)
            text = response_text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            text = text.strip()
            plan = json.loads(text)
```

The full updated `create_scene_plan` function becomes:

```python
def create_scene_plan(analysis, style_override=None, output_dir=None):
    """Create a scene plan using Claude API."""
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
        repaired = _repair_truncated_json(text)
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_director.py::TestCreateScenePlan::test_repairs_truncated_json tests/test_director.py::TestCreateScenePlan::test_retries_when_json_unreperable -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add musicvid/pipeline/director.py tests/test_director.py
git commit -m "fix(director): repair truncated JSON and retry Claude on unreperable truncation"
```

---

### Task 4: Add scene count limits by duration

**Files:**
- Modify: `musicvid/pipeline/director.py` — `_build_user_message`
- Modify: `tests/test_director.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_director.py` inside `TestCreateScenePlan`:

```python
@patch("musicvid.pipeline.director.anthropic")
def test_scene_limit_short_song(self, mock_anthropic, sample_analysis):
    """Songs under 3 minutes: limit 10 scenes in prompt."""
    short_analysis = dict(sample_analysis, duration=150.0)  # 2.5 min
    mock_client = self._make_mock_client(mock_anthropic, self._base_plan())
    create_scene_plan(short_analysis)
    call_kwargs = mock_client.messages.create.call_args[1]
    user_msg = call_kwargs["messages"][0]["content"]
    assert "10 scenes" in user_msg

@patch("musicvid.pipeline.director.anthropic")
def test_scene_limit_medium_song(self, mock_anthropic, sample_analysis):
    """Songs 3-5 minutes: limit 12 scenes in prompt."""
    medium_analysis = dict(sample_analysis, duration=240.0)  # 4 min
    mock_client = self._make_mock_client(mock_anthropic, self._base_plan())
    create_scene_plan(medium_analysis)
    call_kwargs = mock_client.messages.create.call_args[1]
    user_msg = call_kwargs["messages"][0]["content"]
    assert "12 scenes" in user_msg

@patch("musicvid.pipeline.director.anthropic")
def test_scene_limit_long_song(self, mock_anthropic, sample_analysis):
    """Songs over 5 minutes: limit 15 scenes in prompt."""
    long_analysis = dict(sample_analysis, duration=360.0)  # 6 min
    mock_client = self._make_mock_client(mock_anthropic, self._base_plan())
    create_scene_plan(long_analysis)
    call_kwargs = mock_client.messages.create.call_args[1]
    user_msg = call_kwargs["messages"][0]["content"]
    assert "15 scenes" in user_msg
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_director.py::TestCreateScenePlan::test_scene_limit_short_song tests/test_director.py::TestCreateScenePlan::test_scene_limit_medium_song tests/test_director.py::TestCreateScenePlan::test_scene_limit_long_song -v
```

Expected: FAIL — no scene limit in user message

- [ ] **Step 3: Update `_build_user_message` to include scene limit**

Replace `_build_user_message` in `musicvid/pipeline/director.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_director.py::TestCreateScenePlan::test_scene_limit_short_song tests/test_director.py::TestCreateScenePlan::test_scene_limit_medium_song tests/test_director.py::TestCreateScenePlan::test_scene_limit_long_song -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add musicvid/pipeline/director.py tests/test_director.py
git commit -m "fix(director): add scene count limits by song duration to reduce token usage"
```

---

### Task 5: Add visual_prompt length constraint to system prompt

**Files:**
- Modify: `musicvid/prompts/director_system.txt`
- Modify: `tests/test_director.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_director.py` inside `TestCreateScenePlan`:

```python
def test_system_prompt_contains_visual_prompt_length_constraint():
    """System prompt must instruct Claude to keep visual_prompt under 200 chars."""
    from musicvid.pipeline.director import _load_system_prompt
    prompt = _load_system_prompt()
    assert "200" in prompt
    assert "visual_prompt" in prompt
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m pytest tests/test_director.py::TestCreateScenePlan::test_system_prompt_contains_visual_prompt_length_constraint -v
```

Expected: FAIL

Note: This test is a free function inside the class body — add it as a method:

```python
@staticmethod
def test_system_prompt_contains_visual_prompt_length_constraint():
    from musicvid.pipeline.director import _load_system_prompt
    prompt = _load_system_prompt()
    assert "200" in prompt
    assert "visual_prompt" in prompt
```

- [ ] **Step 3: Add constraint to director_system.txt**

Open `musicvid/prompts/director_system.txt` and add to the IMPORTANT section at the bottom (before the last line):

```
- Each visual_prompt must be at most 200 characters. Be concise and specific — do not write long descriptions.
```

The IMPORTANT block becomes:
```
IMPORTANT:
- Scenes must cover the entire duration with no gaps
- Each scene should be 5-15 seconds long
- Transitions should align with beat times when possible
- Visual prompts must reference the scene's lyrics — be specific, not generic
- Match the number of scenes to the song structure
- Each visual_prompt must be at most 200 characters. Be concise and specific — do not write long descriptions.
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python3 -m pytest tests/test_director.py::TestCreateScenePlan::test_system_prompt_contains_visual_prompt_length_constraint -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add musicvid/prompts/director_system.txt tests/test_director.py
git commit -m "fix(director): add 200-char visual_prompt limit to system prompt"
```

---

### Task 6: Run full test suite and verify acceptance criteria

- [ ] **Step 1: Run all tests**

```bash
python3 -m pytest tests/ -v
```

Expected: all tests PASS (currently ~209 tests + new ones)

- [ ] **Step 2: Verify acceptance criteria**

Check against spec:
- `max_tokens=8192` ✓ (Task 1)
- `visual_prompt` ≤ 200 chars enforced in prompt ✓ (Task 5)
- Retry on truncated JSON ✓ (Task 3)
- Scene count limits by duration ✓ (Task 4)
- Markdown stripping robust ✓ (Task 2)

- [ ] **Step 3: Final commit if needed**

```bash
git add -A
git commit -m "fix(director): all JSON truncation fixes complete" 2>/dev/null || echo "nothing to commit"
```
