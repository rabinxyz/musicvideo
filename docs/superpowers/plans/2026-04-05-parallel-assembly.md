# Parallel Assembly Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run all Stage 4 assemblies (YouTube + 3 social reels) in parallel via ThreadPoolExecutor when `--preset all` or `--preset social`, reducing Stage 4 time from ~sum-of-all to ~longest-single assembly.

**Architecture:** Extract per-assembly arguments into a dataclass (`AssemblyJob`), add `assemble_all_parallel()` using `ThreadPoolExecutor(max_workers=4)`, wire a `--sequential-assembly` CLI flag to fall back to sequential loops. All logic stays in `musicvid/musicvid.py`; `assembler.py` is unchanged.

**Tech Stack:** Python 3.11 stdlib (`concurrent.futures.ThreadPoolExecutor`, `psutil` for RAM check or `resource`), existing `assemble_video` from assembler, Click CLI.

---

### Task 1: Add `AssemblyJob` dataclass and `assemble_all_parallel()` to musicvid.py

**Files:**
- Modify: `musicvid/musicvid.py` (add dataclass + parallel helper before `_run_preset_mode`)
- Test: `tests/test_cli.py` (new `TestParallelAssembly` class)

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_cli.py`:

```python
import threading
from dataclasses import dataclass
from unittest.mock import MagicMock, patch, call
from click.testing import CliRunner

class TestParallelAssembly(unittest.TestCase):
    """Tests for assemble_all_parallel helper."""

    def _make_job(self, name, output_path="/tmp/out.mp4"):
        from musicvid.musicvid import AssemblyJob
        return AssemblyJob(
            name=name,
            kwargs={"output_path": output_path, "audio_path": "/tmp/audio.mp3"},
        )

    @patch("musicvid.musicvid.assemble_video")
    def test_parallel_calls_all_jobs(self, mock_av):
        from musicvid.musicvid import assemble_all_parallel
        jobs = [self._make_job(f"job{i}") for i in range(3)]
        results = assemble_all_parallel(jobs)
        self.assertEqual(mock_av.call_count, 3)
        self.assertEqual(len(results), 3)

    @patch("musicvid.musicvid.assemble_video")
    def test_parallel_runs_concurrently(self, mock_av):
        """All workers should start before any finish (barrier test)."""
        from musicvid.musicvid import assemble_all_parallel
        barrier = threading.Barrier(3, timeout=5)
        def side_effect(**kwargs):
            barrier.wait()
        mock_av.side_effect = side_effect
        jobs = [self._make_job(f"job{i}") for i in range(3)]
        # Should not deadlock — all 3 must be in-flight simultaneously
        assemble_all_parallel(jobs)

    @patch("musicvid.musicvid.assemble_video")
    def test_one_failure_does_not_stop_others(self, mock_av):
        from musicvid.musicvid import assemble_all_parallel
        def side_effect(**kwargs):
            if kwargs.get("output_path") == "/tmp/fail.mp4":
                raise RuntimeError("boom")
        mock_av.side_effect = side_effect
        jobs = [
            self._make_job("good1", "/tmp/good1.mp4"),
            self._make_job("fail",  "/tmp/fail.mp4"),
            self._make_job("good2", "/tmp/good2.mp4"),
        ]
        results = assemble_all_parallel(jobs)
        # Two successes, one failure → 2 results returned
        self.assertEqual(len(results), 2)

    @patch("musicvid.musicvid.assemble_video")
    def test_results_contain_output_paths(self, mock_av):
        from musicvid.musicvid import assemble_all_parallel
        jobs = [self._make_job("j1", "/tmp/a.mp4"), self._make_job("j2", "/tmp/b.mp4")]
        results = assemble_all_parallel(jobs)
        self.assertIn("/tmp/a.mp4", results)
        self.assertIn("/tmp/b.mp4", results)
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /Users/s.rzytki/Documents/aiprojects/musicvideo
python3 -m pytest tests/test_cli.py::TestParallelAssembly -v 2>&1 | head -30
```

Expected: `ImportError: cannot import name 'AssemblyJob'` or similar.

- [ ] **Step 3: Add `AssemblyJob` and `assemble_all_parallel` to musicvid.py**

Add after existing imports in `musicvid/musicvid.py`, before the `_run_preset_mode` definition:

```python
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed

