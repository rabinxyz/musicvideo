# MusicVid - Christian Music Video Generator

## Project Overview
CLI tool that generates synchronized MP4 music videos from audio files using stock footage, beat-synced cuts, and whisper-based subtitles.

## Commands
- `python3 -m pytest tests/ -v` - run all tests (~416 tests)
- `python3 -m musicvid.musicvid song.mp3` - run the CLI (uses cache by default)
- `python3 -m musicvid.musicvid song.mp3 --new` - force recalculation, ignore cache
- `python3 -c "import musicvid; print(musicvid.__version__)"` - check version

## Architecture
4-stage pipeline: audio_analyzer → director → visual_router/stock_fetcher → assembler, orchestrated by Click CLI in `musicvid/musicvid.py`.
- `--mode ai` (default): Stage 3 uses `VisualRouter` (hybrid per-scene sourcing — Pexels/Unsplash/BFL/Runway), caches to `image_manifest.json`; `--mode stock` uses `stock_fetcher` (Pexels API for all scenes)
- Hybrid visual sourcing: director outputs `visual_source` (TYPE_VIDEO_STOCK|TYPE_PHOTO_STOCK|TYPE_AI|TYPE_ANIMATED) and `search_query` per scene; `VisualRouter` in `musicvid/pipeline/visual_router.py` dispatches to the correct API; `_validate_scene_plan` defaults `visual_source="TYPE_AI"`, `search_query=""`, `visual_prompt=""`
- VisualRouter fallback chain: TYPE_VIDEO_STOCK → simplified query (2 words) → TYPE_PHOTO_STOCK → TYPE_AI; TYPE_PHOTO_STOCK no key → TYPE_AI; TYPE_ANIMATED no RUNWAY_API_KEY → static image (Ken Burns)
- `--animate` with VisualRouter: `never` converts TYPE_ANIMATED→TYPE_AI; `always` converts all→TYPE_ANIMATED + enforce_animation_rules; `auto` keeps director's visual_source + enforce_animation_rules
- CLI tests for mode=ai must mock `@patch("musicvid.musicvid.VisualRouter")` — `generate_images` and `animate_image` are no longer called directly from `cli()` in ai mode
- `fetch_manifest` entries in ai mode now include `start`, `end`, `source` keys (in addition to `scene_index`, `video_path`)
- `UNSPLASH_ACCESS_KEY` env var: optional, for TYPE_PHOTO_STOCK scenes (free at unsplash.com/developers, 50 req/h)
- `generate_single_image(prompt, output_path, provider)` added to `image_generator.py` — generates a single image (used by VisualRouter internally)
- `fetch_video_by_query(query, min_duration, output_path)` added to `stock_fetcher.py` — direct query without style mapping (used by VisualRouter)
- `--provider [flux-dev|flux-pro|flux-schnell]` (default: flux-pro): selects BFL model for `--mode ai`
- `--font PATH`: custom .ttf font for subtitles (optional, defaults to auto-downloaded Montserrat Light)
- `--lyrics PATH`: custom .txt lyrics file (optional); auto-detects single .txt in audio dir. When provided, Whisper still runs for timing, then Claude API aligns file text to Whisper segments
- `--effects [none|minimal|full]` (default: minimal): visual effects level — none (Ken Burns only), minimal (warm grade + vignette + subtle_film_look + cinematic bars), full (+ film grain + light leak)
- `--clip [15|20|25|30]`: generate short social-media clip — Claude selects best fragment (chorus preferred); clips analysis to window before director; output named `{stem}_{N}s.mp4`
- `--platform [reels|shorts|tiktok]`: forces portrait 9:16 resolution (1080×1920) and adds platform name to output filename; use with `--clip`
- `--title-card`: prepends 2s black title card with song name; only active when used with `--clip`
- `--animate [auto|always|never]` (default: auto): controls TYPE_ANIMATED scenes; `never` converts all to TYPE_AI; `always` converts all to TYPE_ANIMATED; fallback to Ken Burns when RUNWAY_API_KEY absent
- Director scene plan: now includes `master_style`, `animate`, `motion_prompt`, `visual_source`, `search_query` per scene; `_validate_scene_plan` defaults all missing fields
- Director JSON robustness: `max_tokens=8192`; `_strip_markdown(text)` strips ` ``` ` / ` ```json ` fences; on `JSONDecodeError` tries `_repair_truncated_json` (brace counting) then `_repair_truncated_json_aggressive` (stack-based) before retrying Claude with brevity instruction
- Director scene limits: `_build_user_message` passes `max_scenes` to Claude based on duration (≤3 min→10, 3-5 min→12, >5 min→15); system prompt caps `visual_prompt` at 200 chars
- Runway animator: `musicvid/pipeline/video_animator.py` — `animate_image(image_path, motion_prompt, duration, output_path)` calls Runway Gen-4; model=`gen4.5`, ratio=`1280:720` (16:9); POLL_INTERVAL=3s, POLL_TIMEOUT=300s; cache check via output_path exists; mock target: `@patch("musicvid.pipeline.video_animator.requests")` + `@patch("musicvid.pipeline.video_animator.time")`; Runway Gen-4 returns `output` as a list of URL strings (not dicts) — `_poll_animation` handles both formats; test helper `_make_poll_response_str` simulates the string-list format
- Runway animation error tests: use `requests.exceptions.HTTPError` with `.response` mock (`status_code`, `text`) to test the Runway error detail output — these are in `test_visual_router.py` now, not `test_cli.py`
- CLI tests for `--animate` must mock `@patch("musicvid.musicvid.VisualRouter")` — animation is handled inside VisualRouter._route_animated(), not in cli() directly
- Assembler `_load_scene_clip`: skips Ken Burns for scenes with `animate=True` and `.mp4` suffix — just resizes to target_size
- Clip selector: `musicvid/pipeline/clip_selector.py` — `select_clip(analysis, clip_duration)` calls Claude API; manual 2-attempt retry loop with fallback to song center; mock target: `@patch("musicvid.pipeline.clip_selector.anthropic")`
- `--preset [full|social|all]` (default: "all"): preset mode — `full` generates YouTube 16:9 in `output/pelny/`, `social` generates 3 reels (9:16) from different sections in `output/social/`, `all` generates both. Stages 1-3 run once; stage 4 runs all variants in parallel (ThreadPoolExecutor). Uses `_run_preset_mode()` and `assemble_all_parallel()` in `musicvid.py`
- `--sequential-assembly`: disables Stage 4 parallelism (use on low-RAM Macs); `_run_preset_mode` falls back to sequential loop; single-job presets (`--preset full`) always run sequentially regardless of flag
- Parallel assembly: `AssemblyJob(name, kwargs)` dataclass collects per-variant args; `assemble_all_parallel(jobs, max_workers=4)` submits all via `ThreadPoolExecutor`; one job failure does not abort others; warns when system RAM < 16 GB (via `psutil`)
- CLI tests for parallel assembly must mock `@patch("musicvid.musicvid.assemble_all_parallel")` for multi-job presets (`--preset social`, `--preset all`) since `_run_preset_mode` no longer calls `assemble_video` directly in those paths
- `--lut-style [warm|cold|cinematic|natural|faded]` (default: warm): LUT color grade style — passed as `lut_style` kwarg to all `assemble_video` calls (assembler already supports it via `color_grade.py`); `_run_preset_mode` accepts `lut_style`/`lut_intensity` kwargs
- `--subtitle-style [fade|karaoke|none]` (default: karaoke): overrides `scene_plan["subtitle_style"]["animation"]` in `cli()` after Stage 2
- `--transitions [cut|auto]` (default: auto): if "cut", overrides all `scene["transition"]` in scene_plan after Stage 2
- `--beat-sync [off|auto]` (default: auto): if "auto", calls `_apply_beat_sync()` to snap interior scene boundaries to nearest beat position after Stage 2; helpers `_snap_to_nearest_beat`, `_apply_beat_sync` defined in `musicvid.py`
- `--yes`: skips interactive confirmation prompt (prompt only shown when `sys.stdin.isatty()` is True — auto-skipped in CliRunner tests)
- `--quick`: shortcut that sets mode=stock, preset=full, effects=none, animate=never, lut_style=None, transitions=cut, beat_sync=off
- `--economy`: shortcut that sets mode=ai, provider=flux-dev, preset=full, effects=minimal, animate=never, lut_style=warm
- API key fallbacks: checked early in `cli()` after --quick/--economy overrides — missing BFL_API_KEY falls back to mode=stock, missing RUNWAY_API_KEY falls back to animate=never, both with printed messages
- Startup summary: `_print_startup_summary()` called before pipeline stages; displays active settings in a formatted table; shows `Rolki social: 3 × {reel_duration}s z różnych fragmentów` line when preset is "social" or "all"
- `--reel-duration [15|20|25|30|45|60]` (default: 30): duration of social reels; invalidates social clips cache; for ≥30s reels, Claude prompt includes chorus/refrain priority rules
- Social clip selector: `musicvid/pipeline/social_clip_selector.py` — `select_social_clips(analysis, clip_duration)` asks Claude for 3 non-overlapping clips from different sections; mock: `@patch("musicvid.pipeline.social_clip_selector.anthropic")`
- CLI tests for `--preset` must mock `@patch("musicvid.musicvid.select_social_clips")` in addition to the usual pipeline mocks
- Scene plan/manifest clip filters: `_filter_scene_plan_to_clip(scene_plan, clip_start, clip_end)` and `_filter_manifest_to_clip(manifest, scenes, clip_start, clip_end)` in `musicvid.py` — filter and offset scenes/manifest entries to a clip time window
- Reel manifest validation: `find_nearest_scene(start, end, fetch_manifest)` and `_validate_clip_manifest(clip_manifest, full_manifest)` in `musicvid.py` — called in `_run_preset_mode` after `_filter_manifest_to_clip` to replace None/missing video_path entries with nearest valid fallback; entries with no fallback are dropped with `click.echo(WARN ...)`; fetch_manifest entries must include `start`/`end` keys for fallback to work (stock manifest has them; image manifest also carries them)
- Assembler social mode kwargs: `audio_fade_out=1.0` (social uses 1.5), `subtitle_margin_bottom=80` (social uses 200), `cinematic_bars=False` (default); standard/preset-full passes `cinematic_bars=(effects == "full")`, social explicitly passes `False`
- Ken Burns `pan_up`/`pan_down` motions added; `_remap_motion_for_portrait(motion)` maps horizontal pans to vertical for 9:16
- Ken Burns motions also include `diagonal_drift` (top-left → bottom-right pan) and `cut_zoom` (aggressive 1.0→1.25 zoom for chorus energy)
- Assembler `_concatenate_with_transitions(scene_clips, scenes, bpm, target_size)` replaces direct `concatenate_videoclips` in `assemble_video`; handles cut/cross_dissolve/fade/dip_white using `scene["transition_to_next"]`; mock target: `@patch("musicvid.pipeline.assembler._concatenate_with_transitions")`
- Dynamics post-processing in `cli()` after `_apply_beat_sync`: `_enforce_motion_variety(scenes)` (always, deduplicates adjacent same motions) → `_assign_dynamic_transitions(scenes, bpm)` (when `transitions_mode=="auto"`, sets `transition_to_next` per section pair); both mutate scenes list in-place
- `enforce_animation_rules(scenes)` called inside Stage 3 (mode=ai, after animate_mode overrides), not at the fixed post-dynamics location mentioned in old notes
- `--reels-style [crop|blur-bg]` (default: blur-bg): portrait conversion style — `blur-bg` creates blurred background + sharp smart crop overlay; `crop` does tighter POI-centered smart crop; passed as `reels_style` kwarg to `assemble_video` and all social AssemblyJobs
- Smart crop: `musicvid/pipeline/smart_crop.py` — `detect_poi(image_path) -> (x, y)` (Haar face detection → saliency map → center fallback); `smart_crop(image_path, target_w, target_h, poi=None) -> PIL.Image`; `blur_bg_composite(image_path, target_w, target_h) -> PIL.Image`; `convert_for_platform(image_path, platform, style) -> str` (saves to `smart_{stem}.jpg` alongside source)
- Assembler `_load_scene_clip` uses `convert_for_platform` for portrait images (target_size==(1080,1920)) before creating ImageClip; video files and landscape images bypass smart crop; mock target: `@patch("musicvid.pipeline.assembler.convert_for_platform")`
- cv2 import in `smart_crop.py` uses `try/except ImportError` fallback (cv2=None) so module loads even when opencv-python not installed; tests mock `@patch("musicvid.pipeline.smart_crop.cv2")`
- BFL image generator: `generate_images()` accepts `platform=None`; when `platform=="reels"`, uses 768×1360 (native 9:16) and `"portrait 9:16"` prompt hint instead of `"cinematic 16:9"`; `_submit_task()` accepts `width` and `height` params; `generate_single_image()` always uses 1360×768 + `"cinematic 16:9"` (landscape only)
- Clip analysis filter: `_filter_analysis_to_clip(analysis, clip_start, clip_end)` in `musicvid.py` — offsets lyrics/beats/sections to clip-relative t=0 before passing to director
- Lyrics parser: `musicvid/pipeline/lyrics_parser.py` — `merge_whisper_with_lyrics_file(whisper_segments, lyrics_lines, audio_duration)` for deterministic sync (3 cases: N==M 1:1, N>M groups segments, N<M splits time); `align_with_claude()` kept but not used in CLI; `parse()` for variant A (plain text) and B (MM:SS timestamps)
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
- BFL API payload: only `prompt`, `width`, `height` — no `output_format`, `safety_tolerance`, or `prompt_upsampling`; landscape uses 1360x768 (1280x720 causes 422 from flux-dev); portrait (reels) uses 768x1360
- BFL prompts: `DOCUMENTARY_SUFFIX` and `NEGATIVE_CONTEXT` constants in `image_generator.py` are appended to every BFL prompt; they replace the old "photorealistic, high quality" suffix
- Director prompt bans two categories of words: Catholic imagery terms AND photographic AI-fantasy terms (magical, HDR, 8K, ethereal, oversaturated, etc.) — both in `musicvid/prompts/director_system.txt`
- `apply_subtle_film_look(clip)` in `effects.py`: pure-numpy luminance-weighted 8% desaturation + sigma=4/opacity=0.08 grain; called from `apply_effects` for "minimal" and "full" levels (not "none")
- Banned-words test in `test_image_generator.py` uses word-boundary regex `r'\b(?<!no )(?<!no\s)' + re.escape(word) + r'\b'` to allow negation phrases like "no Catholic imagery" while still catching affirmative uses
- Image generator polling tests mock `time.monotonic` and `time.sleep` to control timing
- Image generator retry tests must patch tenacity wait to `wait_none()` to avoid slow tests
- AI lyrics alignment: `align_with_claude` in `lyrics_parser.py` mocks `anthropic` at module level: `@patch("musicvid.pipeline.lyrics_parser.anthropic")`; uses manual retry loop (2 attempts) instead of tenacity
- CLI tests with `--lyrics` must mock `@patch("musicvid.musicvid.merge_whisper_with_lyrics_file")` (deterministic, no API call)
- Lyrics timing corrections order: min/max duration (0.8s/8s) → 0.15s gap → −0.05s pre-display offset (clamped to 0) → clamp to audio_duration; effective post-offset gap is ~0.10s minimum
- Font loader: `musicvid/pipeline/font_loader.py` auto-downloads Montserrat-Light.ttf directly from GitHub as TTF, falls back to system DejaVuSans
- CLI tests that run the full pipeline must mock `get_font_path` via `@patch("musicvid.musicvid.get_font_path", return_value="/fake/font.ttf")`
- Assembler tests must mock effects imports: `@patch("musicvid.pipeline.assembler.apply_effects")`, `@patch("musicvid.pipeline.assembler.create_cinematic_bars")`, `@patch("musicvid.pipeline.assembler.create_light_leak")`
- Assembler clip mode tests must also mock `@patch("musicvid.pipeline.assembler.afx")` and `@patch("musicvid.pipeline.assembler.ColorClip")` to test fades and title card
- Assembler `assemble_video` accepts `clip_start`, `clip_end`, `title_card_text` kwargs; audio trimmed via `audio.subclipped(clip_start, clip_end)` + `afx.AudioFadeIn/AudioFadeOut`; video via `vfx.FadeIn/FadeOut`
- Assembler `RESOLUTION_MAP` includes `"portrait": (1080, 1920)` for social media clips
- CLI tests for `--clip` must mock `@patch("musicvid.musicvid.select_clip")` in addition to the usual pipeline mocks
- CLI tests MUST pass `--mode stock` and `--preset full` explicitly — defaults are now "ai" and "all"; omitting them will hit the real BFL API causing 402 Payment Required errors
- Effects per-frame transforms use `clip.transform(fn)` where `fn(get_frame, t)` returns numpy array; test by extracting transform_fn from `mock_clip.transform.call_args[0][0]`
- `_create_ken_burns_clip` test mocks need `mock_clip.size=(w,h)`, `mock_clip.w=w`, `mock_clip.h=h`, `mock_clip.cropped.return_value=mock_clip` — omitting breaks the mock chain since `cropped()` returns an unconfigured auto-MagicMock
- MoviePy 2.x cover-scale: `scale = max(tw/iw, th/ih); clip = clip.resized(scale); clip = clip.cropped(x1=x1, y1=y1, x2=x1+tw, y2=y1+th)` — scalar for proportional resize, explicit pixel coords for crop
- `_create_subtitle_clips` has try/except around `TextClip` creation — silently skips failed segments; logs each lyric line; falls back to `font=None` if named font fails; accepts `sections=None` kwarg — when provided, looks up per-lyric font size via `_get_section_for_time`; `_SECTION_FONT_SIZES`: chorus=64, verse=54, bridge=48, intro=50, outro=46; `assemble_video` passes `analysis.get("sections")`
- Subtitle descender fix: `TextClip` height is set to `font_size + int(font_size * 0.35)` (35% pad) so j/g/y/p/q/ą/ę aren't clipped; `y_pos` is adjusted so padded clip bottom lands at `margin_bottom` from frame bottom; test count is now 308
- Subtitle pre-display offset: `_create_subtitle_clips` applies `-0.1s` to `segment["start"]` (clamped to 0) and extends duration — so subtitles appear before the word
- Subtitle timing: `with_start(segment["start"])` uses **global** absolute timestamps, composited over the full concatenated video — correct; do NOT subtract `scene["start"]`
- Subtitle clip tests need `@patch("musicvid.pipeline.assembler.vfx")` alongside `TextClip` — `with_effects([vfx.CrossFadeIn(...)])` uses module-level vfx import
- `--new` flag uses `shutil.rmtree(cache_dir)` — deletes entire cache dir including scene_NNN.jpg and animated_scene_NNN.mp4; no partial-clear needed
- Beat sync helpers in `musicvid.py`: `_compute_downbeats(beats)` (every 4th beat via `beats[::4]`), `_snap_to_downbeat(t, downbeats, window=0.5)` (snap only within ±0.5s); `_apply_beat_sync` uses downbeats not all beats
- Director `_build_user_message` includes BPM, bar_duration, suggested_scene_count (`max(4, int(duration/(bar_duration*4)))`), downbeats preview; `_validate_scene_plan` defaults `lyrics_in_scene=[]` per scene
- `enforce_animation_rules(scenes)` and `get_section_priority(section)` defined in `musicvid/musicvid.py` before `@click.command()`; enforces: no adjacent animated, max 25% (`max(1, N//4)`), no outro, no scenes <6s; called only when `animate_mode=="auto"` after animate overrides (~line 566)
- CLI tests with `animate_mode="auto"` and short scenes (<6s) need `@patch("musicvid.musicvid.enforce_animation_rules", side_effect=lambda s: s)` or the function silently disables those scenes
- `enforce_animation_rules` tests expecting 2+ animated scenes to survive must use ≥8 total scenes — with fewer, `max(1, N//4)` trims to 1 causing unexpected failures
- Use `python3` not `python` on this macOS system

## Environment
- macOS, Python 3.14, requires `ffmpeg` and `imagemagick` via Homebrew
- API keys: ANTHROPIC_API_KEY, PEXELS_API_KEY, BFL_API_KEY, RUNWAY_API_KEY (optional, for --animate) in `.env`
- `cairosvg` required for SVG logo files (optional dependency, only needed when `--logo` points to .svg)
