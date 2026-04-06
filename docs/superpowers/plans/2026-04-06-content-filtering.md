# Content Filtering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand content filtering to block alcohol, drugs, gambling, and non-Protestant religious imagery at all four pipeline levels: query sanitization, BFL prompt suffixes, director system prompt, and related tests.

**Architecture:** Four-level defense — (1) `BLOCKED_WORDS` in `visual_router.py` blocks bad search queries before any stock API call; (2) `NEGATIVE_CONTEXT` in `image_generator.py` instructs BFL Flux to exclude inappropriate content; (3) `director_system.txt` bans inappropriate elements from the director's scene plan; (4) existing `test_stock_filtering.py` extended with new word coverage tests.

**Tech Stack:** Python 3.11+, unittest/pytest, existing `BLOCKED_WORDS`/`SAFE_QUERY_MAP` pattern in `visual_router.py`, `NEGATIVE_CONTEXT` constant in `image_generator.py`.

---

### Task 1: Expand BLOCKED_WORDS in visual_router.py

**Files:**
- Modify: `musicvid/pipeline/visual_router.py:11-16`
- Test: `tests/test_stock_filtering.py`

- [ ] **Step 1: Write failing tests for new blocked words**

Add these test cases to `tests/test_stock_filtering.py` — append to the file after the existing `TestSanitizeQueryBlocked` class:

```python
class TestSanitizeQueryBlockedAlcohol:
    """Alcohol-related words must return 'BLOCKED'."""

    @pytest.mark.parametrize("query", [
        "alcohol party",
        "beer glass table",
        "wine bottle sunset",
        "whiskey pour rocks",
        "vodka shot glass",
        "drinking friends bar",
        "bar interior night",
        "pub gathering people",
        "cocktail shaker hands",
        "champagne toast celebration",
        "nightclub crowd music",
        "drunk person street",
    ])
    def test_alcohol_query_blocked(self, query):
        assert sanitize_query(query) == "BLOCKED"


class TestSanitizeQueryBlockedDrugsGambling:
    """Drugs and gambling words must return 'BLOCKED'."""

    @pytest.mark.parametrize("query", [
        "gambling casino",
        "casino slot machine",
        "cigarette smoking man",
        "smoking outdoor people",
        "drugs dealer street",
        "violence street fight",
        "party wild nightlife",
        "nightlife city lights",
    ])
    def test_drugs_gambling_query_blocked(self, query):
        assert sanitize_query(query) == "BLOCKED"


class TestSanitizeQueryBlockedNewReligious:
    """Additional non-Protestant religious words must return 'BLOCKED'."""

    @pytest.mark.parametrize("query", [
        "pope blessing crowd",
        "nun walking convent",
        "monk meditation garden",
        "orthodox church exterior",
        "meditation room peaceful",
    ])
    def test_new_religious_query_blocked(self, query):
        assert sanitize_query(query) == "BLOCKED"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/s.rzytki/Documents/aiprojects/musicvideo
python3 -m pytest tests/test_stock_filtering.py::TestSanitizeQueryBlockedAlcohol tests/test_stock_filtering.py::TestSanitizeQueryBlockedDrugsGambling tests/test_stock_filtering.py::TestSanitizeQueryBlockedNewReligious -v 2>&1 | head -60
```

Expected: FAIL — `sanitize_query("alcohol party")` does not return "BLOCKED" yet.

- [ ] **Step 3: Expand BLOCKED_WORDS in visual_router.py**

Replace the `BLOCKED_WORDS` list in `musicvid/pipeline/visual_router.py` (lines 11–16):

```python
BLOCKED_WORDS = [
    # Non-Protestant religious imagery
    "muslim", "mosque", "islamic", "quran", "hindu",
    "buddha", "buddhist", "catholic", "cathedral",
    "shrine", "temple", "prayer rug", "hijab",
    "church interior", "altar", "rosary", "statue",
    "pope", "nun", "monk", "orthodox", "meditation",
    # Alcohol and intoxicants
    "alcohol", "beer", "wine", "whiskey", "vodka",
    "drinking", "bar", "pub", "cocktail", "champagne",
    "nightclub", "drunk",
    # Other inappropriate content
    "gambling", "casino", "cigarette", "smoking",
    "drugs", "violence", "nightlife",
]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/s.rzytki/Documents/aiprojects/musicvideo
python3 -m pytest tests/test_stock_filtering.py::TestSanitizeQueryBlockedAlcohol tests/test_stock_filtering.py::TestSanitizeQueryBlockedDrugsGambling tests/test_stock_filtering.py::TestSanitizeQueryBlockedNewReligious -v 2>&1 | tail -20
```

Expected: All PASS.

- [ ] **Step 5: Run full test suite to check no regressions**

```bash
cd /Users/s.rzytki/Documents/aiprojects/musicvideo
python3 -m pytest tests/test_stock_filtering.py -v 2>&1 | tail -30
```

Expected: All existing tests still PASS.