@dataclass
class AssemblyJob:
    name: str          # e.g. "youtube", "rolka_A_15s"
    kwargs: dict = field(default_factory=dict)

def assemble_all_parallel(jobs, max_workers=4):
    """Run multiple assemble_video calls in parallel.

    Returns list of output_path strings for successful jobs.
    A failing job is logged but does not abort remaining jobs.
    """
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(assemble_video, **job.kwargs): job for job in jobs}
        for future in as_completed(futures):
            job = futures[future]
            try:
                future.result()
                output_path = job.kwargs["output_path"]
                results.append(output_path)
                click.echo(f"  ✅ Gotowe: {job.name}")
            except Exception as exc:
                click.echo(f"  ❌ Błąd: {job.name} — {exc}")
    return results
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
python3 -m pytest tests/test_cli.py::TestParallelAssembly -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add musicvid/musicvid.py tests/test_cli.py
git commit -m "feat: add AssemblyJob dataclass and assemble_all_parallel helper"
```

---

### Task 2: Add `--sequential-assembly` CLI flag

**Files:**
- Modify: `musicvid/musicvid.py` — add Click option and thread through to `_run_preset_mode`
- Test: `tests/test_cli.py` — new `TestSequentialAssemblyFlag` class

- [ ] **Step 1: Write the failing tests**

```python
class TestSequentialAssemblyFlag(unittest.TestCase):
    """--sequential-assembly forces one-at-a-time assembly."""

    def _base_patches(self):
        return [
            patch("musicvid.musicvid.get_audio_hash", return_value="abc123"),
            patch("musicvid.musicvid.load_cache", return_value=None),
            patch("musicvid.musicvid.save_cache"),
            patch("musicvid.musicvid.analyze_audio", return_value={"duration": 60, "lyrics": [], "beats": [], "sections": []}),
            patch("musicvid.musicvid.create_scene_plan", return_value={"scenes": [], "subtitle_style": {"animation": "fade"}, "master_style": ""}),
            patch("musicvid.musicvid.fetch_videos", return_value={}),
            patch("musicvid.musicvid.select_social_clips", return_value={"clips": [
                {"id": "A", "start": 0.0, "end": 15.0, "section": "verse"},
                {"id": "B", "start": 20.0, "end": 35.0, "section": "chorus"},
                {"id": "C", "start": 40.0, "end": 55.0, "section": "bridge"},
            ]}),
            patch("musicvid.musicvid.assemble_video"),
            patch("musicvid.musicvid.assemble_all_parallel"),
            patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf"),
            patch("os.path.exists", return_value=True),
        ]

    def test_default_preset_all_uses_parallel(self):
        from musicvid.musicvid import cli
        runner = CliRunner()
        patches = self._base_patches()
        with ExitStack() as stack:
            mocks = {p.attribute: stack.enter_context(p) for p in patches}
            mock_parallel = mocks["assemble_all_parallel"]
            mock_serial = mocks["assemble_video"]
            with runner.isolated_filesystem():
                open("song.mp3", "w").close()
                result = runner.invoke(cli, ["song.mp3", "--mode", "stock", "--preset", "all"])
            mock_parallel.assert_called_once()
            mock_serial.assert_not_called()

    def test_sequential_assembly_flag_skips_parallel(self):
        from musicvid.musicvid import cli
        runner = CliRunner()
        patches = self._base_patches()
        with ExitStack() as stack:
            mocks = {p.attribute: stack.enter_context(p) for p in patches}
            mock_parallel = mocks["assemble_all_parallel"]
            mock_serial = mocks["assemble_video"]
            with runner.isolated_filesystem():
                open("song.mp3", "w").close()
                result = runner.invoke(cli, ["song.mp3", "--mode", "stock", "--preset", "all", "--sequential-assembly"])
            mock_parallel.assert_not_called()
            # assemble_video called directly for each variant
            self.assertGreater(mock_serial.call_count, 0)
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
python3 -m pytest tests/test_cli.py::TestSequentialAssemblyFlag -v 2>&1 | head -20
```

Expected: `Error: No such option: --sequential-assembly`

- [ ] **Step 3: Add `--sequential-assembly` Click option to `cli()`**

In `musicvid/musicvid.py`, find the block of `@click.option` decorators before `def cli(...)`. Add:

```python
@click.option("--sequential-assembly", is_flag=True, default=False,
              help="Disable parallel Stage 4 assembly (use on low-RAM Macs)")
