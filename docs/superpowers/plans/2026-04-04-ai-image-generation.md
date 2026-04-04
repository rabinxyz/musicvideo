# AI Image Generation Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `--mode ai` to the pipeline so DALL-E 3 generates one image per scene, assembled into the final video with Ken Burns effect and subtitles.

**Architecture:** New `image_generator` module replaces `stock_fetcher` when `--mode ai`. CLI routes to the correct Stage 3 based on mode flag. Assembler already handles ImageClip — no assembler changes needed.

**Tech Stack:** OpenAI Python SDK (DALL-E 3), requests, tenacity, pytest + unittest.mock

---

## File Structure

| Action | File | Responsibility |
|--------|------|---------------|
| Create | `musicvid/pipeline/image_generator.py` | DALL-E 3 image generation per scene |
| Create | `tests/test_image_generator.py` | Unit tests for image generator |
| Modify | `musicvid/musicvid.py` | Route `--mode ai` to image_generator, cache image_manifest |
| Modify | `tests/test_cli.py` | CLI integration tests for `--mode ai` |

---

### Task 1: Image Generator — Core Function with Tests

**Files:**
- Create: `tests/test_image_generator.py`
- Create: `musicvid/pipeline/image_generator.py`

- [ ] **Step 1: Write failing test — returns correct number of image paths**

```python
"""Tests for the AI image generator pipeline stage."""

import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


class TestGenerateImages:
    """Tests for generate_images()."""

    @patch("musicvid.pipeline.image_generator.requests")
    @patch("musicvid.pipeline.image_generator.openai")
    def test_returns_correct_number_of_paths(self, mock_openai, mock_requests, tmp_path):
        from musicvid.pipeline.image_generator import generate_images

        scene_plan = {
            "scenes": [
                {"visual_prompt": "mountain sunrise golden light", "start": 0.0, "end": 5.0},
                {"visual_prompt": "calm water reflection", "start": 5.0, "end": 10.0},
            ]
        }

        mock_client = MagicMock()
        mock_openai.OpenAI.return_value = mock_client
        mock_image = MagicMock()
        mock_image.url = "https://example.com/image.png"
        mock_response = MagicMock()
        mock_response.data = [mock_image]
        mock_client.images.generate.return_value = mock_response

        mock_http_response = MagicMock()
        mock_http_response.content = b"fake png data"
        mock_requests.get.return_value = mock_http_response

        result = generate_images(scene_plan, str(tmp_path))

        assert len(result) == 2
        assert all(p.endswith(".png") for p in result)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_image_generator.py::TestGenerateImages::test_returns_correct_number_of_paths -v`
