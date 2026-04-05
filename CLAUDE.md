# MusicVid - Christian Music Video Generator

## Project Overview
CLI tool that generates synchronized MP4 music videos from audio files using stock footage, beat-synced cuts, and whisper-based subtitles.

## Commands
- `python3 -m pytest tests/ -v` - run all tests (~250 tests)
- `python3 -m musicvid.musicvid song.mp3` - run the CLI (uses cache by default)
- `python3 -m musicvid.musicvid song.mp3 --new` - force recalculation, ignore cache
- `python3 -c "import musicvid; print(musicvid.__version__)"` - check version

## Architecture
4-stage pipeline: audio_analyzer → director → stock_fetcher/image_generator → assembler, orchestrated by Click CLI in `musicvid/musicvid.py`.
- `--mode stock` (default): Stage 3 uses `stock_fetcher` (Pexels API)
- `--mode ai`: Stage 3 uses `image_generator` (BFL API: flux-dev/flux-pro-1.1/flux-2-klein-4b), caches to `image_manifest.json`
- `--provider [flux-dev|flux-pro|flux-schnell]` (default: flux-pro): selects BFL model for `--mode ai`
- `--font PATH`: custom .ttf font for subtitles (optional, defaults to auto-downloaded Montserrat Light)
- `--lyrics PATH`: custom .txt lyrics file (optional); auto-detects single .txt in audio dir. When provided, Whisper still runs for timing, then Claude API aligns file text to Whisper segments
- `--effects [none|minimal|full]` (default: minimal): visual effects level — none (Ken Burns only), minimal (warm grade + vignette + cinematic bars), full (+ film grain + light leak)
- `--clip [15|20|25|30]`: generate short social-media clip — Claude selects best fragment (chorus preferred); clips analysis to window before director; output named `{stem}_{N}s.mp4`
- `--platform [reels|shorts|tiktok]`: forces portrait 9:16 resolution (1080×1920) and adds platform name to output filename; use with `--clip`
- `--title-card`: prepends 2s black title card with song name; only active when used with `--clip`
- `--animate [auto|always|never]` (default: auto): Runway Gen-4 image-to-video for scenes marked animate=true by director; `never` skips all animation; `always` forces all scenes animated; fallback to Ken Burns when RUNWAY_API_KEY absent
- Director scene plan: now includes `master_style` (top-level string appended to all BFL prompts), `animate` (bool per scene), `motion_prompt` (str per scene); `_validate_scene_plan` defaults missing fields
- Director JSON robustness: `max_tokens=8192`; `_strip_markdown(text)` strips ` ``` ` / ` ```json ` fences; on `JSONDecodeError` tries `_repair_truncated_json` (brace counting) then `_repair_truncated_json_aggressive` (stack-based) before retrying Claude with brevity instruction
- Director scene limits: `_build_user_message` passes `max_scenes` to Claude based on duration (≤3 min→10, 3-5 min→12, >5 min→15); system prompt caps `visual_prompt` at 200 chars
- Runway animator: `musicvid/pipeline/video_animator.py` — `animate_image(image_path, motion_prompt, duration, output_path)` calls Runway Gen-4; POLL_INTERVAL=3s, POLL_TIMEOUT=300s; cache check via output_path exists; mock target: `@patch("musicvid.pipeline.video_animator.requests")` + `@patch("musicvid.pipeline.video_animator.time")`
- CLI tests for `--animate` must mock `@patch("musicvid.musicvid.animate_image")` since animate_image is imported at module level
- Assembler `_load_scene_clip`: skips Ken Burns for scenes with `animate=True` and `.mp4` suffix — just resizes to target_size
- Clip selector: `musicvid/pipeline/clip_selector.py` — `select_clip(analysis, clip_duration)` calls Claude API; manual 2-attempt retry loop with fallback to song center; mock target: `@patch("musicvid.pipeline.clip_selector.anthropic")`
- `--preset [full|social|all]`: preset mode — `full` generates YouTube 16:9 in `output/pelny/`, `social` generates 3 reels (9:16) from different sections in `output/social/`, `all` generates both. Stages 1-3 run once; stage 4 loops per variant. Uses `_run_preset_mode()` in `musicvid.py`
- `--reel-duration [15|20|30]` (default: 15): duration of social reels; invalidates social clips cache
- Social clip selector: `musicvid/pipeline/social_clip_selector.py` — `select_social_clips(analysis, clip_duration)` asks Claude for 3 non-overlapping clips from different sections; mock: `@patch("musicvid.pipeline.social_clip_selector.anthropic")`
- CLI tests for `--preset` must mock `@patch("musicvid.musicvid.select_social_clips")` in addition to the usual pipeline mocks
- Scene plan/manifest clip filters: `_filter_scene_plan_to_clip(scene_plan, clip_start, clip_end)` and `_filter_manifest_to_clip(manifest, scenes, clip_start, clip_end)` in `musicvid.py` — filter and offset scenes/manifest entries to a clip time window
- Assembler social mode kwargs: `audio_fade_out=1.0` (social uses 1.5), `subtitle_margin_bottom=80` (social uses 200), `cinematic_bars=False` (default); standard/preset-full passes `cinematic_bars=(effects == "full")`, social explicitly passes `False`
- Ken Burns `pan_up`/`pan_down` motions added; `_remap_motion_for_portrait(motion)` maps horizontal pans to vertical for 9:16
- Clip analysis filter: `_filter_analysis_to_clip(analysis, clip_start, clip_end)` in `musicvid.py` — offsets lyrics/beats/sections to clip-relative t=0 before passing to director
- Lyrics parser: `musicvid/pipeline/lyrics_parser.py` — `align_with_claude(whisper_segments, file_lines)` for AI alignment via Claude API; also has `parse()` with variant A (plain text, even distribution) and B (MM:SS/HH:MM:SS timestamps)
- Visual effects: `musicvid/pipeline/effects.py` — `apply_effects(clip, level)` orchestrates per-frame transforms (warm grade, vignette, film grain) and overlay effects (cinematic bars, light leak)
- `--logo PATH`: overlay logo (SVG/PNG/JPG) on video as topmost layer with broadcast safe-zone margin (5% of shorter dimension)
- `--logo-position [top-left|top-right|bottom-left|bottom-right]` (default: top-left): logo placement corner
- `--logo-size INT`: logo width in px (default: auto 12% of frame width)
- `--logo-opacity FLOAT` (default: 0.85): logo transparency
- Logo overlay: `musicvid/pipeline/logo_overlay.py` — `compute_margin`, `compute_logo_size`, `get_logo_position`, `load_logo`, `apply_logo`; SVG via `cairosvg` at 2x retina resolution; PNG/JPG via Pillow; opacity applied by scaling alpha channel
- Assembler `assemble_video` accepts `logo_path`, `logo_position`, `logo_size`, `logo_opacity` kwargs; logo composited as last layer (above cinematic bars, light leaks, subtitles)
- Assembler tests for logo must mock `@patch("musicvid.pipeline.assembler.apply_logo")`
- Logo overlay tests mock `@patch("musicvid.pipeline.logo_overlay.ImageClip")` and `@patch("musicvid.pipeline.logo_overlay.cairosvg")` for SVG tests

