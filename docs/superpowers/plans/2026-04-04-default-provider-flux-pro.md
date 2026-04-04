# Default Provider flux-pro Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Change the CLI default `--provider` from `flux-dev` to `flux-pro`.

**Architecture:** Single-line change in Click option definition. Update CLAUDE.md docs to match.

**Tech Stack:** Python/Click CLI

---

### Task 1: Change CLI default provider

**Files:**
- Modify: `musicvid/musicvid.py:36`

- [ ] **Step 1: Change the default value**

In `musicvid/musicvid.py` line 36, change:
```python
@click.option("--provider", type=click.Choice(["flux-dev", "flux-pro", "flux-schnell"]), default="flux-dev", help="Image provider for --mode ai.")
```
to:
```python
@click.option("--provider", type=click.Choice(["flux-dev", "flux-pro", "flux-schnell"]), default="flux-pro", help="Image provider for --mode ai.")
```

- [ ] **Step 2: Verify --help shows flux-pro as default**

Run: `python3 -m musicvid.musicvid --help 2>&1 | grep provider`
Expected: output contains `[default: flux-pro]`

- [ ] **Step 3: Run existing tests**

Run: `python3 -m pytest tests/ -v`
Expected: All tests pass (the test_default_provider_is_flux_dev tests the `generate_images` function default, not the CLI default, so it should still pass)

- [ ] **Step 4: Update CLAUDE.md**

In CLAUDE.md, change:
```
- `--provider [flux-dev|flux-pro|flux-schnell]` (default: flux-dev): selects BFL model for `--mode ai`
```
to:
```
- `--provider [flux-dev|flux-pro|flux-schnell]` (default: flux-pro): selects BFL model for `--mode ai`
```

- [ ] **Step 5: Commit**

```bash
git add musicvid/musicvid.py CLAUDE.md
git commit -m "feat: change default --provider from flux-dev to flux-pro"
```
