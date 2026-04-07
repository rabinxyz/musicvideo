# Fix librosa.feature.rms() sr Parameter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the unsupported `sr` parameter from all `librosa.feature.rms()` calls in `audio_analyzer.py`.

**Architecture:** Single-line fix — newer librosa versions dropped the `sr` parameter from `feature.rms()`. Remove it; the result is identical since `sr` was never used in RMS computation.

**Tech Stack:** Python, librosa

---

### Task 1: Fix librosa.feature.rms() call

**Files:**
- Modify: `musicvid/pipeline/audio_analyzer.py:160`

- [ ] **Step 1: Verify the offending line**

Run: `grep -n "librosa.feature.rms" musicvid/pipeline/audio_analyzer.py`
Expected: line 160 contains `sr=sr`

- [ ] **Step 2: Apply the fix**

In `musicvid/pipeline/audio_analyzer.py` line 160, change:
```python
rms = librosa.feature.rms(y=y, sr=sr, hop_length=512)[0]
```
to:
```python
rms = librosa.feature.rms(y=y, hop_length=512)[0]
```

- [ ] **Step 3: Run the audio analyzer tests**

Run: `python3 -m pytest tests/test_audio_analyzer.py -v`
Expected: all tests PASS

- [ ] **Step 4: Commit**

```bash
git add musicvid/pipeline/audio_analyzer.py
git commit -m "fix: remove unsupported sr param from librosa.feature.rms() call"
```