- [ ] **Step 6: Commit**

```bash
cd /Users/s.rzytki/Documents/aiprojects/musicvideo
git add musicvid/pipeline/visual_router.py tests/test_stock_filtering.py
git commit -m "feat: expand BLOCKED_WORDS with alcohol, drugs, gambling, and additional religious terms"
```

---

### Task 2: Expand NEGATIVE_CONTEXT in image_generator.py

**Files:**
- Modify: `musicvid/pipeline/image_generator.py:27-31`
- Test: `tests/test_image_generator.py`

- [ ] **Step 1: Write failing test for new negative context terms**

Open `tests/test_image_generator.py` and find the existing banned-words test class. Add a new test to verify the extended NEGATIVE_CONTEXT. First read the existing test to understand the pattern:

```bash
cd /Users/s.rzytki/Documents/aiprojects/musicvideo
grep -n "NEGATIVE_CONTEXT\|negative_context\|no alcohol\|no Catholic" tests/test_image_generator.py | head -20
```

Then add this test to `tests/test_image_generator.py` in the appropriate test class (find the class that tests `NEGATIVE_CONTEXT` content, or add a new class if none exists):

```python
class TestNegativeContextContent:
    """NEGATIVE_CONTEXT constant must contain alcohol and inappropriate content exclusions."""

    def test_negative_context_excludes_alcohol(self):
        from musicvid.pipeline.image_generator import NEGATIVE_CONTEXT
        assert "no alcohol" in NEGATIVE_CONTEXT.lower()

    def test_negative_context_excludes_islamic(self):
        from musicvid.pipeline.image_generator import NEGATIVE_CONTEXT
        assert "no islamic" in NEGATIVE_CONTEXT.lower() or "islamic" in NEGATIVE_CONTEXT.lower()

    def test_negative_context_excludes_buddhist(self):
        from musicvid.pipeline.image_generator import NEGATIVE_CONTEXT
        assert "no buddhist" in NEGATIVE_CONTEXT.lower() or "buddhist" in NEGATIVE_CONTEXT.lower()

    def test_negative_context_excludes_hindu(self):
        from musicvid.pipeline.image_generator import NEGATIVE_CONTEXT
        assert "no hindu" in NEGATIVE_CONTEXT.lower() or "hindu" in NEGATIVE_CONTEXT.lower()

    def test_negative_context_excludes_gambling(self):
        from musicvid.pipeline.image_generator import NEGATIVE_CONTEXT
        assert "no gambling" in NEGATIVE_CONTEXT.lower()

    def test_negative_context_excludes_cigarettes(self):
        from musicvid.pipeline.image_generator import NEGATIVE_CONTEXT
        assert "no cigarette" in NEGATIVE_CONTEXT.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/s.rzytki/Documents/aiprojects/musicvideo
python3 -m pytest tests/test_image_generator.py::TestNegativeContextContent -v 2>&1 | tail -20
```

Expected: FAIL — "no alcohol" not in NEGATIVE_CONTEXT yet.

- [ ] **Step 3: Update NEGATIVE_CONTEXT in image_generator.py**

Replace the `NEGATIVE_CONTEXT` constant in `musicvid/pipeline/image_generator.py` (lines 27–31):

```python
NEGATIVE_CONTEXT = (
    "no Catholic imagery, no religious figures, no rosary, no crucifix, "
    "no saints, no Islamic imagery, no Buddhist imagery, no Hindu imagery, "
    "Protestant Christian context only, "
    "no alcohol, no drinking, no beer, no wine, no cigarettes, no smoking, "
    "no gambling, no casino, no drugs, no violence, "
    "family friendly, no inappropriate content, "
    "natural light not artificial, authentic not staged, "
    "film grain not oversaturated"
)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/s.rzytki/Documents/aiprojects/musicvideo
python3 -m pytest tests/test_image_generator.py::TestNegativeContextContent -v 2>&1 | tail -20
```

Expected: All PASS.

- [ ] **Step 5: Run full image_generator tests to check no regressions**

```bash
cd /Users/s.rzytki/Documents/aiprojects/musicvideo
python3 -m pytest tests/test_image_generator.py -v 2>&1 | tail -30
```

Expected: All tests PASS. Note: existing banned-words test uses word-boundary regex that allows "no Catholic imagery" — the new entries follow the same negation pattern so no regex changes needed.

- [ ] **Step 6: Commit**

```bash
cd /Users/s.rzytki/Documents/aiprojects/musicvideo
git add musicvid/pipeline/image_generator.py tests/test_image_generator.py
git commit -m "feat: extend NEGATIVE_CONTEXT with alcohol, drugs, gambling, and non-Protestant religions"
```

---

### Task 3: Update director_system.txt banned words and Pexels nature-only guidance

**Files:**
- Modify: `musicvid/prompts/director_system.txt`
- Test: `tests/test_stock_filtering.py` (extend `TestDirectorPromptFiltering`)

