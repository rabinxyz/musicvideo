# Flux Image Generator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add multi-provider image generation (flux-dev, flux-pro, schnell, dalle) with positive-only prompt strategy and negative_prompt as a separate parameter.

**Architecture:** Replace the single DALL-E 3 generator with a provider-based system. Each provider (flux-dev, flux-pro, schnell, dalle) has its own generation function. Flux providers use fal.ai API with separate `negative_prompt` parameter. The director prompt is rewritten to use only positive descriptions — banned words never appear in prompts.

**Tech Stack:** fal-client (fal.ai API), openai (legacy DALL-E), requests, tenacity, click

---

### Task 1: Add fal-client dependency

**Files:**
- Modify: `musicvid/requirements.txt`
- Modify: `musicvid/.env.example`

- [ ] **Step 1: Add fal-client to requirements.txt**

Add `fal-client>=0.5.0` after the `openai` line in `musicvid/requirements.txt`:

```
openai>=1.50.0
fal-client>=0.5.0
```

- [ ] **Step 2: Update .env.example**

Replace the contents of `musicvid/.env.example` with:

```
ANTHROPIC_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here    # only for --provider dalle (optional)
PEXELS_API_KEY=your_key_here
FAL_KEY=your_key_here            # fal.ai — flux-dev, flux-pro, schnell (free $10 credits at https://fal.ai)
```

- [ ] **Step 3: Install the new dependency**

Run: `pip install fal-client>=0.5.0`

- [ ] **Step 4: Commit**

```bash
git add musicvid/requirements.txt musicvid/.env.example
git commit -m "chore: add fal-client dependency and FAL_KEY to .env.example"
```

---

### Task 2: Rewrite director_system.txt with positive prompt strategy

**Files:**
- Modify: `musicvid/prompts/director_system.txt`

- [ ] **Step 1: Rewrite director_system.txt**

Replace the entire contents of `musicvid/prompts/director_system.txt` with:

```
You are a music video director specializing in Protestant Christian worship music videos.

You will receive an audio analysis containing lyrics, beats, BPM, duration, sections, and mood/energy data.

Your job is to create a detailed scene plan for the music video as pure JSON (no markdown, no code fences).

PROMPT BUILDING RULES:
Every visual_prompt = [main motif] + [lighting] + [mood] + [technical style]
Describe ONLY what IS in the scene — never describe what is NOT there.
Never use any of the BANNED WORDS listed below in visual_prompt fields.

BANNED WORDS (never use these in any visual_prompt):
Catholic, rosary, Madonna, saint, cross with figure, stained glass,
church interior, religious, icon, Byzantine, papal, crucifix,
prayer beads, Maria, monastery, monk, nun, cathedral, chapel,
shrine, altar, candle altar, sacred heart, IHS

POSITIVE MOTIFS TO USE:
- Nature: golden wheat fields, mountain peaks, morning mist, calm lakes, ancient forests
- Light: golden hour sunlight, rays breaking through clouds, abstract light particles
- Spiritual: simple wooden cross on hillside, dove in flight, open Bible on wooden table
- People: silhouette with hands raised toward sky, person walking through field
- Abstract: golden light rays on dark background, floating particles of light

EXAMPLE PROMPTS (follow this style):
- "Golden wheat fields stretching to horizon, warm afternoon light, peaceful and serene, cinematic 16:9, photorealistic, high quality"
- "Mountain peaks emerging from morning mist, rays of sunlight breaking through clouds, majestic and awe-inspiring, cinematic 16:9, photorealistic, high quality"
- "Calm lake reflecting blue sky and white clouds, gentle ripples on water surface, tranquil and meditative, cinematic 16:9, photorealistic, high quality"
- "Simple wooden empty cross on green hillside, blue sky with clouds, peaceful and hopeful, cinematic 16:9, photorealistic, high quality"
- "Dove in flight against bright sky, wings spread wide, freedom and grace, cinematic 16:9, photorealistic, high quality"
- "Silhouette of person standing on hilltop with hands raised toward sky, dramatic sunset behind, cinematic 16:9, photorealistic, high quality"
- "Abstract golden light rays on dark background, particles of light floating, divine and transcendent atmosphere, cinematic 16:9, photorealistic, high quality"

STYLE RULES:
- Match visual energy to musical energy (quiet sections = calm visuals, climax = dramatic)
- Every prompt must end with "cinematic 16:9, photorealistic, high quality"

OUTPUT FORMAT (pure JSON):
{
  "overall_style": "contemplative|joyful|worship|powerful",
  "color_palette": ["#hex1", "#hex2", "#hex3"],
  "subtitle_style": {
    "font_size": 48,
    "color": "#FFFFFF",
    "outline_color": "#000000",
    "position": "center-bottom",
    "animation": "fade"
  },
  "scenes": [
    {
      "section": "intro|verse|chorus|bridge|outro",
      "start": 0.0,
      "end": 15.0,
      "visual_prompt": "Detailed positive description following the rules above",
      "motion": "slow_zoom_in|slow_zoom_out|pan_left|pan_right|static",
      "transition": "crossfade|cut|fade_black",
      "overlay": "none|particles|light_rays|bokeh"
    }
  ]
}

IMPORTANT:
- Scenes must cover the entire duration with no gaps
- Each scene should be 5-15 seconds long
- Transitions should align with beat times when possible
- Visual prompts should be specific enough for image generation
- Match the number of scenes to the song structure
```

