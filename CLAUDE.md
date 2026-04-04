# MusicVid - Christian Music Video Generator

## Project Overview
CLI tool that generates synchronized MP4 music videos from audio files using stock footage, beat-synced cuts, and whisper-based subtitles.

## Commands
- `python3 -m pytest tests/ -v` - run all tests (27 tests)
- `python3 -m musicvid.musicvid song.mp3` - run the CLI
- `python3 -c "import musicvid; print(musicvid.__version__)"` - check version

## Architecture
4-stage pipeline: audio_analyzer → director → stock_fetcher → assembler, orchestrated by Click CLI in `musicvid/musicvid.py`.

## Code Style
- Python 3.11+, no type annotations in existing code
- Tests use `unittest.mock` with `@patch` decorators targeting module-level imports
- External APIs (Whisper, Claude, Pexels, MoviePy) are fully mocked in tests
- `tenacity` retry on all external API calls

## Key Gotchas
- MoviePy 2.1.2 is installed — assembler imports directly from `moviepy` (no `moviepy.editor`)
- MoviePy 2.x API: use `transform()` not `fl()`, `with_position()` not `set_position()`, `with_effects([vfx.CrossFadeIn(d)])` not `crossfadein(d)`, `TextClip(text=..., font_size=...)` not `TextClip(txt, fontsize=...)`
- `librosa` must be mocked at module level (`musicvid.pipeline.audio_analyzer.librosa`) since `_detect_sections` calls multiple librosa functions
- Stock fetcher tests need `PEXELS_API_KEY` env var set via `@patch.dict(os.environ)` to exercise API code path
- Use `python3` not `python` on this macOS system

## Environment
- macOS, Python 3.14, requires `ffmpeg` and `imagemagick` via Homebrew
- API keys: ANTHROPIC_API_KEY, OPENAI_API_KEY, PEXELS_API_KEY (in `.env`)
