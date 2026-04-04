# MusicVid - Christian Music Video Generator

## Project Overview
CLI tool that generates synchronized MP4 music videos from audio files using stock footage, beat-synced cuts, and whisper-based subtitles.

## Commands
- `python3 -m pytest tests/ -v` - run all tests (99 tests)
- `python3 -m musicvid.musicvid song.mp3` - run the CLI (uses cache by default)
- `python3 -m musicvid.musicvid song.mp3 --new` - force recalculation, ignore cache
- `python3 -c "import musicvid; print(musicvid.__version__)"` - check version

## Architecture
4-stage pipeline: audio_analyzer → director → stock_fetcher/image_generator → assembler, orchestrated by Click CLI in `musicvid/musicvid.py`.
- `--mode stock` (default): Stage 3 uses `stock_fetcher` (Pexels API)
- `--mode ai`: Stage 3 uses `image_generator` (BFL API: flux-dev/flux-pro-1.1/flux-2-klein-4b), caches to `image_manifest.json`
- `--provider [flux-dev|flux-pro|flux-schnell]` (default: flux-pro): selects BFL model for `--mode ai`
- `--font PATH`: custom .ttf font for subtitles (optional, defaults to auto-downloaded Montserrat Light)
- `--lyrics PATH`: custom .txt lyrics file (optional, skips Whisper); auto-detects single .txt in audio dir
- `--effects [none|minimal|full]` (default: minimal): visual effects level — none (Ken Burns only), minimal (warm grade + vignette + cinematic bars), full (+ film grain + light leak)
- Lyrics parser: `musicvid/pipeline/lyrics_parser.py` — variant A (plain text, even distribution) and B (MM:SS/HH:MM:SS timestamps)
- Visual effects: `musicvid/pipeline/effects.py` — `apply_effects(clip, level)` orchestrates per-frame transforms (warm grade, vignette, film grain) and overlay effects (cinematic bars, light leak)

## Caching
- Content-addressed cache in `output/tmp/{audio_hash}/` (MD5 of first 64KB, 12 chars)
- Cached files: `audio_analysis.json` (or `audio_analysis_{lyrics_hash}.json` when --lyrics used), `scene_plan.json`, `video_manifest.json`, `image_manifest.json` (ai mode)
- Stages 1-3 skip if cached; stage 3 also verifies video files exist on disk
- `--new` flag forces full recalculation (deletes cache dir)
- Cache utilities in `musicvid/pipeline/cache.py` (`get_audio_hash`, `load_cache`, `save_cache`)

## Code Style
- Python 3.11+, no type annotations in existing code
- Tests use `unittest.mock` with `@patch` decorators targeting module-level imports
- External APIs (Whisper, Claude, Pexels, BFL/Flux, MoviePy) are fully mocked in tests
- `tenacity` retry on all external API calls

## Key Gotchas
- MoviePy 2.1.2 is installed — assembler imports directly from `moviepy` (no `moviepy.editor`)
- MoviePy 2.x API: use `transform()` not `fl()`, `with_position()` not `set_position()`, `with_effects([vfx.CrossFadeIn(d)])` not `crossfadein(d)`, `TextClip(text=..., font_size=...)` not `TextClip(txt, fontsize=...)`
- `librosa` must be mocked at module level (`musicvid.pipeline.audio_analyzer.librosa`) since `_detect_sections` calls multiple librosa functions
- Stock fetcher tests need `PEXELS_API_KEY` env var set via `@patch.dict(os.environ)` to exercise API code path
- Image generator BFL tests need `BFL_API_KEY` env var via `@patch.dict(os.environ)` and mock `requests` at module level
- BFL API flow: `_submit_task` returns `(task_id, polling_url)` tuple; `_poll_result` takes `polling_url` (not task_id)
- BFL API payload: only `prompt`, `width`, `height` — no `output_format`, `safety_tolerance`, or `prompt_upsampling`; use 1024x768 (1280x720 causes 422 from flux-dev)
- Image generator polling tests mock `time.monotonic` and `time.sleep` to control timing
- Image generator retry tests must patch tenacity wait to `wait_none()` to avoid slow tests
- Font loader: `musicvid/pipeline/font_loader.py` auto-downloads Montserrat from Google Fonts ZIP, falls back to system DejaVuSans
- CLI tests that run the full pipeline must mock `get_font_path` via `@patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")`
- Assembler tests must mock effects imports: `@patch("musicvid.pipeline.assembler.apply_effects")`, `@patch("musicvid.pipeline.assembler.create_cinematic_bars")`, `@patch("musicvid.pipeline.assembler.create_light_leak")`
- Effects per-frame transforms use `clip.transform(fn)` where `fn(get_frame, t)` returns numpy array; test by extracting transform_fn from `mock_clip.transform.call_args[0][0]`
- Use `python3` not `python` on this macOS system

## Environment
- macOS, Python 3.14, requires `ffmpeg` and `imagemagick` via Homebrew
- API keys: ANTHROPIC_API_KEY, PEXELS_API_KEY, BFL_API_KEY (in `.env`)
