"""MusicVid CLI — Christian Music Video Generator."""

import hashlib
import os
import shutil
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import click
import psutil
from dotenv import load_dotenv

from musicvid.pipeline.audio_analyzer import analyze_audio
from musicvid.pipeline.cache import get_audio_hash, load_cache, save_cache
from musicvid.pipeline.clip_selector import select_clip
from musicvid.pipeline.director import create_scene_plan
from musicvid.pipeline.stock_fetcher import fetch_videos
from musicvid.pipeline.image_generator import generate_images
from musicvid.pipeline.assembler import assemble_video
from musicvid.pipeline.font_loader import get_font_path
from musicvid.pipeline.lyrics_parser import merge_whisper_with_lyrics_file
from musicvid.pipeline.video_animator import animate_image
from musicvid.pipeline.social_clip_selector import select_social_clips
from musicvid.pipeline.visual_router import VisualRouter
from musicvid.pipeline.assembler import _remap_motion_for_portrait


load_dotenv()


def _video_files_exist(manifest):
    """Check that all video files referenced in the manifest exist on disk."""
    return all(Path(entry["video_path"]).exists() for entry in manifest)


def _image_files_exist(manifest):
    """Check that all image files referenced in the manifest exist on disk."""
    return all(Path(entry["video_path"]).exists() for entry in manifest)


def _filter_analysis_to_clip(analysis, clip_start, clip_end):
    """Return a copy of analysis restricted to the [clip_start, clip_end] window.

    Lyrics, beats, and section times are offset by clip_start so they start at t=0.
    """
    clip_duration = clip_end - clip_start

    lyrics = [
        {**seg, "start": seg["start"] - clip_start, "end": seg["end"] - clip_start}
        for seg in analysis.get("lyrics", [])
        if seg["start"] >= clip_start - 0.1 and seg["end"] <= clip_end + 0.1
    ]

    sections = [
        {
            **sec,
            "start": max(0.0, sec["start"] - clip_start),
            "end": min(clip_duration, sec["end"] - clip_start),
        }
        for sec in analysis.get("sections", [])
        if sec["start"] < clip_end and sec["end"] > clip_start
    ]

    beats = [
        b - clip_start
        for b in analysis.get("beats", [])
        if clip_start <= b <= clip_end
    ]

    return {
        **analysis,
        "lyrics": lyrics,
        "sections": sections,
        "beats": beats,
        "duration": clip_duration,
    }


def _filter_scene_plan_to_clip(scene_plan, clip_start, clip_end):
    """Return a copy of scene_plan with scenes filtered and offset to the clip window.

    Scenes that don't overlap [clip_start, clip_end] are dropped.
    Overlapping scenes are trimmed to the window and offset so clip_start becomes t=0.
    """
    filtered_scenes = []
    for scene in scene_plan["scenes"]:
        if scene["end"] <= clip_start or scene["start"] >= clip_end:
            continue
        trimmed = {
            **scene,
            "start": max(0.0, scene["start"] - clip_start),
            "end": min(clip_end - clip_start, scene["end"] - clip_start),
        }
        filtered_scenes.append(trimmed)

    return {**scene_plan, "scenes": filtered_scenes}


def _filter_manifest_to_clip(manifest, scenes, clip_start, clip_end):
    """Return manifest entries for scenes that overlap the clip window, with reindexed scene_index."""
    overlapping_indices = set()
    for i, scene in enumerate(scenes):
        if scene["end"] > clip_start and scene["start"] < clip_end:
            overlapping_indices.add(i)

    filtered = []
    new_idx = 0
    for entry in manifest:
        if entry["scene_index"] in overlapping_indices:
            filtered.append({**entry, "scene_index": new_idx})
            new_idx += 1

    return filtered


def find_nearest_scene(start, end, fetch_manifest):
    """Return the fetch_manifest entry whose time range best overlaps [start, end].

    Skips entries where video_path is None or the file doesn't exist.
    When no overlap exists, falls back to the entry whose scene center is closest
    to the clip center. As a last resort, returns the first entry with a non-None
    video_path (ignoring file existence). Returns None only if every entry has
    video_path=None.
    """
    clip_center = (start + end) / 2
    best = None
    best_overlap = -1
    best_center_dist = float("inf")

    for entry in fetch_manifest:
        if not entry.get("video_path"):
            continue
        if not os.path.exists(entry["video_path"]):
            continue
        scene_start = entry.get("start", 0)
        scene_end = entry.get("end", 0)
        overlap = min(end, scene_end) - max(start, scene_start)
        if overlap > best_overlap:
            best_overlap = overlap
            best = entry
        elif overlap <= 0 and best_overlap <= 0:
            center_dist = abs((scene_start + scene_end) / 2 - clip_center)
            if center_dist < best_center_dist:
                best_center_dist = center_dist
                best = entry

    if best is not None:
        return best

    # Last resort: first entry with non-None video_path (file may not exist yet)
    for entry in fetch_manifest:
        if entry.get("video_path"):
            return entry

    return None