## Caching
- Content-addressed cache in `output/tmp/{audio_hash}/` (MD5 of first 64KB, 12 chars)
- Cached files: `audio_analysis.json` (or `audio_analysis_{lyrics_hash}.json` when --lyrics used), `lyrics_aligned_{lyrics_hash}.json` (AI alignment result), `scene_plan.json`, `video_manifest.json`, `image_manifest.json` (ai mode)
- Clip mode adds separate cache files: `clip_{N}s.json` (clip selection), `scene_plan_clip_{N}s.json`, `video_manifest_clip_{N}s.json` / `image_manifest_clip_{N}s.json` — changing `--clip` only invalidates `clip_{N}s.json`
- Preset mode adds `social_clips_{N}s.json` (3-clip selection); cache key includes reel duration so `--reel-duration 30` creates a separate cache entry
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
- AI lyrics alignment: `align_with_claude` in `lyrics_parser.py` mocks `anthropic` at module level: `@patch("musicvid.pipeline.lyrics_parser.anthropic")`; uses manual retry loop (2 attempts) instead of tenacity
- CLI tests with `--lyrics` must also mock `@patch("musicvid.musicvid.align_with_claude")` since lyrics flow now uses AI alignment instead of `parse_lyrics`
- Font loader: `musicvid/pipeline/font_loader.py` auto-downloads Montserrat from Google Fonts ZIP, falls back to system DejaVuSans
- CLI tests that run the full pipeline must mock `get_font_path` via `@patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")`
- Assembler tests must mock effects imports: `@patch("musicvid.pipeline.assembler.apply_effects")`, `@patch("musicvid.pipeline.assembler.create_cinematic_bars")`, `@patch("musicvid.pipeline.assembler.create_light_leak")`
- Assembler clip mode tests must also mock `@patch("musicvid.pipeline.assembler.afx")` and `@patch("musicvid.pipeline.assembler.ColorClip")` to test fades and title card
- Assembler `assemble_video` accepts `clip_start`, `clip_end`, `title_card_text` kwargs; audio trimmed via `audio.subclipped(clip_start, clip_end)` + `afx.AudioFadeIn/AudioFadeOut`; video via `vfx.FadeIn/FadeOut`
- Assembler `RESOLUTION_MAP` includes `"portrait": (1080, 1920)` for social media clips
- CLI tests for `--clip` must mock `@patch("musicvid.musicvid.select_clip")` in addition to the usual pipeline mocks
- Effects per-frame transforms use `clip.transform(fn)` where `fn(get_frame, t)` returns numpy array; test by extracting transform_fn from `mock_clip.transform.call_args[0][0]`
- `_create_ken_burns_clip` test mocks need `mock_clip.size=(w,h)`, `mock_clip.w=w`, `mock_clip.h=h`, `mock_clip.cropped.return_value=mock_clip` — omitting breaks the mock chain since `cropped()` returns an unconfigured auto-MagicMock
- MoviePy 2.x cover-scale: `scale = max(tw/iw, th/ih); clip = clip.resized(scale); clip = clip.cropped(x1=x1, y1=y1, x2=x1+tw, y2=y1+th)` — scalar for proportional resize, explicit pixel coords for crop
- `_create_subtitle_clips` has try/except around `TextClip` creation — silently skips failed segments; logs each lyric line; falls back to `font=None` if named font fails
- Use `python3` not `python` on this macOS system

## Environment
- macOS, Python 3.14, requires `ffmpeg` and `imagemagick` via Homebrew
- API keys: ANTHROPIC_API_KEY, PEXELS_API_KEY, BFL_API_KEY, RUNWAY_API_KEY (optional, for --animate) in `.env`
- `cairosvg` required for SVG logo files (optional dependency, only needed when `--logo` points to .svg)