- [ ] **Step 2: Commit**

```bash
git add musicvid/prompts/director_system.txt
git commit -m "feat: rewrite director prompt with positive-only strategy and banned words list"
```

---

### Task 3: Rewrite image_generator.py with multi-provider support

**Files:**
- Modify: `musicvid/pipeline/image_generator.py`

- [ ] **Step 1: Rewrite image_generator.py**

Replace the entire contents of `musicvid/pipeline/image_generator.py` with:

```python
"""Stage 3 (AI mode): Generate images with multiple providers."""

import os
from pathlib import Path

import fal_client
import openai
import requests
from tenacity import retry, stop_after_attempt, wait_exponential


NEGATIVE_PROMPT = (
    "catholic church interior, religious figures, icon, stained glass with people, "
    "cross with body crucifix, statue figurine, rosary prayer beads, altar tabernacle, "
    "monastery nun monk pope bishop, cathedral chapel shrine, byzantine painting, "
    "sacred heart with thorns, watermark text logo, ugly blurry low quality, nsfw"
)

FLUX_MODELS = {
    "flux-dev": "fal-ai/flux/dev",
    "flux-pro": "fal-ai/flux-pro",
    "schnell": "fal-ai/flux/schnell",
}

FLUX_STEPS = {
    "flux-dev": 28,
    "flux-pro": 28,
    "schnell": 4,
}


def _detect_provider(requested):
    """Validate that the API key for the requested provider is available."""
    if requested in FLUX_MODELS:
        if not os.environ.get("FAL_KEY", ""):
            raise EnvironmentError(
                "FAL_KEY not set. Register at https://fal.ai for free $10 credits, "
                "then export FAL_KEY or add to .env file."
            )
    elif requested == "dalle":
        if not os.environ.get("OPENAI_API_KEY", ""):
            raise EnvironmentError(
                "OPENAI_API_KEY not set. Export it or add to .env file."
            )
    else:
        raise ValueError(f"Unknown provider: {requested}. Choose from: flux-dev, flux-pro, schnell, dalle")


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _generate_flux(prompt, model_id, output_path, num_steps):
    """Call fal.ai Flux API to generate a single image."""
    result = fal_client.run(
        model_id,
        arguments={
            "prompt": prompt,
            "negative_prompt": NEGATIVE_PROMPT,
            "image_size": {"width": 1280, "height": 720},
            "num_inference_steps": num_steps,
            "guidance_scale": 3.5,
            "num_images": 1,
            "output_format": "jpeg",
        },
    )
    image_url = result["images"][0]["url"]
    response = requests.get(image_url)
    response.raise_for_status()
    Path(output_path).write_bytes(response.content)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _generate_dalle(client, prompt):
    """Call DALL-E 3 to generate a single image."""
    response = client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size="1792x1024",
        quality="standard",
        n=1,
    )
    return response.data[0].url


def generate_images(scene_plan, output_dir, provider="flux-dev"):
    """Generate one image per scene using the specified provider.

    Args:
        scene_plan: Scene plan dict from Stage 2.
        output_dir: Directory to save generated images.
        provider: One of flux-dev, flux-pro, schnell, dalle.

    Returns:
        list of image file paths in scene order.
    """
    _detect_provider(provider)

    scenes = scene_plan.get("scenes", [])
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    image_paths = []

    if provider == "dalle":
        client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        for i, scene in enumerate(scenes):
            visual_prompt = scene.get("visual_prompt", "nature landscape")
            full_prompt = f"{visual_prompt}, cinematic 16:9, photorealistic, high quality"

            image_url = _generate_dalle(client, full_prompt)

            dest = output_path / f"scene_{i:03d}.jpg"
            resp = requests.get(image_url)
            resp.raise_for_status()
            dest.write_bytes(resp.content)
            image_paths.append(str(dest))
    else:
        model_id = FLUX_MODELS[provider]
        num_steps = FLUX_STEPS[provider]
        for i, scene in enumerate(scenes):
            visual_prompt = scene.get("visual_prompt", "nature landscape")
            dest = output_path / f"scene_{i:03d}.jpg"

            _generate_flux(visual_prompt, model_id, str(dest), num_steps)
            image_paths.append(str(dest))

    return image_paths
```

