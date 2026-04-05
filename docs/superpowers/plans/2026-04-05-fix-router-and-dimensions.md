# Fix Router and BFL Dimensions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix BFL image dimensions (1024×768), add Pexels fallback in TYPE_PHOTO_STOCK, implement proper fallback hierarchy for all visual source types, and improve per-scene logging.

**Architecture:** Changes are isolated to `image_generator.py` (dimension fix), `visual_router.py` (fallback hierarchy + logging), and `musicvid.py` (log format). No new files needed.

**Tech Stack:** Python 3.11+, unittest.mock, pytest

---

## File Map

| File | Change |
|------|--------|
| `musicvid/pipeline/image_generator.py` | `generate_single_image` uses 1024×768 instead of 1360×768 |
| `musicvid/pipeline/visual_router.py` | `_route_photo_stock` adds Pexels fallback; `_route_video_stock` final fallback goes direct to BFL |
| `musicvid/musicvid.py` | Scene logging format updated to use `\|` separators and `query:`/`prompt:` prefixes |
| `tests/test_image_generator.py` | Add dimension assertion for `generate_single_image` |
| `tests/test_visual_router.py` | Update fallback test names + add Pexels fallback test |

---

### Task 1: Fix BFL dimensions in `generate_single_image`

**Files:**
- Modify: `musicvid/pipeline/image_generator.py:166`
- Test: `tests/test_image_generator.py`

- [ ] **Step 1: Write the failing test**

Add to `class TestGenerateSingleImage` in `tests/test_image_generator.py`:

```python
@patch.dict(os.environ, {"BFL_API_KEY": "test-key"})
@patch("musicvid.pipeline.image_generator.requests")
def test_single_image_uses_1024x768(self, mock_requests, tmp_path):
    mock_requests.post.return_value = _make_post_response()
    mock_requests.get.side_effect = [_make_poll_response(), _make_download_response()]

    from musicvid.pipeline.image_generator import generate_single_image
    output = str(tmp_path / "scene_001.jpg")
    generate_single_image("mountain sunrise", output, provider="flux-pro")

    payload = mock_requests.post.call_args[1]["json"]
    assert payload["width"] == 1024
    assert payload["height"] == 768
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m pytest tests/test_image_generator.py::TestGenerateSingleImage::test_single_image_uses_1024x768 -v
```
Expected: FAIL — `assert 1360 == 1024`

- [ ] **Step 3: Implement the fix**

In `musicvid/pipeline/image_generator.py` line 166, change:
```python
    task_id, polling_url = _submit_task(model_name, full_prompt)
```
to:
```python
    task_id, polling_url = _submit_task(model_name, full_prompt, width=1024, height=768)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python3 -m pytest tests/test_image_generator.py::TestGenerateSingleImage::test_single_image_uses_1024x768 -v
```
Expected: PASS

- [ ] **Step 5: Run full image_generator tests to check no regressions**

```bash
python3 -m pytest tests/test_image_generator.py -v
```
Expected: all pass (the `test_landscape_dimensions_are_1360x768` test is for `generate_images`, not `generate_single_image`, so it still passes)

- [ ] **Step 6: Commit**

```bash
git add musicvid/pipeline/image_generator.py tests/test_image_generator.py
git commit -m "fix(image_generator): use 1024x768 for generate_single_image (avoids BFL 422)"
```

---

### Task 2: Add Pexels fallback in `_route_photo_stock`

**Files:**
- Modify: `musicvid/pipeline/visual_router.py:68-94`
- Test: `tests/test_visual_router.py`

The new fallback hierarchy for TYPE_PHOTO_STOCK:
1. Cached file on disk
2. Unsplash (if UNSPLASH_ACCESS_KEY set)
3. Pexels video (if PEXELS_API_KEY set)
4. BFL Flux (last resort)

- [ ] **Step 1: Write the failing test**

Add to `class TestVisualRouterPhotoStock` in `tests/test_visual_router.py`:

```python
def test_route_photo_stock_no_unsplash_pexels_fallback(self, tmp_path):
    from musicvid.pipeline.visual_router import VisualRouter
    router = VisualRouter(cache_dir=str(tmp_path), provider="flux-pro")

    pexels_path = str(tmp_path / "scene_001.mp4")

    with patch.dict(os.environ, {"PEXELS_API_KEY": "pexels-key"}, clear=True), \
         patch("musicvid.pipeline.visual_router.fetch_video_by_query",
               return_value=pexels_path) as mock_fetch, \
         patch("musicvid.pipeline.visual_router.generate_single_image") as mock_gen:
        result = router.route(SCENE_PHOTO_STOCK)

    mock_fetch.assert_called_once_with(
        SCENE_PHOTO_STOCK["search_query"],
        SCENE_PHOTO_STOCK["end"] - SCENE_PHOTO_STOCK["start"],
        str(tmp_path / "scene_001.mp4"),
    )
    mock_gen.assert_not_called()
    assert result == pexels_path
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m pytest tests/test_visual_router.py::TestVisualRouterPhotoStock::test_route_photo_stock_no_unsplash_pexels_fallback -v
```
Expected: FAIL — `generate_single_image` is called instead of `fetch_video_by_query`

