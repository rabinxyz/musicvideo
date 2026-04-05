# Stock Content Filtering — Protestant Christian Only

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Filter Pexels/Unsplash stock queries to prevent non-Protestant-Christian content from appearing in generated music videos.

**Architecture:** Add a `sanitize_query()` function to `visual_router.py` that checks search queries against blocked words and safe replacements before any stock API call. Update `director_system.txt` to instruct the Claude director to avoid risky queries. Add dedicated test file `tests/test_stock_filtering.py`.

**Tech Stack:** Python 3.11+, pytest, unittest.mock

---

### Task 1: Add `sanitize_query` function and constants to `visual_router.py`

**Files:**
- Modify: `musicvid/pipeline/visual_router.py:1-10` (add constants and function after imports)
- Test: `tests/test_stock_filtering.py` (create)

- [ ] **Step 1: Write failing tests for `sanitize_query`**

Create `tests/test_stock_filtering.py`:

```python
"""Tests for stock content filtering (sanitize_query)."""

import pytest
from musicvid.pipeline.visual_router import sanitize_query


class TestSanitizeQueryBlocked:
    """Blocked words return 'BLOCKED'."""

    def test_muslim_blocked(self):
        assert sanitize_query("muslim prayer hands") == "BLOCKED"

    def test_mosque_blocked(self):
        assert sanitize_query("mosque sunset") == "BLOCKED"

    def test_islamic_blocked(self):
        assert sanitize_query("islamic architecture") == "BLOCKED"

    def test_quran_blocked(self):
        assert sanitize_query("quran reading") == "BLOCKED"

    def test_hindu_blocked(self):
        assert sanitize_query("hindu temple") == "BLOCKED"

    def test_buddha_blocked(self):
        assert sanitize_query("buddha statue garden") == "BLOCKED"

    def test_buddhist_blocked(self):
        assert sanitize_query("buddhist monastery") == "BLOCKED"

    def test_catholic_blocked(self):
        assert sanitize_query("catholic church interior") == "BLOCKED"

    def test_cathedral_blocked(self):
        assert sanitize_query("cathedral stained glass") == "BLOCKED"

    def test_shrine_blocked(self):
        assert sanitize_query("shrine offering") == "BLOCKED"

    def test_temple_blocked(self):
        assert sanitize_query("temple entrance") == "BLOCKED"

    def test_prayer_rug_blocked(self):
        assert sanitize_query("prayer rug room") == "BLOCKED"

    def test_hijab_blocked(self):
        assert sanitize_query("hijab woman praying") == "BLOCKED"

    def test_church_interior_blocked(self):
        assert sanitize_query("church interior pews") == "BLOCKED"

    def test_altar_blocked(self):
        assert sanitize_query("altar candles") == "BLOCKED"

    def test_rosary_blocked(self):
        assert sanitize_query("rosary beads hands") == "BLOCKED"

    def test_statue_blocked(self):
        assert sanitize_query("religious statue garden") == "BLOCKED"

    def test_case_insensitive(self):
        assert sanitize_query("MUSLIM prayer") == "BLOCKED"
        assert sanitize_query("Hindu Temple") == "BLOCKED"


class TestSanitizeQuerySafeReplacement:
    """Unsafe queries get replaced with safe alternatives."""

    def test_prayer_hands_replaced(self):
        result = sanitize_query("prayer hands")
        assert result == "person sitting quietly nature"
        assert "prayer" not in result

    def test_hands_praying_replaced(self):
        result = sanitize_query("hands praying")
        assert result == "person peaceful outdoor sunrise"

    def test_worship_replaced(self):
        result = sanitize_query("worship")
        assert result == "outdoor gathering people singing sunset"

    def test_meditation_replaced(self):
        result = sanitize_query("meditation person")
        assert result == "person sitting peaceful nature"

    def test_spiritual_replaced(self):
        result = sanitize_query("spiritual journey")
        assert result == "peaceful nature landscape morning"


class TestSanitizeQuerySafePassthrough:
    """Safe queries pass through unchanged."""

    def test_mountain_sunrise(self):
        assert sanitize_query("mountain sunrise") == "mountain sunrise"

    def test_ocean_waves(self):
        assert sanitize_query("ocean waves horizon") == "ocean waves horizon"

    def test_person_walking(self):
        assert sanitize_query("person walking mountain") == "person walking mountain"

    def test_golden_wheat_field(self):
        assert sanitize_query("golden wheat field") == "golden wheat field"

    def test_empty_query(self):
        assert sanitize_query("") == ""

    def test_nature_landscape(self):
        assert sanitize_query("nature landscape") == "nature landscape"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_stock_filtering.py -v`
Expected: FAIL with `ImportError: cannot import name 'sanitize_query'`