```

Also add `sequential_assembly` to the `def cli(...)` parameter list.

- [ ] **Step 4: Thread `sequential_assembly` into `_run_preset_mode`**

In `cli()`, find the `_run_preset_mode(...)` call and add `sequential_assembly=sequential_assembly`.

Update `_run_preset_mode` signature:

```python
def _run_preset_mode(preset, reel_duration, analysis, scene_plan, fetch_manifest,
                     audio_path, output_dir, stem, font, effects, cache_dir, new,
                     logo_path=None, logo_position="top-left", logo_size=None, logo_opacity=0.85,
                     lut_style=None, lut_intensity=0.85, sequential_assembly=False):
```

- [ ] **Step 5: Run tests to confirm they pass**

```bash
python3 -m pytest tests/test_cli.py::TestSequentialAssemblyFlag -v
```

Expected: 2 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add musicvid/musicvid.py tests/test_cli.py
git commit -m "feat(cli): add --sequential-assembly flag"
```

---

### Task 3: Refactor `_run_preset_mode` to use parallel assembly

**Files:**
- Modify: `musicvid/musicvid.py` — replace sequential loops with `assemble_all_parallel` / sequential fallback
- Test: `tests/test_cli.py` — verify `AssemblyJob` kwargs match what old sequential code passed

- [ ] **Step 1: Write the failing test**