- [ ] **Step 3: Implement the fix**

Replace `_route_photo_stock` in `musicvid/pipeline/visual_router.py`:

```python
def _route_photo_stock(self, scene, idx):
    output_path = str(self.cache_dir / f"scene_{idx:03d}.jpg")
    if Path(output_path).exists():
        return output_path

    unsplash_key = os.environ.get("UNSPLASH_ACCESS_KEY", "")
    if unsplash_key:
        query = scene.get("search_query", "nature landscape")
        try:
            resp = requests.get(
                "https://api.unsplash.com/photos/random",
                headers={"Authorization": f"Client-ID {unsplash_key}"},
                params={"query": query, "orientation": "landscape", "content_filter": "high"},
                timeout=10,
            )
            resp.raise_for_status()
            image_url = resp.json()["urls"]["regular"]
            img_resp = requests.get(image_url, timeout=30)
            img_resp.raise_for_status()
            Path(output_path).write_bytes(img_resp.content)
            return output_path
        except Exception as exc:
            print(f"  Fallback: scene {idx} Unsplash failed ({exc}), trying Pexels")

    pexels_key = os.environ.get("PEXELS_API_KEY", "")
    if pexels_key:
        duration = scene["end"] - scene["start"]
        query = scene.get("search_query", "nature landscape")
        video_path = str(self.cache_dir / f"scene_{idx:03d}.mp4")
        result = fetch_video_by_query(query, duration, video_path)
        if result:
            return result
        print(f"  Fallback: scene {idx} Pexels failed, falling back to TYPE_AI")

    print(f"  WARN: Brak kluczy stock — fallback TYPE_AI dla sceny {idx}")
    return self._generate_bfl(scene.get("visual_prompt", "nature landscape"), idx)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python3 -m pytest tests/test_visual_router.py::TestVisualRouterPhotoStock::test_route_photo_stock_no_unsplash_pexels_fallback -v
```
Expected: PASS

- [ ] **Step 5: Run full photo stock tests**

```bash
python3 -m pytest tests/test_visual_router.py::TestVisualRouterPhotoStock -v
```
Expected: all pass (existing tests still work — `test_route_photo_stock_no_key_falls_back_to_type_ai` still works because when no PEXELS_API_KEY either, BFL is called)

- [ ] **Step 6: Commit**

```bash
git add musicvid/pipeline/visual_router.py tests/test_visual_router.py
git commit -m "fix(visual_router): TYPE_PHOTO_STOCK fallback via Pexels before BFL"
```

---

### Task 3: Fix TYPE_VIDEO_STOCK final fallback (direct to BFL)

**Files:**
- Modify: `musicvid/pipeline/visual_router.py:50-66`
- Test: `tests/test_visual_router.py`

Current behavior: `TYPE_VIDEO_STOCK` → simplified query → `_route_photo_stock` → BFL
Spec behavior: `TYPE_VIDEO_STOCK` → simplified query → BFL with `visual_prompt` → BFL with "nature landscape peaceful"

- [ ] **Step 1: Write the failing test**

Add to `class TestVisualRouterVideoStock` in `tests/test_visual_router.py`:

```python
def test_route_video_stock_fallback_uses_visual_prompt_for_bfl(self, tmp_path):
    from musicvid.pipeline.visual_router import VisualRouter
    router = VisualRouter(cache_dir=str(tmp_path), provider="flux-pro")

    scene = {
        "index": 0,
        "section": "verse",
        "start": 0.0,
        "end": 12.0,
        "visual_source": "TYPE_VIDEO_STOCK",
        "search_query": "mountain valley peaceful morning",
        "visual_prompt": "sunrise over misty mountain valley, wide angle",
        "motion_prompt": "",
        "animate": False,
    }
    ai_path = str(tmp_path / "scene_000.jpg")

    with patch("musicvid.pipeline.visual_router.fetch_video_by_query", return_value=None), \
         patch("musicvid.pipeline.visual_router.generate_single_image",
               return_value=ai_path) as mock_gen:
        result = router.route(scene)

    mock_gen.assert_called_once_with(
        "sunrise over misty mountain valley, wide angle",
        ai_path,
        "flux-pro",
    )
    assert result == ai_path

def test_route_video_stock_fallback_uses_default_when_no_visual_prompt(self, tmp_path):
    from musicvid.pipeline.visual_router import VisualRouter
    router = VisualRouter(cache_dir=str(tmp_path), provider="flux-pro")

    ai_path = str(tmp_path / "scene_000.jpg")

    with patch("musicvid.pipeline.visual_router.fetch_video_by_query", return_value=None), \
         patch("musicvid.pipeline.visual_router.generate_single_image",
               return_value=ai_path) as mock_gen:
        result = router.route(SCENE_VIDEO_STOCK)  # SCENE_VIDEO_STOCK has visual_prompt=""

    mock_gen.assert_called_once_with(
        "nature landscape peaceful",
        ai_path,
        "flux-pro",
    )
    assert result == ai_path
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_visual_router.py::TestVisualRouterVideoStock::test_route_video_stock_fallback_uses_visual_prompt_for_bfl tests/test_visual_router.py::TestVisualRouterVideoStock::test_route_video_stock_fallback_uses_default_when_no_visual_prompt -v
```
Expected: FAIL