- [ ] **Step 3: Implement `sanitize_query` with constants in `visual_router.py`**

Add after the imports (line 9) in `musicvid/pipeline/visual_router.py`:

```python
BLOCKED_WORDS = [
    "muslim", "mosque", "islamic", "quran", "hindu",
    "buddha", "buddhist", "catholic", "cathedral",
    "shrine", "temple", "prayer rug", "hijab",
    "church interior", "altar", "rosary", "statue",
]

SAFE_QUERY_MAP = {
    "prayer hands": "person sitting quietly nature",
    "hands praying": "person peaceful outdoor sunrise",
    "praying hands": "person sitting peaceful morning",
    "worship": "outdoor gathering people singing sunset",
    "worship hands raised": "people outdoor arms up sunset",
    "prayer outdoor": "person sitting field morning light",
    "spiritual": "peaceful nature landscape morning",
    "meditation": "person sitting peaceful nature",
}


def sanitize_query(query):
    """Check query against blocked words and safe replacements.

    Returns 'BLOCKED' for religious non-Protestant content,
    a safe replacement for risky queries, or the original query if safe.
    """
    if not query:
        return query
    query_lower = query.lower()
    for blocked in BLOCKED_WORDS:
        if blocked in query_lower:
            return "BLOCKED"
    for unsafe, safe in SAFE_QUERY_MAP.items():
        if unsafe in query_lower:
            return safe
    return query
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_stock_filtering.py -v`
Expected: All 24 tests PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_stock_filtering.py musicvid/pipeline/visual_router.py
git commit -m "feat: add sanitize_query for stock content filtering"
```

---

### Task 2: Integrate `sanitize_query` into VisualRouter dispatch methods

**Files:**
- Modify: `musicvid/pipeline/visual_router.py:50-106` (`_route_video_stock` and `_route_photo_stock`)
- Test: `tests/test_stock_filtering.py` (append integration tests)

- [ ] **Step 1: Write failing integration tests**

Append to `tests/test_stock_filtering.py`:

```python
import os
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestVideoStockSanitization:
    """sanitize_query blocks risky queries before Pexels API call."""

    def test_blocked_query_falls_back_to_bfl(self, tmp_path):
        from musicvid.pipeline.visual_router import VisualRouter
        router = VisualRouter(cache_dir=str(tmp_path), provider="flux-pro")

        scene = {
            "index": 0,
            "section": "verse",
            "start": 0.0,
            "end": 12.0,
            "visual_source": "TYPE_VIDEO_STOCK",
            "search_query": "muslim prayer hands",
            "visual_prompt": "person praying at sunrise",
            "motion_prompt": "",
            "animate": False,
        }
        ai_path = str(tmp_path / "scene_000.jpg")

        with patch("musicvid.pipeline.visual_router.fetch_video_by_query") as mock_fetch, \
             patch("musicvid.pipeline.visual_router.generate_single_image",
                   return_value=ai_path) as mock_gen:
            result = router.route(scene)

        mock_fetch.assert_not_called()
        mock_gen.assert_called_once_with("person praying at sunrise", ai_path, "flux-pro")
        assert result == ai_path

    def test_safe_replacement_used_for_pexels(self, tmp_path):
        from musicvid.pipeline.visual_router import VisualRouter
        router = VisualRouter(cache_dir=str(tmp_path), provider="flux-pro")

        scene = {
            "index": 0,
            "section": "verse",
            "start": 0.0,
            "end": 12.0,
            "visual_source": "TYPE_VIDEO_STOCK",
            "search_query": "worship hands raised",
            "visual_prompt": "",
            "motion_prompt": "",
            "animate": False,
        }
        video_path = str(tmp_path / "scene_000.mp4")

        with patch("musicvid.pipeline.visual_router.fetch_video_by_query",
                   return_value=video_path) as mock_fetch:
            result = router.route(scene)

        mock_fetch.assert_called_once_with(
            "people outdoor arms up sunset",
            12.0,
            video_path,
        )
        assert result == video_path

    def test_safe_query_passes_through(self, tmp_path):
        from musicvid.pipeline.visual_router import VisualRouter
        router = VisualRouter(cache_dir=str(tmp_path), provider="flux-pro")

        scene = {
            "index": 0,
            "section": "verse",
            "start": 0.0,
            "end": 12.0,
            "visual_source": "TYPE_VIDEO_STOCK",
            "search_query": "mountain sunrise valley",
            "visual_prompt": "",
            "motion_prompt": "",
            "animate": False,
        }
        video_path = str(tmp_path / "scene_000.mp4")

        with patch("musicvid.pipeline.visual_router.fetch_video_by_query",
                   return_value=video_path) as mock_fetch:
            result = router.route(scene)

        mock_fetch.assert_called_once_with(
            "mountain sunrise valley",
            12.0,
            video_path,
        )