def _validate_clip_manifest(clip_manifest, full_manifest):
    """Return a copy of clip_manifest with None/missing video_path entries replaced.

    For each entry whose video_path is None or points to a non-existent file,
    find_nearest_scene is used to locate the closest valid entry in full_manifest.
    Entries with no fallback are dropped with a warning.
    The original scene_index is preserved in the replacement entry.
    """
    validated = []
    for entry in clip_manifest:
        path = entry.get("video_path")
        if path and os.path.exists(path):
            validated.append(entry)
            continue
        # Invalid path — find nearest fallback
        start = entry.get("start", 0)
        end = entry.get("end", 0)
        fallback = find_nearest_scene(start, end, full_manifest)
        if fallback is None:
            click.echo(
                f"  WARN: brak video_path dla sceny {entry.get('scene_index')} "
                f"(start={start:.1f}s end={end:.1f}s) — pomijam scenę"
            )
            continue
        click.echo(
            f"  WARN: video_path dla sceny {entry.get('scene_index')} "
            f"jest None/brak — używam sceny {fallback.get('scene_index')} jako zastępstwa"
        )
        validated.append({**entry, "video_path": fallback["video_path"]})
    return validated


@dataclass
class AssemblyJob:
    name: str          # e.g. "youtube", "rolka_A_15s"
    kwargs: dict = field(default_factory=dict)