Expected: FAIL — ModuleNotFoundError (image_generator doesn't exist yet)

- [ ] **Step 3: Write minimal implementation**

Create `musicvid/pipeline/image_generator.py`:

```python
"""Stage 3 (AI mode): Generate images with DALL-E 3."""

import os
from pathlib import Path

import openai
import requests
from tenacity import retry, stop_after_attempt, wait_exponential


PROTESTANT_DISCLAIMER = (
    "Protestant Christian aesthetic, no religious figures, "
    "no Catholic symbols, no rosary, no stained glass with figures, "
    "no crucifix, no Madonna, no saints, no monks, no papal imagery, "
    "no incense burner, no tabernacle, no confessional, "
    "no Byzantine icons, cinematic 16:9, photorealistic, high quality"
)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _generate_image(client, prompt):
    """Call DALL-E 3 to generate a single image."""
    response = client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size="1792x1024",
        quality="standard",
        n=1,
    )
    return response.data[0].url


def generate_images(scene_plan, output_dir):
    """Generate one DALL-E 3 image per scene.

    Args:
        scene_plan: Scene plan dict from Stage 2.
        output_dir: Directory to save generated images.

    Returns:
        list of image file paths in scene order.
    """
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise EnvironmentError(
            "OPENAI_API_KEY not set. Export it or add to .env file."
        )

    client = openai.OpenAI(api_key=api_key)
    scenes = scene_plan.get("scenes", [])
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    image_paths = []

    for i, scene in enumerate(scenes):
        visual_prompt = scene.get("visual_prompt", "nature landscape")
        full_prompt = f"{visual_prompt}, {PROTESTANT_DISCLAIMER}"

        image_url = _generate_image(client, full_prompt)

        dest = output_path / f"scene_{i:03d}.png"
        response = requests.get(image_url)
        response.raise_for_status()
        dest.write_bytes(response.content)

        image_paths.append(str(dest))

    return image_paths
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_image_generator.py::TestGenerateImages::test_returns_correct_number_of_paths -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add musicvid/pipeline/image_generator.py tests/test_image_generator.py
git commit -m "feat: add image_generator with DALL-E 3 and first test"
```

---

### Task 2: Image Generator — Protestant Disclaimer and Error Tests

**Files:**
- Modify: `tests/test_image_generator.py`

- [ ] **Step 1: Write failing test — every prompt contains Protestant disclaimer**

Add to `TestGenerateImages` in `tests/test_image_generator.py`:

```python
    @patch("musicvid.pipeline.image_generator.requests")
    @patch("musicvid.pipeline.image_generator.openai")
    def test_every_prompt_contains_protestant_disclaimer(self, mock_openai, mock_requests, tmp_path):
        from musicvid.pipeline.image_generator import generate_images, PROTESTANT_DISCLAIMER

        scene_plan = {
            "scenes": [
                {"visual_prompt": "mountain sunrise", "start": 0.0, "end": 5.0},
                {"visual_prompt": "calm water", "start": 5.0, "end": 10.0},
                {"visual_prompt": "sunset horizon", "start": 10.0, "end": 15.0},
            ]
        }

        mock_client = MagicMock()
        mock_openai.OpenAI.return_value = mock_client
        mock_image = MagicMock()
        mock_image.url = "https://example.com/image.png"
        mock_response = MagicMock()
        mock_response.data = [mock_image]
        mock_client.images.generate.return_value = mock_response

        mock_http_response = MagicMock()
        mock_http_response.content = b"fake png data"
        mock_requests.get.return_value = mock_http_response

        generate_images(scene_plan, str(tmp_path))

        calls = mock_client.images.generate.call_args_list
        assert len(calls) == 3
        for call in calls:
            prompt = call[1]["prompt"] if "prompt" in call[1] else call[0][0]
            assert PROTESTANT_DISCLAIMER in prompt
```

- [ ] **Step 2: Run test to verify it passes** (implementation already appends disclaimer)

Run: `python3 -m pytest tests/test_image_generator.py::TestGenerateImages::test_every_prompt_contains_protestant_disclaimer -v`
Expected: PASS

- [ ] **Step 3: Write failing test — raises EnvironmentError when OPENAI_API_KEY missing**

Add to `TestGenerateImages`:

```python
    @patch.dict(os.environ, {}, clear=True)
    def test_raises_error_when_api_key_missing(self, tmp_path):
        from musicvid.pipeline.image_generator import generate_images

        scene_plan = {"scenes": [{"visual_prompt": "test", "start": 0.0, "end": 5.0}]}

        with pytest.raises(EnvironmentError, match="OPENAI_API_KEY"):
            generate_images(scene_plan, str(tmp_path))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_image_generator.py::TestGenerateImages::test_raises_error_when_api_key_missing -v`
Expected: PASS

- [ ] **Step 5: Write failing test — retry on API error**

Add to `TestGenerateImages`:

```python
    @patch("musicvid.pipeline.image_generator.requests")
    @patch("musicvid.pipeline.image_generator.openai")
    def test_retry_on_api_error(self, mock_openai, mock_requests, tmp_path):
        from musicvid.pipeline.image_generator import generate_images

        scene_plan = {"scenes": [{"visual_prompt": "test", "start": 0.0, "end": 5.0}]}

        mock_client = MagicMock()
        mock_openai.OpenAI.return_value = mock_client
        mock_openai.APIError = type("APIError", (Exception,), {})

        mock_image = MagicMock()
        mock_image.url = "https://example.com/image.png"
        mock_success = MagicMock()
        mock_success.data = [mock_image]

        # Fail twice, succeed on third attempt
        mock_client.images.generate.side_effect = [
            mock_openai.APIError("rate limit"),
            mock_openai.APIError("server error"),
            mock_success,
        ]

        mock_http_response = MagicMock()
        mock_http_response.content = b"fake png"
        mock_requests.get.return_value = mock_http_response

        result = generate_images(scene_plan, str(tmp_path))

        assert len(result) == 1
        assert mock_client.images.generate.call_count == 3
```

- [ ] **Step 6: Run test to verify it passes**

Run: `python3 -m pytest tests/test_image_generator.py::TestGenerateImages::test_retry_on_api_error -v`
Expected: PASS (tenacity retry handles it)

Note: The `@retry` decorator retries on any exception by default. If this test fails because tenacity doesn't catch the mock `APIError`, update the retry decorator to add `retry=retry_if_exception_type(Exception)`.

- [ ] **Step 7: Run all image generator tests**

Run: `python3 -m pytest tests/test_image_generator.py -v`
Expected: All 4 tests PASS

- [ ] **Step 8: Commit**

```bash
git add tests/test_image_generator.py
git commit -m "test: add disclaimer, missing key, and retry tests for image_generator"
```

---

### Task 3: CLI Integration — Route --mode ai to Image Generator

**Files:**
- Modify: `musicvid/musicvid.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing CLI test — mode ai calls image_generator instead of stock_fetcher**

Add to `TestCLI` in `tests/test_cli.py`:

```python
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.generate_images")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    def test_mode_ai_calls_image_generator(
        self, mock_analyze, mock_direct, mock_gen_images, mock_assemble, runner, tmp_path
    ):
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")

        mock_analyze.return_value = {
            "lyrics": [], "beats": [0.0, 0.5], "bpm": 120.0,
            "duration": 10.0, "sections": [{"label": "verse", "start": 0.0, "end": 10.0}],
            "mood_energy": "contemplative", "language": "en",
        }
        mock_direct.return_value = {
            "overall_style": "contemplative",
            "color_palette": ["#aaa"],
            "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                               "position": "center-bottom", "animation": "fade"},
            "scenes": [{"section": "verse", "start": 0.0, "end": 10.0,
                         "visual_prompt": "test", "motion": "static",
                         "transition": "cut", "overlay": "none"}],
        }
        mock_gen_images.return_value = [str(tmp_path / "scene_000.png")]

        output_dir = tmp_path / "output"
        result = runner.invoke(cli, [
            str(audio_file),
            "--output", str(output_dir),
            "--mode", "ai",
        ])

        assert result.exit_code == 0
        mock_gen_images.assert_called_once()
        mock_assemble.assert_called_once()

        # Check that fetch_manifest passed to assembler uses image paths
        call_kwargs = mock_assemble.call_args[1]
        manifest = call_kwargs["fetch_manifest"]
        assert manifest[0]["video_path"].endswith(".png")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_cli.py::TestCLI::test_mode_ai_calls_image_generator -v`
Expected: FAIL — `generate_images` is not imported in musicvid.py

- [ ] **Step 3: Modify musicvid.py to support --mode ai**

In `musicvid/musicvid.py`, add the import at the top (after the stock_fetcher import):

```python
from musicvid.pipeline.image_generator import generate_images
```

Then replace the Stage 3 section (lines 68-77) with:

```python
    # Stage 3: Fetch Videos or Generate Images
    if mode == "ai":
        image_manifest = load_cache(str(cache_dir), "image_manifest.json") if not new else None
        if image_manifest and _image_files_exist(image_manifest):
            click.echo("[3/4] Generating images... CACHED (skipped)")
            fetch_manifest = image_manifest
        else:
            click.echo("[3/4] Generating AI images...")
            image_paths = generate_images(scene_plan, str(cache_dir))
            fetch_manifest = [
                {"scene_index": i, "video_path": path, "search_query": scene["visual_prompt"]}
                for i, (path, scene) in enumerate(zip(image_paths, scene_plan["scenes"]))
            ]
            save_cache(str(cache_dir), "image_manifest.json", fetch_manifest)
        click.echo(f"  Generated: {len(fetch_manifest)} images")
    else:
        fetch_manifest = load_cache(str(cache_dir), "video_manifest.json") if not new else None
        if fetch_manifest and _video_files_exist(fetch_manifest):
            click.echo("[3/4] Fetching videos... CACHED (skipped)")
        else:
            click.echo("[3/4] Fetching stock videos...")
            fetch_manifest = fetch_videos(scene_plan, output_dir=str(cache_dir))
            save_cache(str(cache_dir), "video_manifest.json", fetch_manifest)
        fetched = sum(1 for f in fetch_manifest if f["video_path"].endswith(".mp4"))
        click.echo(f"  Fetched: {fetched}/{len(fetch_manifest)} videos")