- [ ] **Step 3: Implement the fix**

Replace `_route_video_stock` in `musicvid/pipeline/visual_router.py`:

```python
def _route_video_stock(self, scene, idx, duration):
    query = scene.get("search_query", "nature landscape")
    output_path = str(self.cache_dir / f"scene_{idx:03d}.mp4")

    result = fetch_video_by_query(query, duration, output_path)
    if result:
        return result

    # Simplified query fallback (first 2 words)
    simplified = " ".join(query.split()[:2])
    if simplified and simplified != query:
        result = fetch_video_by_query(simplified, duration, output_path)
        if result:
            return result

    # BFL fallback — use visual_prompt if available, else default
    visual_prompt = scene.get("visual_prompt") or ""
    fallback_prompt = visual_prompt if visual_prompt else "nature landscape peaceful"
    print(f"  Fallback: scene {idx} TYPE_VIDEO_STOCK → TYPE_AI (Pexels exhausted)")
    return self._generate_bfl(fallback_prompt, idx)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_visual_router.py::TestVisualRouterVideoStock -v
```
Expected: all pass (including the renamed existing test)

Note: `test_route_video_stock_falls_back_to_photo_then_ai` still passes because it patches `generate_single_image` to return a path and just checks it was called once. The test name is slightly misleading now (no longer goes through photo stock) — it can be left as-is since behavior is functionally the same from the test's perspective, or renamed.

- [ ] **Step 5: Commit**

```bash
git add musicvid/pipeline/visual_router.py tests/test_visual_router.py
git commit -m "fix(visual_router): TYPE_VIDEO_STOCK fallback direct to BFL with visual_prompt"
```

---

### Task 4: Fix scene logging format in musicvid.py

**Files:**
- Modify: `musicvid/musicvid.py:629-631`
- Test: `tests/test_cli.py` (check for any logging assertions; update format if found)

Current format: `  [1/10] verse: TYPE_VIDEO_STOCK — 'mountain sunrise'`
Spec format: `  [1/10] verse | TYPE_VIDEO_STOCK | query: mountain sunrise`

- [ ] **Step 1: Update the log line in musicvid.py**

Find and replace in `musicvid/musicvid.py` around line 626-632:

Old code:
```python
            for i, scene in enumerate(scene_plan["scenes"]):
                scene["index"] = i
                src = scene.get("visual_source", "TYPE_AI")
                label = scene.get("search_query") or scene.get("visual_prompt", "")
                click.echo(f"  [{i + 1}/{len(scene_plan['scenes'])}] "
                           f"{scene['section']}: {src} — '{label[:40]}'")
                asset_path = router.route(scene)
```

New code:
```python
            for i, scene in enumerate(scene_plan["scenes"]):
                scene["index"] = i
                src = scene.get("visual_source", "TYPE_AI")
                query = scene.get("search_query", "")
                prompt_preview = (scene.get("visual_prompt") or "")[:50]
                detail = f"query: {query}" if query else f"prompt: {prompt_preview}"
                total = len(scene_plan["scenes"])
                click.echo(f"  [{i + 1}/{total}] {scene['section']} | {src} | {detail}")
                asset_path = router.route(scene)
```

- [ ] **Step 2: Run tests to check for regressions**

```bash
python3 -m pytest tests/test_cli.py -v -k "mode_ai or visual_router or router" 2>&1 | tail -30
```
Expected: all pass (CLI tests typically mock router.route and don't assert on click.echo logging format)

- [ ] **Step 3: Run full test suite**

```bash
python3 -m pytest tests/ -v 2>&1 | tail -30
```
Expected: all pass

- [ ] **Step 4: Commit**

```bash
git add musicvid/musicvid.py
git commit -m "fix(cli): update scene log format to pipe-separated with query/prompt prefix"
```

---

## Acceptance Criteria Checklist

- [ ] `generate_single_image` submits width=1024, height=768 to BFL (no more 422 errors)
- [ ] `_route_photo_stock` without Unsplash key tries Pexels before BFL
- [ ] `_route_video_stock` final fallback uses `visual_prompt` or "nature landscape peaceful", not `_route_photo_stock`
- [ ] Scene logging shows `| query: X` or `| prompt: X` with pipe separators
- [ ] All 416+ tests pass