- [ ] **Step 1: Write failing tests for new director prompt requirements**

Add these tests to the `TestDirectorPromptFiltering` class in `tests/test_stock_filtering.py`:

```python
    def test_director_prompt_bans_alcohol_in_banned_words(self):
        prompt_path = Path(__file__).parent.parent / "musicvid" / "prompts" / "director_system.txt"
        prompt_text = prompt_path.read_text().lower()
        for word in ["alcohol", "beer", "wine", "whiskey", "drinking", "bar", "nightclub"]:
            assert word in prompt_text, f"Missing banned word in director prompt: {word}"

    def test_director_prompt_bans_smoking_gambling(self):
        prompt_path = Path(__file__).parent.parent / "musicvid" / "prompts" / "director_system.txt"
        prompt_text = prompt_path.read_text().lower()
        for word in ["gambling", "casino", "cigarette", "smoking"]:
            assert word in prompt_text, f"Missing banned word in director prompt: {word}"

    def test_director_prompt_restricts_pexels_to_nature_no_people(self):
        prompt_path = Path(__file__).parent.parent / "musicvid" / "prompts" / "director_system.txt"
        prompt_text = prompt_path.read_text()
        # Must mention that TYPE_VIDEO_STOCK is safest for nature without people
        assert "without people" in prompt_text.lower() or "no people" in prompt_text.lower() or "NOT" in prompt_text
        assert "TYPE_VIDEO_STOCK" in prompt_text
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/s.rzytki/Documents/aiprojects/musicvideo
python3 -m pytest tests/test_stock_filtering.py::TestDirectorPromptFiltering -v 2>&1 | tail -20
```

Expected: FAIL — "alcohol", "beer", etc. not in director_system.txt yet.

- [ ] **Step 3: Update director_system.txt — extend BANNED WORDS section**

In `musicvid/prompts/director_system.txt`, find the `BANNED WORDS` section (around line 90). Append these entries to the existing list:

Replace the block ending at line 101:
```
HDR, ultra-realistic, 8K, ultra HD, hyper-detailed
```

with:
```
HDR, ultra-realistic, 8K, ultra HD, hyper-detailed,
alcohol, beer, wine, whiskey, vodka, drinking glass, bar interior,
pub, cocktail, champagne, nightclub, drunk,
gambling, casino, cigarette, smoking, drugs,
violence, fight, nightlife, party wild
```

- [ ] **Step 4: Update director_system.txt — strengthen TYPE_VIDEO_STOCK nature-only guidance**

In `musicvid/prompts/director_system.txt`, find the TYPE_VIDEO_STOCK section (around line 14–27). After the line:
```
  TYPE_VIDEO_STOCK is SAFEST for nature and landscapes only.
  For people in prayer/worship — prefer TYPE_AI to avoid non-Protestant content.
```

Add this line:
```
  For all scenes with people (any activity) — prefer TYPE_AI for full prompt control.
  TYPE_VIDEO_STOCK: landscapes, sky, water, forests, mountains ONLY — no people, no activities.
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd /Users/s.rzytki/Documents/aiprojects/musicvideo
python3 -m pytest tests/test_stock_filtering.py::TestDirectorPromptFiltering -v 2>&1 | tail -20
```

Expected: All PASS.

- [ ] **Step 6: Run full stock_filtering tests**

```bash
cd /Users/s.rzytki/Documents/aiprojects/musicvideo
python3 -m pytest tests/test_stock_filtering.py -v 2>&1 | tail -30
```

Expected: All PASS.

- [ ] **Step 7: Commit**

```bash
cd /Users/s.rzytki/Documents/aiprojects/musicvideo
git add musicvid/prompts/director_system.txt tests/test_stock_filtering.py
git commit -m "feat: ban alcohol/gambling/smoking in director prompt and restrict TYPE_VIDEO_STOCK to nature-only"
```

---

### Task 4: Full regression run

**Files:** None (verification only)

- [ ] **Step 1: Run the full test suite**

```bash
cd /Users/s.rzytki/Documents/aiprojects/musicvideo
python3 -m pytest tests/ -v 2>&1 | tail -40
```

Expected: All tests PASS (currently ~523 tests; count may grow by ~20 from new tests added in tasks 1–3).

- [ ] **Step 2: If any failures, fix them**

Check the failure output. Common causes:
- Existing banned-words regex in `test_image_generator.py` — the regex `r'\b(?<!no )(?<!no\s)' + re.escape(word) + r'\b'` allows negation phrases. New `NEGATIVE_CONTEXT` additions all use "no X" prefix, so should be safe.
- `TestSanitizeQueryBlocked` parametrized with `BLOCKED_WORDS` — new words in `BLOCKED_WORDS` will be auto-included since the test parametrizes over the constant itself.

- [ ] **Step 3: Commit any fixes**

```bash
cd /Users/s.rzytki/Documents/aiprojects/musicvideo
git add -p
git commit -m "fix: resolve test regressions from content filtering expansion"
```