- [ ] **Step 2: Commit**

```bash
git add musicvid/pipeline/image_generator.py
git commit -m "feat: rewrite image_generator with multi-provider support (flux-dev, flux-pro, schnell, dalle)"
```

---

### Task 4: Rewrite tests for multi-provider image_generator

**Files:**
- Modify: `tests/test_image_generator.py`

- [ ] **Step 1: Rewrite test_image_generator.py**

Replace the entire contents of `tests/test_image_generator.py` with:

```python
"""Tests for the multi-provider AI image generator pipeline stage."""

import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from tenacity import wait_none


BANNED_WORDS = [
    "catholic", "rosary", "madonna", "saint", "cross with figure",
    "stained glass", "church interior", "religious", "icon", "byzantine",
    "papal", "crucifix", "prayer beads", "maria", "monastery", "monk",
    "nun", "cathedral", "chapel", "shrine", "altar", "candle altar",
    "sacred heart", "ihs",
]


class TestFluxProvider:
    """Tests for Flux providers (flux-dev, flux-pro, schnell)."""

    @patch.dict(os.environ, {"FAL_KEY": "test-key"})
    @patch("musicvid.pipeline.image_generator.requests")
    @patch("musicvid.pipeline.image_generator.fal_client")
    def test_flux_dev_returns_correct_paths(self, mock_fal, mock_requests, tmp_path):
        from musicvid.pipeline.image_generator import generate_images

        scene_plan = {
            "scenes": [
                {"visual_prompt": "mountain sunrise golden light", "start": 0.0, "end": 5.0},
                {"visual_prompt": "calm water reflection", "start": 5.0, "end": 10.0},
            ]
        }

        mock_fal.run.return_value = {"images": [{"url": "https://example.com/image.jpg"}]}
        mock_http = MagicMock()
        mock_http.content = b"fake jpeg data"
        mock_requests.get.return_value = mock_http

        result = generate_images(scene_plan, str(tmp_path), provider="flux-dev")

        assert len(result) == 2
        assert all(p.endswith(".jpg") for p in result)

    @patch.dict(os.environ, {"FAL_KEY": "test-key"})
    @patch("musicvid.pipeline.image_generator.requests")
    @patch("musicvid.pipeline.image_generator.fal_client")
    def test_flux_dev_uses_correct_model_id(self, mock_fal, mock_requests, tmp_path):
        from musicvid.pipeline.image_generator import generate_images

        scene_plan = {"scenes": [{"visual_prompt": "test", "start": 0.0, "end": 5.0}]}
        mock_fal.run.return_value = {"images": [{"url": "https://example.com/image.jpg"}]}
        mock_http = MagicMock()
        mock_http.content = b"fake jpeg"
        mock_requests.get.return_value = mock_http

        generate_images(scene_plan, str(tmp_path), provider="flux-dev")

        mock_fal.run.assert_called_once()
        assert mock_fal.run.call_args[0][0] == "fal-ai/flux/dev"

    @patch.dict(os.environ, {"FAL_KEY": "test-key"})
    @patch("musicvid.pipeline.image_generator.requests")
    @patch("musicvid.pipeline.image_generator.fal_client")
    def test_flux_pro_uses_correct_model_id(self, mock_fal, mock_requests, tmp_path):
        from musicvid.pipeline.image_generator import generate_images

        scene_plan = {"scenes": [{"visual_prompt": "test", "start": 0.0, "end": 5.0}]}
        mock_fal.run.return_value = {"images": [{"url": "https://example.com/image.jpg"}]}
        mock_http = MagicMock()
        mock_http.content = b"fake jpeg"
        mock_requests.get.return_value = mock_http

        generate_images(scene_plan, str(tmp_path), provider="flux-pro")

        assert mock_fal.run.call_args[0][0] == "fal-ai/flux-pro"

    @patch.dict(os.environ, {"FAL_KEY": "test-key"})
    @patch("musicvid.pipeline.image_generator.requests")
    @patch("musicvid.pipeline.image_generator.fal_client")
    def test_schnell_uses_correct_model_and_steps(self, mock_fal, mock_requests, tmp_path):
        from musicvid.pipeline.image_generator import generate_images

        scene_plan = {"scenes": [{"visual_prompt": "test", "start": 0.0, "end": 5.0}]}
        mock_fal.run.return_value = {"images": [{"url": "https://example.com/image.jpg"}]}
        mock_http = MagicMock()
        mock_http.content = b"fake jpeg"
        mock_requests.get.return_value = mock_http

        generate_images(scene_plan, str(tmp_path), provider="schnell")

        assert mock_fal.run.call_args[0][0] == "fal-ai/flux/schnell"
        assert mock_fal.run.call_args[1]["arguments"]["num_inference_steps"] == 4

    @patch.dict(os.environ, {"FAL_KEY": "test-key"})
    @patch("musicvid.pipeline.image_generator.requests")
    @patch("musicvid.pipeline.image_generator.fal_client")
    def test_negative_prompt_is_separate_parameter(self, mock_fal, mock_requests, tmp_path):
        from musicvid.pipeline.image_generator import generate_images, NEGATIVE_PROMPT

        scene_plan = {"scenes": [{"visual_prompt": "mountain sunrise", "start": 0.0, "end": 5.0}]}
        mock_fal.run.return_value = {"images": [{"url": "https://example.com/image.jpg"}]}
        mock_http = MagicMock()
        mock_http.content = b"fake jpeg"
        mock_requests.get.return_value = mock_http

        generate_images(scene_plan, str(tmp_path), provider="flux-dev")

        args = mock_fal.run.call_args[1]["arguments"]
        assert args["negative_prompt"] == NEGATIVE_PROMPT
        assert NEGATIVE_PROMPT not in args["prompt"]

    @patch.dict(os.environ, {"FAL_KEY": "test-key"})
    @patch("musicvid.pipeline.image_generator.requests")
    @patch("musicvid.pipeline.image_generator.fal_client")
    def test_flux_retry_on_api_error(self, mock_fal, mock_requests, tmp_path):
        from musicvid.pipeline.image_generator import generate_images, _generate_flux

        scene_plan = {"scenes": [{"visual_prompt": "test", "start": 0.0, "end": 5.0}]}
        mock_fal.run.side_effect = [
            Exception("rate limit"),
            Exception("server error"),
            {"images": [{"url": "https://example.com/image.jpg"}]},
        ]
        mock_http = MagicMock()
        mock_http.content = b"fake jpeg"
        mock_requests.get.return_value = mock_http

        original_wait = _generate_flux.retry.wait
        _generate_flux.retry.wait = wait_none()
        try:
            result = generate_images(scene_plan, str(tmp_path), provider="flux-dev")
        finally:
            _generate_flux.retry.wait = original_wait

        assert len(result) == 1
        assert mock_fal.run.call_count == 3


class TestDalleProvider:
    """Tests for legacy DALL-E provider."""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("musicvid.pipeline.image_generator.requests")
    @patch("musicvid.pipeline.image_generator.openai")
    def test_dalle_returns_correct_paths(self, mock_openai, mock_requests, tmp_path):
        from musicvid.pipeline.image_generator import generate_images

        scene_plan = {
            "scenes": [
                {"visual_prompt": "mountain sunrise", "start": 0.0, "end": 5.0},
                {"visual_prompt": "calm water", "start": 5.0, "end": 10.0},
            ]
        }

        mock_client = MagicMock()
        mock_openai.OpenAI.return_value = mock_client
        mock_image = MagicMock()
        mock_image.url = "https://example.com/image.png"
        mock_response = MagicMock()
        mock_response.data = [mock_image]
        mock_client.images.generate.return_value = mock_response

        mock_http = MagicMock()
        mock_http.content = b"fake png data"
        mock_requests.get.return_value = mock_http

        result = generate_images(scene_plan, str(tmp_path), provider="dalle")

        assert len(result) == 2
        assert all(p.endswith(".jpg") for p in result)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("musicvid.pipeline.image_generator.requests")
    @patch("musicvid.pipeline.image_generator.openai")
    def test_dalle_prompt_has_no_negative_content(self, mock_openai, mock_requests, tmp_path):
        from musicvid.pipeline.image_generator import generate_images, NEGATIVE_PROMPT

        scene_plan = {"scenes": [{"visual_prompt": "mountain sunrise", "start": 0.0, "end": 5.0}]}

        mock_client = MagicMock()
        mock_openai.OpenAI.return_value = mock_client
        mock_image = MagicMock()
        mock_image.url = "https://example.com/image.png"
        mock_response = MagicMock()
        mock_response.data = [mock_image]
        mock_client.images.generate.return_value = mock_response

        mock_http = MagicMock()
        mock_http.content = b"fake png"
        mock_requests.get.return_value = mock_http

        generate_images(scene_plan, str(tmp_path), provider="dalle")

        prompt = mock_client.images.generate.call_args[1]["prompt"]
        assert NEGATIVE_PROMPT not in prompt
        assert "no " not in prompt.lower()

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("musicvid.pipeline.image_generator.requests")
    @patch("musicvid.pipeline.image_generator.openai")
    def test_dalle_retry_on_api_error(self, mock_openai, mock_requests, tmp_path):
        from musicvid.pipeline.image_generator import generate_images, _generate_dalle

        scene_plan = {"scenes": [{"visual_prompt": "test", "start": 0.0, "end": 5.0}]}

        mock_client = MagicMock()
        mock_openai.OpenAI.return_value = mock_client

        mock_image = MagicMock()
        mock_image.url = "https://example.com/image.png"
        mock_success = MagicMock()
        mock_success.data = [mock_image]

        mock_client.images.generate.side_effect = [
            Exception("rate limit"),
            Exception("server error"),
            mock_success,
        ]

        mock_http = MagicMock()
        mock_http.content = b"fake png"
        mock_requests.get.return_value = mock_http

        original_wait = _generate_dalle.retry.wait
        _generate_dalle.retry.wait = wait_none()
        try:
            result = generate_images(scene_plan, str(tmp_path), provider="dalle")
        finally:
            _generate_dalle.retry.wait = original_wait

        assert len(result) == 1
        assert mock_client.images.generate.call_count == 3


class TestProviderDetection:
    """Tests for provider validation and error messages."""

    @patch.dict(os.environ, {}, clear=True)
    def test_raises_error_when_fal_key_missing(self, tmp_path):
        from musicvid.pipeline.image_generator import generate_images

        scene_plan = {"scenes": [{"visual_prompt": "test", "start": 0.0, "end": 5.0}]}

        with pytest.raises(EnvironmentError, match="FAL_KEY"):
            generate_images(scene_plan, str(tmp_path), provider="flux-dev")

    @patch.dict(os.environ, {}, clear=True)
    def test_raises_error_when_openai_key_missing(self, tmp_path):
        from musicvid.pipeline.image_generator import generate_images

        scene_plan = {"scenes": [{"visual_prompt": "test", "start": 0.0, "end": 5.0}]}

        with pytest.raises(EnvironmentError, match="OPENAI_API_KEY"):
            generate_images(scene_plan, str(tmp_path), provider="dalle")

    def test_raises_error_for_unknown_provider(self, tmp_path):
        from musicvid.pipeline.image_generator import generate_images

        scene_plan = {"scenes": [{"visual_prompt": "test", "start": 0.0, "end": 5.0}]}

        with pytest.raises(ValueError, match="Unknown provider"):
            generate_images(scene_plan, str(tmp_path), provider="midjourney")

    @patch.dict(os.environ, {"FAL_KEY": "test-key"})
    @patch("musicvid.pipeline.image_generator.requests")
    @patch("musicvid.pipeline.image_generator.fal_client")
    def test_default_provider_is_flux_dev(self, mock_fal, mock_requests, tmp_path):
        from musicvid.pipeline.image_generator import generate_images

        scene_plan = {"scenes": [{"visual_prompt": "test", "start": 0.0, "end": 5.0}]}
        mock_fal.run.return_value = {"images": [{"url": "https://example.com/image.jpg"}]}
        mock_http = MagicMock()
        mock_http.content = b"fake jpeg"
        mock_requests.get.return_value = mock_http

        generate_images(scene_plan, str(tmp_path))

        assert mock_fal.run.call_args[0][0] == "fal-ai/flux/dev"


class TestBannedWords:
    """Tests that banned words never appear in prompts."""

    @patch.dict(os.environ, {"FAL_KEY": "test-key"})
    @patch("musicvid.pipeline.image_generator.requests")
    @patch("musicvid.pipeline.image_generator.fal_client")
    def test_flux_prompt_has_no_banned_words(self, mock_fal, mock_requests, tmp_path):
        from musicvid.pipeline.image_generator import generate_images

        scene_plan = {
            "scenes": [
                {"visual_prompt": "golden wheat fields, warm light, peaceful", "start": 0.0, "end": 5.0},
                {"visual_prompt": "mountain peaks, morning mist, majestic", "start": 5.0, "end": 10.0},
            ]
        }

        mock_fal.run.return_value = {"images": [{"url": "https://example.com/image.jpg"}]}
        mock_http = MagicMock()
        mock_http.content = b"fake jpeg"
        mock_requests.get.return_value = mock_http

        generate_images(scene_plan, str(tmp_path), provider="flux-dev")

        for call in mock_fal.run.call_args_list:
            prompt = call[1]["arguments"]["prompt"].lower()
            for word in BANNED_WORDS:
                assert word not in prompt, f"Banned word '{word}' found in prompt: {prompt}"
```