```

Also add this helper function after `_video_files_exist`:

```python
def _image_files_exist(manifest):
    """Check that all image files referenced in the manifest exist on disk."""
    return all(Path(entry["video_path"]).exists() for entry in manifest)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_cli.py::TestCLI::test_mode_ai_calls_image_generator -v`
Expected: PASS

- [ ] **Step 5: Write failing test — mode ai caching works**

Add to `TestCLI` in `tests/test_cli.py`:

```python
    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.generate_images")
    @patch("musicvid.musicvid.create_scene_plan")
    @patch("musicvid.musicvid.analyze_audio")
    def test_mode_ai_cache_skips_generation(
        self, mock_analyze, mock_direct, mock_gen_images, mock_assemble, runner, tmp_path
    ):
        """When cached image_manifest.json exists with valid files, skip generation."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")

        from musicvid.pipeline.cache import get_audio_hash
        audio_hash = get_audio_hash(str(audio_file))

        output_dir = tmp_path / "output"
        cache_dir = output_dir / "tmp" / audio_hash
        cache_dir.mkdir(parents=True)

        analysis_data = {
            "lyrics": [], "beats": [0.0], "bpm": 120.0,
            "duration": 10.0, "sections": [{"label": "verse", "start": 0.0, "end": 10.0}],
            "mood_energy": "contemplative", "language": "en",
        }
        scene_plan_data = {
            "overall_style": "contemplative",
            "color_palette": ["#aaa"],
            "subtitle_style": {"font_size": 48, "color": "#FFF", "outline_color": "#000",
                               "position": "center-bottom", "animation": "fade"},
            "scenes": [{"section": "verse", "start": 0.0, "end": 10.0,
                         "visual_prompt": "test", "motion": "static",
                         "transition": "cut", "overlay": "none"}],
        }

        # Create the cached image file
        image_path = cache_dir / "scene_000.png"
        image_path.write_bytes(b"fake png")

        import json
        manifest_data = [
            {"scene_index": 0, "video_path": str(image_path), "search_query": "test"},
        ]

        (cache_dir / "audio_analysis.json").write_text(json.dumps(analysis_data))
        (cache_dir / "scene_plan.json").write_text(json.dumps(scene_plan_data))
        (cache_dir / "image_manifest.json").write_text(json.dumps(manifest_data))

        result = runner.invoke(cli, [
            str(audio_file), "--output", str(output_dir), "--mode", "ai",
        ])

        assert result.exit_code == 0
        mock_gen_images.assert_not_called()
        mock_assemble.assert_called_once()
        assert "CACHED" in result.output
```

- [ ] **Step 6: Run test to verify it passes**

Run: `python3 -m pytest tests/test_cli.py::TestCLI::test_mode_ai_cache_skips_generation -v`
Expected: PASS

- [ ] **Step 7: Run full test suite**

Run: `python3 -m pytest tests/ -v`
Expected: All tests PASS (existing 39 + new 6 = 45)

- [ ] **Step 8: Commit**

```bash
git add musicvid/musicvid.py tests/test_cli.py
git commit -m "feat: route --mode ai to image_generator with caching"
```

---

### Task 4: Final Verification and Cleanup

**Files:**
- All files from previous tasks

- [ ] **Step 1: Run full test suite**

Run: `python3 -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 2: Verify no Catholic imagery keywords leak into prompts**

Run: `python3 -c "from musicvid.pipeline.image_generator import PROTESTANT_DISCLAIMER; banned = ['rosary', 'crucifix', 'Madonna', 'saints', 'monks', 'papal', 'incense', 'tabernacle', 'confessional', 'Byzantine']; assert all(word in PROTESTANT_DISCLAIMER for word in banned), 'Missing banned keywords'; print('All banned keywords present in disclaimer')"`
Expected: "All banned keywords present in disclaimer"

- [ ] **Step 3: Verify CLI accepts --mode ai**

Run: `python3 -m musicvid.musicvid --help`
Expected: Shows `--mode` option with `[stock|ai|hybrid]` choices

- [ ] **Step 4: Commit final state if any changes needed**

```bash
git add -A
git commit -m "feat: complete AI image generation mode with DALL-E 3"
```