```python
class TestPresetModeParallelKwargs(unittest.TestCase):
    """Verify AssemblyJob kwargs match what assemble_video expects."""

    @patch("musicvid.musicvid.assemble_all_parallel")
    def test_full_preset_job_has_correct_kwargs(self, mock_parallel):
        from musicvid.musicvid import _run_preset_mode, AssemblyJob
        mock_parallel.return_value = ["/out/pelny/song_youtube.mp4"]
        analysis = {"duration": 60, "lyrics": [], "beats": [], "sections": []}
        scene_plan = {"scenes": [], "subtitle_style": {"animation": "fade"}, "master_style": ""}
        import tempfile, pathlib
        with tempfile.TemporaryDirectory() as tmp:
            _run_preset_mode(
                preset="full",
                reel_duration=15,
                analysis=analysis,
                scene_plan=scene_plan,
                fetch_manifest={},
                audio_path="/tmp/audio.mp3",
                output_dir=pathlib.Path(tmp),
                stem="song",
                font="/fake/font.ttf",
                effects="minimal",
                cache_dir=pathlib.Path(tmp),
                new=False,
            )
        mock_parallel.assert_called_once()
        jobs = mock_parallel.call_args[0][0]
        self.assertEqual(len(jobs), 1)
        job = jobs[0]
        self.assertEqual(job.name, "youtube")
        self.assertEqual(job.kwargs["resolution"], "1080p")
        self.assertEqual(job.kwargs["audio_path"], "/tmp/audio.mp3")

    @patch("musicvid.musicvid.select_social_clips")
    @patch("musicvid.musicvid.load_cache", return_value=None)
    @patch("musicvid.musicvid.save_cache")
    @patch("musicvid.musicvid.assemble_all_parallel")
    def test_social_preset_creates_3_portrait_jobs(self, mock_parallel, mock_save, mock_load, mock_select):
        from musicvid.musicvid import _run_preset_mode
        mock_select.return_value = {"clips": [
            {"id": "A", "start": 0.0, "end": 15.0, "section": "verse"},
            {"id": "B", "start": 20.0, "end": 35.0, "section": "chorus"},
            {"id": "C", "start": 40.0, "end": 55.0, "section": "bridge"},
        ]}
        mock_parallel.return_value = []
        analysis = {"duration": 60, "lyrics": [], "beats": [], "sections": []}
        scene_plan = {"scenes": [], "subtitle_style": {"animation": "fade"}, "master_style": ""}
        import tempfile, pathlib
        with tempfile.TemporaryDirectory() as tmp:
            _run_preset_mode(
                preset="social",
                reel_duration=15,
                analysis=analysis,
                scene_plan=scene_plan,
                fetch_manifest={},
                audio_path="/tmp/audio.mp3",
                output_dir=pathlib.Path(tmp),
                stem="song",
                font="/fake/font.ttf",
                effects="minimal",
                cache_dir=pathlib.Path(tmp),
                new=False,
            )
        jobs = mock_parallel.call_args[0][0]
        self.assertEqual(len(jobs), 3)
        for job in jobs:
            self.assertEqual(job.kwargs["resolution"], "portrait")
            self.assertEqual(job.kwargs["audio_fade_out"], 1.5)
            self.assertEqual(job.kwargs["cinematic_bars"], False)
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
python3 -m pytest tests/test_cli.py::TestPresetModeParallelKwargs -v 2>&1 | head -20
```

Expected: FAIL — `_run_preset_mode` still calls `assemble_video` directly.

- [ ] **Step 3: Refactor `_run_preset_mode` body**

Replace the sequential `assemble_video(...)` calls in `_run_preset_mode` with job-building logic:

```python
def _run_preset_mode(preset, reel_duration, analysis, scene_plan, fetch_manifest,
                     audio_path, output_dir, stem, font, effects, cache_dir, new,
                     logo_path=None, logo_position="top-left", logo_size=None, logo_opacity=0.85,
                     lut_style=None, lut_intensity=0.85, sequential_assembly=False):
    """Handle --preset flag: generate full video and/or social reels."""
    generate_full = preset in ("full", "all")
    generate_social = preset in ("social", "all")

    # Social clip selection (unchanged)
    social_clips = None
    if generate_social:
        social_cache_name = f"social_clips_{reel_duration}s.json"
        social_clips = load_cache(str(cache_dir), social_cache_name) if not new else None
        if social_clips:
            click.echo(f"[social] Social clip selection ({reel_duration}s)... CACHED (skipped)")
        else:
            click.echo(f"[social] Selecting 3 × {reel_duration}s fragments...")
            social_clips = select_social_clips(analysis, reel_duration)
            save_cache(str(cache_dir), social_cache_name, social_clips)
        for clip in social_clips["clips"]:
            click.echo(f"  Clip {clip['id']}: {clip['start']:.1f}s–{clip['end']:.1f}s "
                       f"({clip.get('section', '?')}) — {clip.get('reason', '')}")

    click.echo("[4/4] Montaż:")

    # Build AssemblyJob list
    jobs = []

    if generate_full:
        pelny_dir = output_dir / "pelny"
        pelny_dir.mkdir(parents=True, exist_ok=True)
        full_output = str(pelny_dir / f"{stem}_youtube.mp4")
        jobs.append(AssemblyJob(
            name="youtube",
            kwargs=dict(
                analysis=analysis,
                scene_plan=scene_plan,
                fetch_manifest=fetch_manifest,
                audio_path=audio_path,
                output_path=full_output,
                resolution="1080p",
                font_path=font,
                effects_level=effects,
                logo_path=logo_path,
                logo_position=logo_position,
                logo_size=logo_size,
                logo_opacity=logo_opacity,
                cinematic_bars=(effects == "full"),
                lut_style=lut_style,
                lut_intensity=lut_intensity,
            ),
        ))

    if generate_social:
        social_dir = output_dir / "social"
        social_dir.mkdir(parents=True, exist_ok=True)
        for clip_info in social_clips["clips"]:
            clip_id = clip_info["id"]
            clip_start = clip_info["start"]
            clip_end = clip_info["end"]
            section = clip_info.get("section", "unknown")
            reel_output = str(social_dir / f"{stem}_rolka_{clip_id}_{reel_duration}s.mp4")
            clip_analysis = _filter_analysis_to_clip(analysis, clip_start, clip_end)
            clip_scene_plan = _filter_scene_plan_to_clip(scene_plan, clip_start, clip_end)
            for scene in clip_scene_plan["scenes"]:
                scene["motion"] = _remap_motion_for_portrait(scene.get("motion", "static"))
            clip_manifest = _filter_manifest_to_clip(
                fetch_manifest, scene_plan["scenes"], clip_start, clip_end
            )
            jobs.append(AssemblyJob(
                name=f"rolka_{clip_id}_{section}",
                kwargs=dict(
                    analysis=clip_analysis,
                    scene_plan=clip_scene_plan,
                    fetch_manifest=clip_manifest,
                    audio_path=audio_path,
                    output_path=reel_output,
                    resolution="portrait",
                    font_path=font,
                    effects_level=effects,
                    clip_start=clip_start,
                    clip_end=clip_end,
                    audio_fade_out=1.5,
                    subtitle_margin_bottom=200,
                    cinematic_bars=False,
                    logo_path=logo_path,
                    logo_position=logo_position,
                    logo_size=logo_size,
                    logo_opacity=logo_opacity,
                    lut_style=lut_style,
                    lut_intensity=lut_intensity,
                ),
            ))

    # Assemble: parallel (default) or sequential (--sequential-assembly)
    if sequential_assembly or len(jobs) == 1:
        output_paths = []
        for job in jobs:
            click.echo(f"  → {job.name}...")
            assemble_video(**job.kwargs)
            click.echo(f"  → {job.name}... ✅")
            output_paths.append(job.kwargs["output_path"])
    else:
        click.echo(f"  Równoległy montaż ({len(jobs)} wątki, max 4)...")
        output_paths = assemble_all_parallel(jobs)

    # Summary
    click.echo(f"\nGotowe! Wygenerowano {len(output_paths)} plików:")
    for path in output_paths:
        click.echo(f"  {path}")
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
python3 -m pytest tests/test_cli.py::TestPresetModeParallelKwargs tests/test_cli.py::TestParallelAssembly tests/test_cli.py::TestSequentialAssemblyFlag -v
```

Expected: all PASS.

- [ ] **Step 5: Run full test suite to check regressions**

```bash
python3 -m pytest tests/ -v 2>&1 | tail -20
```