- [ ] **Step 2: Run tests to verify they fail (no implementation yet would cause import error, but since we wrote implementation in Task 3, run to verify they pass)**

Run: `python3 -m pytest tests/test_image_generator.py -v`
Expected: All 15 tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_image_generator.py
git commit -m "test: rewrite image_generator tests for multi-provider support"
```

---

### Task 5: Add --provider CLI flag to musicvid.py

**Files:**
- Modify: `musicvid/musicvid.py`

- [ ] **Step 1: Add --provider option to CLI**

In `musicvid/musicvid.py`, add the `--provider` option after the `--mode` option (line 32):

```python
@click.option("--provider", type=click.Choice(["dalle", "flux-dev", "flux-pro", "schnell"]), default="flux-dev", help="Image provider for --mode ai.")
```

Add `provider` parameter to the `cli` function signature:

```python
def cli(audio_file, mode, style, output, resolution, lang, new, provider):
```

- [ ] **Step 2: Pass provider to generate_images and update log message**

In the Stage 3 `if mode == "ai":` block, change the echo line and the `generate_images` call:

Replace:
```python
            click.echo("[3/4] Generating AI images...")
            image_paths = generate_images(scene_plan, str(cache_dir))
```

With:
```python
            click.echo(f"[3/4] Generating images (provider: {provider})...")
            image_paths = generate_images(scene_plan, str(cache_dir), provider=provider)
