# Fix Runway API (400 Error) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the Runway Gen-4 API returning 400 Bad Request by correcting the ratio and model name, and improve error visibility in the CLI.

**Architecture:** Two surgical edits — `video_animator.py` gets correct payload values, `musicvid.py` gets richer error output. Test assertions updated to match new values.

**Tech Stack:** Python 3.11+, requests, pytest, unittest.mock

---

### Task 1: Fix payload values in video_animator.py and update tests

**Files:**
- Modify: `musicvid/pipeline/video_animator.py:46-50`
- Modify: `tests/test_video_animator.py:174-176`

- [ ] **Step 1: Update test assertion to expect new values**

Edit `tests/test_video_animator.py`, lines 174-176, changing:
```python
        assert payload["model"] == "gen4_turbo"
        assert payload["duration"] == 5
        assert payload["ratio"] == "1280:768"
```
to:
```python
        assert payload["model"] == "gen4.5"
        assert payload["duration"] == 5
        assert payload["ratio"] == "1280:720"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m pytest tests/test_video_animator.py::TestAnimateImage::test_submit_called_with_correct_payload -v
```
Expected: FAIL — `AssertionError: assert 'gen4_turbo' == 'gen4.5'`

- [ ] **Step 3: Fix payload in video_animator.py**

Edit `musicvid/pipeline/video_animator.py` lines 46-50, changing:
```python
    payload = {
        "model": "gen4_turbo",
        "promptImage": image_b64,
        "promptText": motion_prompt,
        "duration": duration,
        "ratio": "1280:768",
    }
```
to:
```python
    payload = {
        "model": "gen4.5",
        "promptImage": image_b64,
        "promptText": motion_prompt,
        "duration": duration,
        "ratio": "1280:720",
    }
```

- [ ] **Step 4: Run all video animator tests**

```bash
python3 -m pytest tests/test_video_animator.py -v
```
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add musicvid/pipeline/video_animator.py tests/test_video_animator.py
git commit -m "fix: use gen4.5 model and 1280:720 ratio for Runway API"
```

---

### Task 2: Improve error output in musicvid.py

**Files:**
- Modify: `musicvid/musicvid.py:443-445`

- [ ] **Step 1: Write a failing test for the improved error output**

In `tests/test_musicvid_cli.py` (or the relevant CLI test file that covers the animate path), add a test that patches `animate_image` to raise an `HTTPError` with a `.response` attribute and checks that the response status code and body are printed.

First, find the relevant test file:
```bash
grep -l "animate_image\|Animation failed" tests/
```

Then add this test to the class that tests the animation error path:
```python
@patch.dict(os.environ, {"RUNWAY_API_KEY": "test-key", "ANTHROPIC_API_KEY": "test-key", "PEXELS_API_KEY": "test-key"})
@patch("musicvid.musicvid.animate_image")
# ... (keep all existing mocks from surrounding tests)
def test_animate_error_shows_runway_response(self, mock_animate, ...):
    import requests as req_lib
    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.text = '{"error":"invalid ratio"}'
    http_err = req_lib.exceptions.HTTPError("400 Bad Request")
    http_err.response = mock_resp
    mock_animate.side_effect = http_err

    result = runner.invoke(cli, [..., "--animate", "always", "--mode", "stock", "--preset", "full"])
    assert "Runway error: 400" in result.output
    assert "invalid ratio" in result.output
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m pytest tests/test_musicvid_cli.py -k "test_animate_error_shows_runway_response" -v
```
Expected: FAIL — "Runway error" not found in output.

- [ ] **Step 3: Fix the except block in musicvid.py**

Edit `musicvid/musicvid.py` line 443-444, changing:
```python
                except Exception as exc:
                    click.echo(f"  ⚠ Animation failed for scene {idx + 1}: {exc} — Ken Burns fallback")
```
to:
```python
                except Exception as exc:
                    if hasattr(exc, 'response') and exc.response is not None:
                        click.echo(f"  Runway error: {exc.response.status_code} {exc.response.text[:300]}")
                    click.echo(f"  ⚠ Animation failed for scene {idx + 1}: {exc} — Ken Burns fallback")
```

- [ ] **Step 4: Run the new test**

```bash
python3 -m pytest tests/test_musicvid_cli.py -k "test_animate_error_shows_runway_response" -v
```
Expected: PASS.

- [ ] **Step 5: Run full test suite to check for regressions**

```bash
python3 -m pytest tests/ -v
```
Expected: All tests PASS (no regressions).

- [ ] **Step 6: Commit**

```bash
git add musicvid/musicvid.py tests/test_musicvid_cli.py
git commit -m "fix: show Runway HTTP response details on animation failure"
```

---

## Self-Review

**Spec coverage:**
- ✅ Poprawka 1 (ratio): Task 1 changes "1280:768" → "1280:720"
- ✅ Poprawka 2 (model): Task 1 changes "gen4_turbo" → "gen4.5"
- ✅ Poprawka 3 (error display): Task 2 adds response detail printing
- ✅ AC: animate_image() sends correct ratio and model — covered by updated test_submit_called_with_correct_payload

**Placeholder scan:** No TBDs, no vague instructions. All code blocks complete.

**Type consistency:** No cross-task type references. Tasks are independent.
