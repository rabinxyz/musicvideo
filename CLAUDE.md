# MusicVid - Christian Music Video Generator

## Project Overview
CLI tool that generates synchronized MP4 music videos from audio files using stock footage, beat-synced cuts, and whisper-based subtitles.

## Commands
- `python3 -m pytest tests/ -v` - run all tests (56 tests)
- `python3 -m musicvid.musicvid song.mp3` - run the CLI (uses cache by default)
- `python3 -m musicvid.musicvid song.mp3 --new` - force recalculation, ignore cache
- `python3 -c "import musicvid; print(musicvid.__version__)"` - check version

## Architecture
4-stage pipeline: audio_analyzer → director → stock_fetcher/image_generator → assembler, orchestrated by Click CLI in `musicvid/musicvid.py`.
- `--mode stock` (default): Stage 3 uses `stock_fetcher` (Pexels API)
- `--mode ai`: Stage 3 uses `image_generator` (multi-provider: flux-dev/flux-pro/schnell/dalle), caches to `image_manifest.json`
- `--provider [flux-dev|flux-pro|schnell|dalle]` (default: flux-dev): selects image generation provider for `--mode ai`

## Caching
- Content-addressed cache in `output/tmp/{audio_hash}/` (MD5 of first 64KB, 12 chars)
- Cached files: `audio_analysis.json`, `scene_plan.json`, `video_manifest.json`, `image_manifest.json` (ai mode)
- Stages 1-3 skip if cached; stage 3 also verifies video files exist on disk
- `--new` flag forces full recalculation (deletes cache dir)
- Cache utilities in `musicvid/pipeline/cache.py` (`get_audio_hash`, `load_cache`, `save_cache`)

## Code Style
- Python 3.11+, no type annotations in existing code
- Tests use `unittest.mock` with `@patch` decorators targeting module-level imports
- External APIs (Whisper, Claude, Pexels, OpenAI/DALL-E, fal.ai/Flux, MoviePy) are fully mocked in tests
- `tenacity` retry on all external API calls

## Key Gotchas
- MoviePy 2.1.2 is installed — assembler imports directly from `moviepy` (no `moviepy.editor`)
- MoviePy 2.x API: use `transform()` not `fl()`, `with_position()` not `set_position()`, `with_effects([vfx.CrossFadeIn(d)])` not `crossfadein(d)`, `TextClip(text=..., font_size=...)` not `TextClip(txt, fontsize=...)`
- `librosa` must be mocked at module level (`musicvid.pipeline.audio_analyzer.librosa`) since `_detect_sections` calls multiple librosa functions
- Stock fetcher tests need `PEXELS_API_KEY` env var set via `@patch.dict(os.environ)` to exercise API code path
- Image generator Flux tests need `FAL_KEY` env var via `@patch.dict(os.environ)` and mock `fal_client` and `requests` at module level
- Image generator DALL-E tests need `OPENAI_API_KEY` env var via `@patch.dict(os.environ)` and mock `openai` and `requests` at module level
- Image generator retry tests must patch tenacity wait to `wait_none()` to avoid slow tests
- Use `python3` not `python` on this macOS system

## Environment
- macOS, Python 3.14, requires `ffmpeg` and `imagemagick` via Homebrew
- API keys: ANTHROPIC_API_KEY, OPENAI_API_KEY, PEXELS_API_KEY, FAL_KEY (in `.env`)
