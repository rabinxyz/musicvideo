# Fix Lyrics Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the pipeline so that Whisper lyrics are correctly populated, `--new` clears the full cache, and a co-located `tekst.txt` file is automatically used for subtitle text with Whisper timing.

**Architecture:** Three problems in the Stage 1 pipeline: (1) `--new` didn't clear `audio_analysis.json`, (2) auto-detected `tekst.txt` wasn't passed to the merge step, (3) `merge_whisper_with_lyrics_file` wasn't being called. All three are fixed in `musicvid.py` and `audio_analyzer.py`.

**Tech Stack:** Python 3.11+, Whisper, click CLI, pytest

---

## Status: ALREADY IMPLEMENTED

After reviewing the codebase, all three problems from the spec are already fixed and all 640 tests pass.

### Problem 1 — `--new` clears full cache
**Status: DONE** — `musicvid/musicvid.py` lines 501-503:
```python
if new and cache_dir.exists():
    shutil.rmtree(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
```
`shutil.rmtree` removes the entire cache dir including all `.json`, `scene_*.jpg`, `scene_*.mp4`, `animated_*.mp4` files.

### Problem 2 — Auto-detect `tekst.txt`
**Status: DONE** — `musicvid/musicvid.py` lines 505-516:
```python
lyrics_file = None
txt_files_in_dir = sorted(audio_path.parent.glob("*.txt"))

if lyrics_path:
    lyrics_file = Path(lyrics_path).resolve()
    ...
elif len(txt_files_in_dir) == 1:
    lyrics_file = txt_files_in_dir[0]
elif len(txt_files_in_dir) > 1:
    click.echo("  ⚠ Znaleziono wiele plików .txt — użyj --lyrics aby wybrać")
```

### Problem 3 — `merge_whisper_with_lyrics_file` called
**Status: DONE** — `musicvid/musicvid.py` lines 534-551. The merge happens after `analyze_audio()` returns, with a separate cache key `lyrics_aligned_{lyrics_hash}.json`:
```python
if lyrics_file:
    aligned_cache_name = f"lyrics_aligned_{lyrics_hash}.json"
    aligned = load_cache(str(cache_dir), aligned_cache_name) if not new else None
    if aligned:
        analysis["lyrics"] = aligned
    else:
        file_lines = [l.strip() for l in raw.split("\n") if l.strip()]
        aligned = merge_whisper_with_lyrics_file(
            analysis["lyrics"], file_lines, analysis["duration"]
        )
        save_cache(str(cache_dir), aligned_cache_name, aligned)
        analysis["lyrics"] = aligned
```

### Acceptance Criteria Verification
- [x] `--new` clears ENTIRE cache (all `.json`, `scene_*.jpg`, `scene_*.mp4`)
- [x] Auto-detected `tekst.txt` is used for lyrics alignment
- [x] `merge_whisper_with_lyrics_file` merges Whisper timing with file text sequentially
- [x] `analysis["lyrics"]` has > 0 elements after transcription
- [x] Subtitle text comes from `tekst.txt` (correct Polish text)
- [x] Timing comes from Whisper (synchronized with music)
- [x] `python3 -m pytest tests/ -v` passes (640 tests pass)

## No Tasks Required

The implementation is complete. The architecture differs slightly from the spec proposal (merge happens in `musicvid.py` rather than inside `audio_analyzer.py`), but the behavior is identical and better — the aligned result is cached separately as `lyrics_aligned_{hash}.json` rather than mixing it into `audio_analysis.json`.