Expected: all existing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add musicvid/musicvid.py tests/test_cli.py
git commit -m "feat: refactor _run_preset_mode to use parallel assembly via ThreadPoolExecutor"
```

---

### Task 4: RAM warning for low-memory Macs

**Files:**
- Modify: `musicvid/musicvid.py` — add RAM check in `assemble_all_parallel`
- Test: `tests/test_cli.py` — verify warning printed when RAM < 16 GB

- [ ] **Step 1: Write the failing test**

```python
class TestRamWarning(unittest.TestCase):

    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.psutil")
    def test_low_ram_prints_warning(self, mock_psutil, mock_av):
        from musicvid.musicvid import assemble_all_parallel, AssemblyJob
        # Simulate 8 GB RAM
        mock_psutil.virtual_memory.return_value = MagicMock(total=8 * 1024**3)
        import io
        from unittest.mock import patch as p
        jobs = [AssemblyJob(name="j1", kwargs={"output_path": "/tmp/a.mp4", "audio_path": "/a.mp3"})]
        with p("click.echo") as mock_echo:
            assemble_all_parallel(jobs)
            calls = [str(c) for c in mock_echo.call_args_list]
            self.assertTrue(any("RAM" in c for c in calls))

    @patch("musicvid.musicvid.assemble_video")
    @patch("musicvid.musicvid.psutil")
    def test_high_ram_no_warning(self, mock_psutil, mock_av):
        from musicvid.musicvid import assemble_all_parallel, AssemblyJob
        mock_psutil.virtual_memory.return_value = MagicMock(total=32 * 1024**3)
        jobs = [AssemblyJob(name="j1", kwargs={"output_path": "/tmp/a.mp4", "audio_path": "/a.mp3"})]
        with patch("click.echo") as mock_echo:
            assemble_all_parallel(jobs)
            calls = [str(c) for c in mock_echo.call_args_list]
            self.assertFalse(any("RAM" in c for c in calls))
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
python3 -m pytest tests/test_cli.py::TestRamWarning -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'psutil'` or `AttributeError`.

- [ ] **Step 3: Install psutil if needed and add RAM check to `assemble_all_parallel`**

```bash
pip install psutil
```

Update `assemble_all_parallel` in `musicvid/musicvid.py`:

```python
import psutil  # add near other stdlib imports at top of file

def assemble_all_parallel(jobs, max_workers=4):
    """Run multiple assemble_video calls in parallel via ThreadPoolExecutor.

    Warns when system RAM < 16 GB since each FFmpeg process uses ~2 GB.
    Returns list of output_path strings for successful jobs.
    """
    RAM_THRESHOLD_BYTES = 16 * 1024 ** 3
    total_ram = psutil.virtual_memory().total
    if total_ram < RAM_THRESHOLD_BYTES:
        ram_gb = total_ram / 1024 ** 3
        click.echo(
            f"  ⚠️  Uwaga: równoległy montaż wymaga ~8GB RAM "
            f"(wykryto {ram_gb:.0f}GB). "
            f"Jeśli Mac zwalnia użyj --sequential-assembly"
        )

    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(assemble_video, **job.kwargs): job for job in jobs}
        for future in as_completed(futures):
            job = futures[future]
            try:
                future.result()
                output_path = job.kwargs["output_path"]
                results.append(output_path)
                click.echo(f"  ✅ Gotowe: {job.name}")
            except Exception as exc:
                click.echo(f"  ❌ Błąd: {job.name} — {exc}")
    return results
```

- [ ] **Step 4: Run tests**

```bash
python3 -m pytest tests/test_cli.py::TestRamWarning -v
```

Expected: 2 tests PASS.

- [ ] **Step 5: Run full test suite**

```bash
python3 -m pytest tests/ -v 2>&1 | tail -10
```

Expected: all PASS (no regressions from psutil import).

- [ ] **Step 6: Commit**

```bash
git add musicvid/musicvid.py tests/test_cli.py
git commit -m "feat: add RAM warning in assemble_all_parallel for Macs with <16GB"
```

---

## Self-Review Against Spec

| Spec requirement | Covered by |
|---|---|
| `--preset all`: 4 assemblies parallel via ThreadPoolExecutor | Task 1 + Task 3 |
| Stage 4 time = longest assembly (not sum) | Task 1 `assemble_all_parallel` |
| One reel failure doesn't abort youtube | Task 1 `test_one_failure_does_not_stop_others` |
| `--sequential-assembly` restores sequential behavior | Task 2 + Task 3 |
| Output files in correct folders (pelny/ social/) | Task 3 (paths preserved in kwargs) |
| `python3 -m pytest tests/ -v` passes | Verified in each task's step 5 |
| RAM warning when < 16 GB | Task 4 |
| Progress logging during parallel assembly | Task 1 `click.echo` in `assemble_all_parallel` |