class TestPhotoStockSanitization:
    """sanitize_query blocks risky queries before Unsplash/Pexels photo API call."""

    @patch.dict(os.environ, {"UNSPLASH_ACCESS_KEY": "fake-key"})
    def test_blocked_query_falls_back_to_bfl(self, tmp_path):
        from musicvid.pipeline.visual_router import VisualRouter
        router = VisualRouter(cache_dir=str(tmp_path), provider="flux-pro")

        scene = {
            "index": 1,
            "section": "verse",
            "start": 12.0,
            "end": 24.0,
            "visual_source": "TYPE_PHOTO_STOCK",
            "search_query": "cathedral stained glass",
            "visual_prompt": "light streaming through window",
            "motion_prompt": "",
            "animate": False,
        }
        ai_path = str(tmp_path / "scene_001.jpg")

        with patch("musicvid.pipeline.visual_router.requests.get") as mock_get, \
             patch("musicvid.pipeline.visual_router.generate_single_image",
                   return_value=ai_path) as mock_gen:
            result = router.route(scene)

        mock_get.assert_not_called()
        mock_gen.assert_called_once_with("light streaming through window", ai_path, "flux-pro")
        assert result == ai_path

    @patch.dict(os.environ, {"UNSPLASH_ACCESS_KEY": "fake-key"})
    def test_safe_replacement_used_for_unsplash(self, tmp_path):
        from musicvid.pipeline.visual_router import VisualRouter
        router = VisualRouter(cache_dir=str(tmp_path), provider="flux-pro")

        scene = {
            "index": 1,
            "section": "verse",
            "start": 12.0,
            "end": 24.0,
            "visual_source": "TYPE_PHOTO_STOCK",
            "search_query": "meditation person peaceful",
            "visual_prompt": "",
            "motion_prompt": "",
            "animate": False,
        }
        output_path = str(tmp_path / "scene_001.jpg")

        def fake_get(url, **kwargs):
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            if "api.unsplash" in url:
                # Verify the sanitized query was used
                assert kwargs["params"]["query"] == "person sitting peaceful nature"
                resp.json.return_value = {
                    "urls": {"regular": "https://img.unsplash.com/photo.jpg"}
                }
            else:
                resp.content = b"photo-data"
            return resp

        with patch("musicvid.pipeline.visual_router.requests.get", side_effect=fake_get):
            result = router.route(scene)

        assert result == output_path
```

- [ ] **Step 2: Run tests to verify the integration tests fail**

Run: `python3 -m pytest tests/test_stock_filtering.py::TestVideoStockSanitization -v`
Expected: FAIL (sanitize_query not yet integrated into route methods)

- [ ] **Step 3: Integrate `sanitize_query` into `_route_video_stock`**

Replace the `_route_video_stock` method in `musicvid/pipeline/visual_router.py`:

```python
def _route_video_stock(self, scene, idx, duration):
    query = scene.get("search_query", "nature landscape")
    output_path = str(self.cache_dir / f"scene_{idx:03d}.mp4")

    sanitized = sanitize_query(query)
    if sanitized == "BLOCKED":
        print(f"  WARN: query '{query}' blocked — fallback TYPE_AI for scene {idx}")
        fallback_prompt = scene.get("visual_prompt") or "peaceful nature landscape"
        return self._generate_bfl(fallback_prompt, idx)
    query = sanitized

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

- [ ] **Step 4: Integrate `sanitize_query` into `_route_photo_stock`**

Replace the `_route_photo_stock` method in `musicvid/pipeline/visual_router.py`:

```python
def _route_photo_stock(self, scene, idx):
    output_path = str(self.cache_dir / f"scene_{idx:03d}.jpg")
    if Path(output_path).exists():
        return output_path

    query = scene.get("search_query", "nature landscape")
    sanitized = sanitize_query(query)
    if sanitized == "BLOCKED":
        print(f"  WARN: query '{query}' blocked — fallback TYPE_AI for scene {idx}")
        fallback_prompt = scene.get("visual_prompt") or "peaceful nature landscape"
        return self._generate_bfl(fallback_prompt, idx)
    query = sanitized

    unsplash_key = os.environ.get("UNSPLASH_ACCESS_KEY", "")
    if unsplash_key:
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
        video_path = str(self.cache_dir / f"scene_{idx:03d}.mp4")
        result = fetch_video_by_query(query, duration, video_path)
        if result:
            return result
        print(f"  Fallback: scene {idx} Pexels failed, falling back to TYPE_AI")

    print(f"  WARN: Brak kluczy stock — fallback TYPE_AI dla sceny {idx}")
    return self._generate_bfl(scene.get("visual_prompt", "nature landscape"), idx)
```