def assemble_all_parallel(jobs, max_workers=4):
    """Run multiple assemble_video calls in parallel.

    Warns when system RAM < 16 GB since each FFmpeg process uses ~2 GB.
    Returns list of output_path strings for successful jobs.
    A failing job is logged but does not abort remaining jobs.
    """
    RAM_THRESHOLD_BYTES = 16 * 1024 ** 3
    total_ram = psutil.virtual_memory().total
    if total_ram < RAM_THRESHOLD_BYTES:
        ram_gb = total_ram / 1024 ** 3
        click.echo(
            f"  \u26a0\ufe0f  Uwaga: r\u00f3wnoleg\u0142y monta\u017c wymaga ~8GB RAM "
            f"(wykryto {ram_gb:.0f}GB). "
            f"Je\u015bli Mac zwalnia u\u017cyj --sequential-assembly"
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
                click.echo(f"  \u2705 Gotowe: {job.name}")
            except Exception as exc:
                click.echo(f"  \u274c B\u0142\u0105d: {job.name} \u2014 {exc}")
    return results


def _compute_downbeats(beats):
    """Return every 4th beat (downbeat) from the beats list."""
    return beats[::4]


def _snap_to_downbeat(t, downbeats, window=0.5):
    """Snap t to the nearest downbeat within window seconds; return t unchanged if none qualifies."""
    candidates = [d for d in downbeats if abs(d - t) <= window]
    if not candidates:
        return t
    return min(candidates, key=lambda d: abs(d - t))


def _snap_to_nearest_beat(t, beats):
    """Return the beat timestamp closest to t (kept for backward compat)."""
    if not beats:
        return t
    return min(beats, key=lambda b: abs(b - t))


def _apply_beat_sync(scene_plan, beats):
    """Snap interior scene boundaries to nearest downbeat within ±0.5s.

    First scene start stays 0.0; last scene end stays as-is.
    Adjacent scenes share the same snapped boundary (no gaps).
    Falls back to unsnapped boundary if no downbeat is within 0.5s.
    """
    scenes = scene_plan["scenes"]
    if not scenes or not beats:
        return scene_plan
    downbeats = _compute_downbeats(beats)
    for i in range(len(scenes) - 1):
        snapped = _snap_to_downbeat(scenes[i]["end"], downbeats)
        scenes[i]["end"] = snapped
        scenes[i + 1]["start"] = snapped
    return scene_plan


def _print_startup_summary(mode, provider, preset, effects, animate_mode, lut_style,
                            lut_intensity, subtitle_style_override, transitions_mode,
                            beat_sync, reel_duration):
    """Print a human-readable summary of the active generation settings."""
    if mode == "runway":
        images_desc = "Runway Gen-4.5 AI video + Pexels przyroda"
    elif mode == "ai":
        images_desc = f"BFL {provider.upper()} (AI)"
    else:
        images_desc = "Pexels (stock)"
    animate_desc = "Runway Gen-4 (auto)" if animate_mode == "auto" else (
        "Runway Gen-4 (wszystkie)" if animate_mode == "always" else "wyłączone (Ken Burns)"
    )
    preset_desc = {"full": "Pełny teledysk", "social": "3 rolki", "all": "Pełny teledysk + 3 rolki"}.get(preset or "full", preset)
    lut_desc = f"LUT {lut_style} (intensity {lut_intensity})" if lut_style else "brak"
    click.echo("  MusicVid — tryb pełny")
    click.echo("  " + "━" * 38)
    click.echo(f"  Obrazy:      {images_desc}")
    click.echo(f"  Animacje:    {animate_desc}")
    click.echo(f"  Preset:      {preset_desc}")
    if preset in ("social", "all"):
        click.echo(f"  Rolki social:   3 × {reel_duration}s z różnych fragmentów")
    click.echo(f"  Efekty:      {effects}")
    click.echo(f"  Napisy:      {subtitle_style_override} style")
    click.echo(f"  Przejścia:   {transitions_mode}")
    click.echo(f"  Color grade: {lut_desc}")
    click.echo(f"  Beat sync:   {beat_sync}")
    click.echo("  " + "━" * 38)


def get_section_priority(section: str) -> int:
    """Return animation priority for a section type. Higher = more important."""
    return {"chorus": 5, "bridge": 4, "verse": 3, "intro": 2, "outro": 0}.get(section, 1)


def enforce_animation_rules(scenes: list) -> list:
    """Enforce animation placement rules on director's scene plan.

    Rules applied in order:
    1. Disable short scenes (< 3s) — Runway minimum
    2. Disable outro scenes — should always be calm
    3. Fix adjacency — no two animated scenes side by side (lower priority loses)
    4. Enforce max 25% animated (max(1, total//4)), keeping highest priority
    5. Print animation plan summary
    """
    # Rule 1: short scenes and outro
    for scene in scenes:
        if scene.get("animate"):
            duration = scene["end"] - scene["start"]
            if duration < 3.0:
                scene["animate"] = False
                print(
                    f"WARN: Scena {scene['section']} za krótka"
                    f" ({duration:.1f}s) — Ken Burns fallback"
                )
            elif scene["section"] == "outro":
                scene["animate"] = False

    # Rule 2: adjacency — iterate forward, disable lower-priority neighbour
    for i in range(len(scenes) - 1):
        if scenes[i].get("animate") and scenes[i + 1].get("animate"):
            p_i = get_section_priority(scenes[i]["section"])
            p_next = get_section_priority(scenes[i + 1]["section"])
            if p_i >= p_next:
                scenes[i + 1]["animate"] = False
            else:
                scenes[i]["animate"] = False

    # Rule 3: max animated = max(1, total // 4)
    animated_indices = [i for i, s in enumerate(scenes) if s.get("animate")]
    max_animated = max(1, len(scenes) // 4)
    if len(animated_indices) > max_animated:
        # Sort by priority descending, keep top max_animated
        animated_indices.sort(key=lambda i: get_section_priority(scenes[i]["section"]), reverse=True)
        for idx in animated_indices[max_animated:]:
            scenes[idx]["animate"] = False

    # Rule 4: print summary
    animated = [i for i, s in enumerate(scenes) if s.get("animate")]
    print(f"Plan animacji Runway: {len(animated)} scen z {len(scenes)}")
    for i in animated:
        s = scenes[i]
        print(f"  Scena {i}: {s['section']} @ {s['start']:.1f}-{s['end']:.1f}s")

    return scenes


_MOTION_MAP = {
    "intro":  ["static", "slow_zoom_in", "pan_right"],
    "verse":  ["slow_zoom_in", "slow_zoom_out", "pan_left", "pan_right"],
    "chorus": ["cut_zoom", "slow_zoom_in", "pan_left", "pan_right"],
    "bridge": ["slow_zoom_out", "static", "diagonal_drift"],
    "outro":  ["slow_zoom_out", "static"],
}
_DEFAULT_MOTIONS = ["slow_zoom_in", "slow_zoom_out", "pan_left", "pan_right", "static"]


def _enforce_motion_variety(scenes):
    """Ensure no two adjacent scenes have the same motion type.

    For each scene that matches the previous one, picks the first allowed motion
    from the section map that differs from the previous scene's motion.
    Mutates and returns the list.
    """
    for i in range(1, len(scenes)):
        if scenes[i].get("motion") == scenes[i - 1].get("motion"):
            section = scenes[i].get("section", "verse")
            allowed = _MOTION_MAP.get(section, _DEFAULT_MOTIONS)
            prev_motion = scenes[i - 1].get("motion")
            alternatives = [m for m in allowed if m != prev_motion]
            if alternatives:
                scenes[i]["motion"] = alternatives[0]
    return scenes


_TRANSITIONS_MAP = {
    ("intro", "verse"):   "cross_dissolve",
    ("verse", "chorus"):  "cut",
    ("chorus", "verse"):  "fade",
    ("chorus", "chorus"): "dip_white",
    ("verse", "verse"):   "cross_dissolve",
    ("verse", "bridge"):  "cross_dissolve",
    ("bridge", "chorus"): "cut",
    ("chorus", "outro"):  "fade",
    ("outro", "outro"):   "cross_dissolve",
}
_DEFAULT_TRANSITION = "cross_dissolve"


def _assign_dynamic_transitions(scenes, bpm):
    """Assign transition_to_next on each scene (except the last) based on section pairs.

    Does not affect the last scene. Returns mutated scenes list.
    """
    for i in range(len(scenes) - 1):
        key = (scenes[i].get("section", ""), scenes[i + 1].get("section", ""))
        scenes[i]["transition_to_next"] = _TRANSITIONS_MAP.get(key, _DEFAULT_TRANSITION)
    return scenes


_STYLE_TO_LUT = {
    "worship": "warm",
    "contemplative": "cinematic",
    "powerful": "cold",
    "joyful": "natural",
}


def _lut_for_style(overall_style):
    """Return LUT style name for a given director overall_style."""
    return _STYLE_TO_LUT.get(overall_style, "warm")


@click.command()
@click.argument("audio_file", type=click.Path(exists=True))
@click.option("--mode", type=click.Choice(["stock", "ai", "runway", "hybrid"]), default="runway", help="Video source mode.")
@click.option("--provider", type=click.Choice(["flux-dev", "flux-pro", "flux-schnell"]), default="flux-pro", help="Image provider for --mode ai.")
@click.option("--style", type=click.Choice(["auto", "contemplative", "joyful", "worship", "powerful"]), default="auto", help="Visual style.")
@click.option("--output", type=click.Path(), default="./output/", help="Output directory.")
@click.option("--resolution", type=click.Choice(["720p", "1080p", "4k"]), default="1080p", help="Output resolution.")
@click.option("--lang", default="auto", help="Language for transcription.")
@click.option("--new", is_flag=True, default=False, help="Force recalculation, ignore cache.")
@click.option("--font", "font_path", type=click.Path(), default=None, help="Custom .ttf font file for subtitles.")
@click.option("--lyrics", "lyrics_path", type=click.Path(), default=None, help="Path to .txt lyrics file (skips Whisper).")
@click.option("--effects", type=click.Choice(["none", "minimal", "full"]), default="minimal", help="Visual effects level.")
@click.option("--clip", "clip_duration", type=click.Choice(["15", "20", "25", "30"]), default=None, help="Clip duration in seconds for social media (selects best fragment).")
@click.option("--platform", type=click.Choice(["reels", "shorts", "tiktok"]), default=None, help="Social media platform (sets portrait 9:16 resolution).")
@click.option("--title-card", is_flag=True, default=False, help="Add 2-second title card with song name at start of clip.")
@click.option("--animate", "animate_mode", type=click.Choice(["auto", "always", "never"]), default="auto", help="Animated video via Runway Gen-4.")
@click.option("--preset", type=click.Choice(["full", "social", "all"]), default="all", help="Preset mode: full (YouTube), social (3 reels), all (both).")
@click.option("--reel-duration", type=click.Choice(["15", "20", "25", "30", "45", "60"]), default="30", help="Duration of social media reels in seconds.")
@click.option("--logo", "logo_path", type=click.Path(), default=None, help="Path to logo file (SVG/PNG) to overlay on video.")
@click.option("--logo-position", type=click.Choice(["top-left", "top-right", "bottom-left", "bottom-right"]), default="top-left", help="Logo position on screen.")
@click.option("--logo-size", type=int, default=None, help="Logo width in pixels (default: auto 12%% of frame width).")
@click.option("--logo-opacity", type=float, default=0.85, help="Logo opacity 0.0-1.0.")
@click.option("--lut-style", type=click.Choice(["warm", "cold", "cinematic", "natural", "faded"]), default=None, help="Built-in LUT color grade style.")
@click.option("--lut-intensity", type=float, default=0.85, help="LUT intensity 0.0-1.0.")
@click.option("--subtitle-style", "subtitle_style_override", type=click.Choice(["fade", "karaoke", "none"]), default="karaoke", help="Subtitle animation style.")
@click.option("--transitions", "transitions_mode", type=click.Choice(["cut", "auto"]), default="auto", help="Scene transition style (auto: director decides, cut: force hard cuts).")
@click.option("--beat-sync", "beat_sync", type=click.Choice(["off", "auto"]), default="auto", help="Align scene cuts to beat positions.")
@click.option("--yes", "skip_confirm", is_flag=True, default=False, help="Skip confirmation prompt.")
@click.option("--quick", "quick_mode", is_flag=True, default=False, help="Quick mode: stock images, no animation, cut transitions, no LUT.")
@click.option("--economy", "economy_mode", is_flag=True, default=False, help="Economy mode: flux-dev AI images, no Runway animation, warm LUT.")
@click.option("--wow/--no-wow", "wow_effects", default=True, help="Enable WOW effects (zoom punch, light flash, reactive color grade). Active when --effects minimal or full.")
@click.option("--zoom-punch/--no-zoom-punch", "wow_zoom_punch", default=True, help="Zoom punch on chorus downbeats.")
@click.option("--light-flash/--no-light-flash", "wow_light_flash", default=True, help="Light flash on chorus entry.")
@click.option("--dynamic-grade/--no-dynamic-grade", "wow_dynamic_grade", default=True, help="Reactive color grade (verse vs chorus palettes).")
@click.option("--particles/--no-particles", "wow_particles", default=False, help="Particle overlay on AI/animated clips (expensive).")
@click.option("--sequential-assembly", is_flag=True, default=False,
              help="Disable parallel Stage 4 assembly (use on low-RAM Macs)")
@click.option("--reels-style", "reels_style", type=click.Choice(["crop", "blur-bg"]), default="blur-bg", help="Portrait conversion style for social reels: blur-bg (blurred background) or crop (smart crop).")
def cli(audio_file, mode, provider, style, output, resolution, lang, new, font_path, lyrics_path,
        effects, clip_duration, platform, title_card, animate_mode, preset, reel_duration,
        logo_path, logo_position, logo_size, logo_opacity,
        lut_style, lut_intensity, subtitle_style_override, transitions_mode, beat_sync,
        skip_confirm, quick_mode, economy_mode, sequential_assembly, reels_style,
        wow_effects, wow_zoom_punch, wow_light_flash, wow_dynamic_grade, wow_particles):
    """Generate a music video from AUDIO_FILE."""
    # Apply --quick mode overrides
    if quick_mode:
        mode = "stock"
        preset = "full"
        effects = "none"
        animate_mode = "never"
        lut_style = None
        transitions_mode = "cut"
        beat_sync = "off"
        wow_effects = False

    # Apply --economy mode overrides
    if economy_mode:
        mode = "ai"
        provider = "flux-dev"
        preset = "full"
        effects = "minimal"
        animate_mode = "never"
        lut_style = "warm"
        transitions_mode = "auto"
        beat_sync = "auto"

    # API key fallbacks
    if mode == "ai" and not os.environ.get("BFL_API_KEY"):
        click.echo(
            "Brak BFL_API_KEY — przełączam na tryb stock (Pexels).\n"
            "Aby używać AI obrazów: dodaj BFL_API_KEY do .env\n"
            "Rejestracja: https://bfl.ai/dashboard"
        )
        mode = "stock"

    if animate_mode in ("auto", "always") and not os.environ.get("RUNWAY_API_KEY"):
        click.echo(
            "Brak RUNWAY_API_KEY — animacje wyłączone (Ken Burns zamiast Runway).\n"
            "Aby używać Runway: dodaj RUNWAY_API_KEY do .env\n"
            "Rejestracja: https://app.runwayml.com"
        )
        animate_mode = "never"

    # Build wow_config: only active when effects level is not "none" AND --wow flag set
    wow_config = None
    if wow_effects and effects != "none":
        from musicvid.pipeline.wow_effects import default_wow_config
        wow_config = default_wow_config()
        wow_config["zoom_punch"] = wow_zoom_punch
        wow_config["light_flash"] = wow_light_flash
        wow_config["dynamic_grade"] = wow_dynamic_grade
        wow_config["particles"] = wow_particles

    _print_startup_summary(mode, provider, preset, effects, animate_mode, lut_style,
                           lut_intensity, subtitle_style_override, transitions_mode,
                           beat_sync, reel_duration)

    import sys
    if not skip_confirm and sys.stdin.isatty():
        if not click.confirm("  Kontynuować?", default=True):
            raise SystemExit(0)

    audio_path = Path(audio_file).resolve()
    output_dir = Path(output).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    audio_hash = get_audio_hash(str(audio_path))
    cache_dir = output_dir / "tmp" / audio_hash
    cache_dir.mkdir(parents=True, exist_ok=True)

    if new and cache_dir.exists():
        shutil.rmtree(cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)

    # Resolve lyrics file (explicit flag or auto-detection)
    lyrics_file = None
    txt_files_in_dir = sorted(audio_path.parent.glob("*.txt"))

    if lyrics_path:
        lyrics_file = Path(lyrics_path).resolve()
        if not lyrics_file.exists():
            raise click.BadParameter(f"Lyrics file not found: {lyrics_file}", param_hint="--lyrics")
    elif len(txt_files_in_dir) == 1:
        lyrics_file = txt_files_in_dir[0]
    elif len(txt_files_in_dir) > 1:
        click.echo("  \u26a0 Znaleziono wiele plik\u00f3w .txt \u2014 u\u017cyj --lyrics aby wybra\u0107")

    # Compute lyrics hash for cache invalidation
    lyrics_hash = None
    if lyrics_file:
        with open(lyrics_file, "rb") as f:
            lyrics_hash = hashlib.md5(f.read()).hexdigest()[:12]

    # Stage 1: Analyze Audio
    analysis_cache_name = f"audio_analysis_{lyrics_hash}.json" if lyrics_hash else "audio_analysis.json"
    analysis = load_cache(str(cache_dir), analysis_cache_name) if not new else None
    if analysis:
        click.echo("[1/4] Audio analysis... CACHED (skipped)")
    else:
        click.echo("[1/4] Analyzing audio...")
        analysis = analyze_audio(str(audio_path), output_dir=str(cache_dir))
        save_cache(str(cache_dir), analysis_cache_name, analysis)
    # Replace lyrics using deterministic alignment if lyrics file available
    if lyrics_file:
        aligned_cache_name = f"lyrics_aligned_{lyrics_hash}.json"
        aligned = load_cache(str(cache_dir), aligned_cache_name) if not new else None
        if aligned:
            analysis["lyrics"] = aligned
            line_count = len(aligned)
            click.echo(f"[1/4] Tekst: dopasowanie... CACHED ({line_count} linii)")
        else:
            with open(lyrics_file, "r", encoding="utf-8") as f:
                raw = f.read()
            file_lines = [l.strip() for l in raw.split("\n") if l.strip()]
            aligned = merge_whisper_with_lyrics_file(
                analysis["lyrics"], file_lines, analysis["duration"]
            )
            save_cache(str(cache_dir), aligned_cache_name, aligned)
            analysis["lyrics"] = aligned
            line_count = len(file_lines)
            click.echo(f"[1/4] Tekst: Whisper timing + dopasowanie tekstu z pliku ({line_count} linii)")

    click.echo(f"  BPM: {analysis['bpm']}, Duration: {analysis['duration']}s, "
               f"Sections: {len(analysis['sections'])}, Mood: {analysis['mood_energy']}")

    # Clip selection (between Stage 1 and Stage 2)
    clip_start = None
    clip_end = None
    if clip_duration is not None:
        clip_secs = int(clip_duration)
        clip_cache_name = f"clip_{clip_secs}s.json"
        clip_info = load_cache(str(cache_dir), clip_cache_name) if not new else None
        if clip_info:
            click.echo(f"[clip] Clip selection ({clip_secs}s)... CACHED (skipped)")
        else:
            click.echo(f"[clip] Selecting best {clip_secs}s fragment...")
            clip_info = select_clip(analysis, clip_secs)
            save_cache(str(cache_dir), clip_cache_name, clip_info)
        clip_start = clip_info["start"]
        clip_end = clip_info["end"]
        click.echo(f"  Clip: {clip_start:.1f}s\u2013{clip_end:.1f}s \u2014 {clip_info.get('reason', '')}")
        analysis = _filter_analysis_to_clip(analysis, clip_start, clip_end)

    # Determine resolution (platform overrides --resolution)
    effective_resolution = "portrait" if platform else resolution

    # Stage 2: Direct Scenes
    style_override = style if style != "auto" else None
    scene_cache_name = f"scene_plan_clip_{clip_duration}s.json" if clip_duration else "scene_plan.json"
    scene_plan = load_cache(str(cache_dir), scene_cache_name) if not new else None
    if scene_plan:
        click.echo("[2/4] Scene planning... CACHED (skipped)")
    else:
        click.echo("[2/4] Creating scene plan...")
        scene_plan = create_scene_plan(analysis, style_override=style_override, output_dir=str(cache_dir), mode=mode)
        save_cache(str(cache_dir), scene_cache_name, scene_plan)
    click.echo(f"  Style: {scene_plan['overall_style']}, Scenes: {len(scene_plan['scenes'])}")

    # Auto-select LUT from overall_style if not explicitly set by user
    if lut_style is None and not quick_mode:
        lut_style = _lut_for_style(scene_plan.get("overall_style", "worship"))
        click.echo(f"  Auto LUT: {lut_style} (styl: {scene_plan.get('overall_style')})")

    # Override transitions if --transitions cut
    if transitions_mode == "cut":
        for scene in scene_plan["scenes"]:
            scene["transition"] = "cut"

    # Override subtitle animation style
    if subtitle_style_override:
        if "subtitle_style" not in scene_plan:
            scene_plan["subtitle_style"] = {}
        scene_plan["subtitle_style"]["animation"] = subtitle_style_override

    # Snap scene cuts to beat positions if --beat-sync auto
    if beat_sync == "auto":
        scene_plan = _apply_beat_sync(scene_plan, analysis.get("beats", []))

    # Enforce motion variety: no two adjacent scenes with same motion
    scene_plan["scenes"] = _enforce_motion_variety(scene_plan["scenes"])

    # Assign section-based transitions (only when --transitions auto)
    if transitions_mode == "auto":
        bpm = analysis.get("bpm", 120.0)
        _assign_dynamic_transitions(scene_plan["scenes"], bpm)

    # Stage 3: Fetch Videos or Generate Images
    manifest_suffix = f"_clip_{clip_duration}s" if clip_duration else ""
    if mode in ("ai", "runway"):
        image_cache_name = f"image_manifest{manifest_suffix}.json"
        image_manifest = load_cache(str(cache_dir), image_cache_name) if not new else None
        if image_manifest and _image_files_exist(image_manifest):
            click.echo("[3/4] Generating assets... CACHED (skipped)")
            fetch_manifest = image_manifest
        else:
            # Apply --animate overrides to visual_source before routing
            scenes = scene_plan["scenes"]
            if animate_mode == "always":
                for scene in scenes:
                    if scene.get("visual_source") in ("TYPE_AI", "TYPE_VIDEO_STOCK", "TYPE_PHOTO_STOCK"):
                        scene["visual_source"] = "TYPE_ANIMATED"
                    if not scene.get("motion_prompt"):
                        scene["motion_prompt"] = "Slow camera push forward, gentle atmospheric movement"
                scenes = enforce_animation_rules(scenes)
            elif animate_mode == "never":
                for scene in scenes:
                    if scene.get("visual_source") == "TYPE_ANIMATED":
                        scene["visual_source"] = "TYPE_AI"
            elif animate_mode == "auto":
                scenes = enforce_animation_rules(scenes)
            scene_plan["scenes"] = scenes

            click.echo(f"[3/4] Generating assets (provider: {provider})...")
            router = VisualRouter(cache_dir=str(cache_dir), provider=provider)
            fetch_manifest = []
            for i, scene in enumerate(scene_plan["scenes"]):
                scene["index"] = i
                src = scene.get("visual_source", "TYPE_AI")
                query = scene.get("search_query", "")
                prompt_preview = (scene.get("visual_prompt") or "")[:50]
                detail = f"query: {query}" if query else f"prompt: {prompt_preview}"
                total = len(scene_plan["scenes"])
                click.echo(f"  [{i + 1}/{total}] {scene['section']} | {src} | {detail}")
                asset_path = router.route(scene)
                if asset_path is None:
                    from musicvid.pipeline.stock_fetcher import _create_placeholder_video
                    placeholder_dest = cache_dir / f"scene_{i:03d}"
                    asset_path = _create_placeholder_video(placeholder_dest, scene)
                fetch_manifest.append({
                    "scene_index": i,
                    "video_path": asset_path,
                    "start": scene["start"],
                    "end": scene["end"],
                    "source": src,
                })
            save_cache(str(cache_dir), image_cache_name, fetch_manifest)
        click.echo(f"  Assets: {len(fetch_manifest)} scenes")
    else:
        video_cache_name = f"video_manifest{manifest_suffix}.json"
        fetch_manifest = load_cache(str(cache_dir), video_cache_name) if not new else None
        if fetch_manifest and _video_files_exist(fetch_manifest):
            click.echo("[3/4] Fetching videos... CACHED (skipped)")
        else:
            click.echo("[3/4] Fetching stock videos...")
            fetch_manifest = fetch_videos(scene_plan, output_dir=str(cache_dir))
            save_cache(str(cache_dir), video_cache_name, fetch_manifest)
        fetched = sum(1 for f in fetch_manifest if f["video_path"].endswith(".mp4"))
        click.echo(f"  Fetched: {fetched}/{len(fetch_manifest)} videos")

    # Resolve font
    font = get_font_path(custom_path=font_path)

    # === Preset mode routing ===
    if preset is not None:
        _run_preset_mode(
            preset=preset,
            reel_duration=int(reel_duration),
            analysis=analysis,
            scene_plan=scene_plan,
            fetch_manifest=fetch_manifest,
            audio_path=str(audio_path),
            output_dir=output_dir,
            stem=audio_path.stem,
            font=font,
            effects=effects,
            cache_dir=cache_dir,
            new=new,
            logo_path=logo_path,
            logo_position=logo_position,
            logo_size=logo_size,
            logo_opacity=logo_opacity,
            lut_style=lut_style,
            lut_intensity=lut_intensity,
            sequential_assembly=sequential_assembly,
            reels_style=reels_style,
            wow_config=wow_config,
        )
        return

    # === Original single-output mode (unchanged) ===
    # Build output filename
    if clip_duration:
        suffix = f"_{clip_duration}s"
        if platform:
            suffix += f"_{platform}"
        output_filename = audio_path.stem + suffix + ".mp4"
    else:
        output_filename = audio_path.stem + "_musicvideo.mp4"
    output_path = str(output_dir / output_filename)

    # Build title card text if requested
    title_card_text = audio_path.stem if title_card and clip_duration else None

    # Stage 4: Assemble Video
    click.echo("[4/4] Assembling video...")
    assemble_video(
        analysis=analysis,
        scene_plan=scene_plan,
        fetch_manifest=fetch_manifest,
        audio_path=str(audio_path),
        output_path=output_path,
        resolution=effective_resolution,
        font_path=font,
        effects_level=effects,
        clip_start=clip_start,
        clip_end=clip_end,
        title_card_text=title_card_text,
        logo_path=logo_path,
        logo_position=logo_position,
        logo_size=logo_size,
        logo_opacity=logo_opacity,
        cinematic_bars=(effects == "full"),
        lut_style=lut_style,
        lut_intensity=lut_intensity,
        reels_style=reels_style,
        wow_config=wow_config,
    )
    click.echo(f"  Done! Output: {output_path}")


def _run_preset_mode(preset, reel_duration, analysis, scene_plan, fetch_manifest,
                     audio_path, output_dir, stem, font, effects, cache_dir, new,
                     logo_path=None, logo_position="top-left", logo_size=None, logo_opacity=0.85,
                     lut_style=None, lut_intensity=0.85, sequential_assembly=False,
                     reels_style="blur-bg", wow_config=None):
    """Handle --preset flag: generate full video and/or social reels."""
    generate_full = preset in ("full", "all")
    generate_social = preset in ("social", "all")

    # Social clip selection (unchanged from before)
    social_clips = None
    if generate_social:
        social_cache_name = f"social_clips_{reel_duration}s.json"
        social_clips = load_cache(str(cache_dir), social_cache_name) if not new else None
        if social_clips:
            click.echo(f"[social] Social clip selection ({reel_duration}s)... CACHED (skipped)")
        else:
            click.echo(f"[social] Selecting 3 \u00d7 {reel_duration}s fragments...")
            social_clips = select_social_clips(analysis, reel_duration)
            save_cache(str(cache_dir), social_cache_name, social_clips)
        for clip in social_clips["clips"]:
            click.echo(f"  Clip {clip['id']}: {clip['start']:.1f}s\u2013{clip['end']:.1f}s "
                       f"({clip.get('section', '?')}) \u2014 {clip.get('reason', '')}")

    click.echo("[4/4] Monta\u017c:")

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
                wow_config=wow_config,
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
            click.echo(f"  Rolka {clip_id}: start={clip_start:.1f}s end={clip_end:.1f}s")
            click.echo(f"    Dostępne sceny: {[(e['scene_index'], e['video_path']) for e in fetch_manifest]}")
            clip_analysis = _filter_analysis_to_clip(analysis, clip_start, clip_end)
            clip_scene_plan = _filter_scene_plan_to_clip(scene_plan, clip_start, clip_end)
            for scene in clip_scene_plan["scenes"]:
                scene["motion"] = _remap_motion_for_portrait(scene.get("motion", "static"))
            clip_manifest = _filter_manifest_to_clip(
                fetch_manifest, scene_plan["scenes"], clip_start, clip_end
            )
            clip_manifest = _validate_clip_manifest(clip_manifest, fetch_manifest)
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
                    reels_style=reels_style,
                    wow_config=wow_config,
                ),
            ))

    # Assemble: parallel (default) or sequential (--sequential-assembly or single job)
    if sequential_assembly or len(jobs) == 1:
        output_paths = []
        for job in jobs:
            click.echo(f"  \u2192 {job.name}...")
            assemble_video(**job.kwargs)
            click.echo(f"  \u2192 {job.name}... \u2705")
            output_paths.append(job.kwargs["output_path"])
    else:
        click.echo(f"  R\u00f3wnoleg\u0142y monta\u017c ({len(jobs)} w\u0105tki, max 4)...")
        output_paths = assemble_all_parallel(jobs)

    # Summary
    click.echo(f"\nGotowe! Wygenerowano {len(output_paths)} plik\u00f3w:")
    for path in output_paths:
        click.echo(f"  {path}")


if __name__ == "__main__":
    cli()