```

- [ ] **Step 3: Run full test suite**

Run: `python3 -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add musicvid/musicvid.py
git commit -m "feat: add --provider CLI flag for image generation provider selection"
```

---

### Task 6: Run full test suite and verify acceptance criteria

- [ ] **Step 1: Run all tests**

Run: `python3 -m pytest tests/ -v`
Expected: All tests PASS (should be ~55 tests total now)

- [ ] **Step 2: Verify acceptance criteria manually**

Check each criterion:
1. `--provider flux-dev` generates via fal.ai Flux Dev — verified by test_flux_dev_uses_correct_model_id
2. `--provider flux-pro` generates via Flux Pro — verified by test_flux_pro_uses_correct_model_id
3. `--provider schnell` generates via Flux Schnell — verified by test_schnell_uses_correct_model_and_steps
4. `--provider dalle` generates via DALL-E 3 — verified by test_dalle_returns_correct_paths
5. Default is flux-dev — verified by test_default_provider_is_flux_dev
6. No banned words in prompts — verified by test_flux_prompt_has_no_banned_words
7. negative_prompt is separate parameter — verified by test_negative_prompt_is_separate_parameter
8. Clear error when FAL_KEY missing — verified by test_raises_error_when_fal_key_missing
9. All tests pass — verified by full test run

- [ ] **Step 3: Commit all remaining changes**

```bash
git add -A
git commit -m "feat: complete multi-provider image generation with flux and positive prompt strategy"
```