- [ ] **Step 5: Run all tests to verify they pass**

Run: `python3 -m pytest tests/test_stock_filtering.py tests/test_visual_router.py -v`
Expected: All tests PASS (both new filtering tests and existing router tests)

- [ ] **Step 6: Commit**

```bash
git add musicvid/pipeline/visual_router.py tests/test_stock_filtering.py
git commit -m "feat: integrate sanitize_query into VisualRouter stock dispatch"
```

---

### Task 3: Update `director_system.txt` with stock filtering rules

**Files:**
- Modify: `musicvid/prompts/director_system.txt:12-17` (TYPE_VIDEO_STOCK section)
- Test: `tests/test_stock_filtering.py` (append director prompt test)

- [ ] **Step 1: Write test that director prompt contains the filtering rules**

Append to `tests/test_stock_filtering.py`:

```python
class TestDirectorPromptFiltering:
    """Director system prompt contains stock filtering rules."""

    def test_director_prompt_bans_religious_keywords_in_search_query(self):
        prompt_path = Path(__file__).parent.parent / "musicvid" / "prompts" / "director_system.txt"
        prompt_text = prompt_path.read_text()

        # Must ban these words in search_query context
        for word in ["muslim", "mosque", "islamic", "hindu", "buddha",
                     "church interior", "cathedral", "shrine", "altar",
                     "rosary", "meditation", "prayer rug", "hijab"]:
            assert word in prompt_text.lower(), f"Missing banned word in director prompt: {word}"

    def test_director_prompt_has_safe_query_guidance(self):
        prompt_path = Path(__file__).parent.parent / "musicvid" / "prompts" / "director_system.txt"
        prompt_text = prompt_path.read_text().lower()

        # Must contain guidance for safe query alternatives
        assert "person sitting" in prompt_text or "person walking" in prompt_text
        assert "nature" in prompt_text

    def test_director_prompt_restricts_video_stock_to_nature(self):
        prompt_path = Path(__file__).parent.parent / "musicvid" / "prompts" / "director_system.txt"
        prompt_text = prompt_path.read_text()

        # TYPE_VIDEO_STOCK should mention nature/landscape restriction
        assert "TYPE_VIDEO_STOCK" in prompt_text
        # The prompt must warn against using TYPE_VIDEO_STOCK for religious content
        assert "prayer" in prompt_text.lower() or "worship" in prompt_text.lower()
```

- [ ] **Step 2: Run tests to verify some fail**

Run: `python3 -m pytest tests/test_stock_filtering.py::TestDirectorPromptFiltering -v`
Expected: `test_director_prompt_bans_religious_keywords_in_search_query` may partially fail (some words already banned in visual_prompt, but not all are listed for search_query context)

- [ ] **Step 3: Update `director_system.txt` TYPE_VIDEO_STOCK section**

Add after the TYPE_VIDEO_STOCK description (after line 17 in `director_system.txt`), before TYPE_PHOTO_STOCK:

```
  CRITICAL search_query rules:
  NEVER use these words in search_query: muslim, mosque, islamic, quran, hindu, buddha,
  buddhist, church interior, cathedral, shrine, altar, rosary, meditation,
  prayer rug, hijab, pope, bishop, temple
  For prayer/worship scenes: describe ACTION and PLACE without religious context:
    NO: "prayer hands", "worship hands", "meditation person"
    YES: "person sitting quietly sunrise", "hands open palms upward outdoor",
         "people outdoor arms up sunset", "person peaceful field morning"
  TYPE_VIDEO_STOCK is SAFEST for nature and landscapes only.
  For people in prayer/worship — prefer TYPE_AI to avoid non-Protestant content.
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_stock_filtering.py::TestDirectorPromptFiltering -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add musicvid/prompts/director_system.txt tests/test_stock_filtering.py
git commit -m "feat: add stock query filtering rules to director prompt"
```

---

### Task 4: Run full test suite and verify no regressions

**Files:**
- No new files

- [ ] **Step 1: Run the full test suite**

Run: `python3 -m pytest tests/ -v`
Expected: All tests pass (existing + new filtering tests)

- [ ] **Step 2: Fix any failures if needed**

If any existing test fails due to the sanitize_query integration, check if the existing test's `search_query` fixture data triggers sanitization. The existing fixtures (`SCENE_VIDEO_STOCK` with "mountain valley peaceful morning", `SCENE_PHOTO_STOCK` with "open bible morning light wooden table") should pass through unchanged.

- [ ] **Step 3: Final commit if any fixes were needed**

```bash
git add -A
git commit -m "fix: resolve any test regressions from stock filtering"
```
