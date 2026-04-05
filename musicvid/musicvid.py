"""MusicVid CLI — Christian Music Video Generator."""

import hashlib
import os
import shutil
from pathlib import Path

import click
from dotenv import load_dotenv

from musicvid.pipeline.audio_analyzer import analyze_audio
from musicvid.pipeline.cache import get_audio_hash, load_cache, save_cache
from musicvid.pipeline.clip_selector import select_clip
from musicvid.pipeline.director import create_scene_plan
from musicvid.pipeline.stock_fetcher import fetch_videos
from musicvid.pipeline.image_generator import generate_images
from musicvid.pipeline.assembler import assemble_video
from musicvid.pipeline.font_loader import get_font_path
from musicvid.pipeline.lyrics_parser import align_with_claude
from musicvid.pipeline.video_animator import animate_image
from musicvid.pipeline.social_clip_selector import select_social_clips
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


@click.command()
@click.argument("audio_file", type=click.Path(exists=True))
@click.option("--mode", type=click.Choice(["stock", "ai", "hybrid"]), default="ai", help="Video source mode.")
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
@click.option("--reel-duration", type=click.Choice(["15", "20", "30"]), default="15", help="Duration of social media reels in seconds.")
@click.option("--logo", "logo_path", type=click.Path(), default=None, help="Path to logo file (SVG/PNG) to overlay on video.")
@click.option("--logo-position", type=click.Choice(["top-left", "top-right", "bottom-left", "bottom-right"]), default="top-left", help="Logo position on screen.")
@click.option("--logo-size", type=int, default=None, help="Logo width in pixels (default: auto 12%% of frame width).")
@click.option("--logo-opacity", type=float, default=0.85, help="Logo opacity 0.0-1.0.")
@click.option("--lut-style", type=click.Choice(["warm", "cold", "cinematic", "natural", "faded"]), default="warm", help="Built-in LUT color grade style.")
@click.option("--lut-intensity", type=float, default=0.85, help="LUT intensity 0.0-1.0.")
@click.option("--subtitle-style", "subtitle_style_override", type=click.Choice(["fade", "karaoke", "none"]), default="karaoke", help="Subtitle animation style.")
@click.option("--transitions", "transitions_mode", type=click.Choice(["cut", "auto"]), default="auto", help="Scene transition style (auto: director decides, cut: force hard cuts).")
@click.option("--beat-sync", "beat_sync", type=click.Choice(["off", "auto"]), default="auto", help="Align scene cuts to beat positions.")
@click.option("--yes", "skip_confirm", is_flag=True, default=False, help="Skip confirmation prompt.")
@click.option("--quick", "quick_mode", is_flag=True, default=False, help="Quick mode: stock images, no animation, cut transitions, no LUT.")
@click.option("--economy", "economy_mode", is_flag=True, default=False, help="Economy mode: flux-dev AI images, no Runway animation, warm LUT.")
def cli(audio_file, mode, provider, style, output, resolution, lang, new, font_path, lyrics_path,
        effects, clip_duration, platform, title_card, animate_mode, preset, reel_duration,
        logo_path, logo_position, logo_size, logo_opacity,
        lut_style, lut_intensity, subtitle_style_override, transitions_mode, beat_sync,
        skip_confirm, quick_mode, economy_mode):
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
    # Replace lyrics using AI alignment if lyrics file available
    if lyrics_file:
        aligned_cache_name = f"lyrics_aligned_{lyrics_hash}.json"
        aligned = load_cache(str(cache_dir), aligned_cache_name) if not new else None
        if aligned:
            analysis["lyrics"] = aligned
            line_count = len(aligned)
            click.echo(f"[1/4] Tekst: AI dopasowanie... CACHED ({line_count} linii)")
        else:
            with open(lyrics_file, "r", encoding="utf-8") as f:
                file_lines = [line.strip() for line in f if line.strip()]
            aligned = align_with_claude(analysis["lyrics"], file_lines)
            save_cache(str(cache_dir), aligned_cache_name, aligned)
            analysis["lyrics"] = aligned
            line_count = len(file_lines)
            click.echo(f"[1/4] Tekst: Whisper timing + AI dopasowanie tekstu z pliku ({line_count} linii)")

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
        scene_plan = create_scene_plan(analysis, style_override=style_override, output_dir=str(cache_dir))
        save_cache(str(cache_dir), scene_cache_name, scene_plan)
    click.echo(f"  Style: {scene_plan['overall_style']}, Scenes: {len(scene_plan['scenes'])}")

    # Stage 3: Fetch Videos or Generate Images
    manifest_suffix = f"_clip_{clip_duration}s" if clip_duration else ""
    if mode == "ai":
        image_cache_name = f"image_manifest{manifest_suffix}.json"
        image_manifest = load_cache(str(cache_dir), image_cache_name) if not new else None
        if image_manifest and _image_files_exist(image_manifest):
            click.echo("[3/4] Generating images... CACHED (skipped)")
            fetch_manifest = image_manifest
        else:
            click.echo(f"[3/4] Generating images (provider: {provider})...")
            image_paths = generate_images(scene_plan, str(cache_dir), provider=provider)
            fetch_manifest = [
                {"scene_index": i, "video_path": path, "search_query": scene["visual_prompt"]}
                for i, (path, scene) in enumerate(zip(image_paths, scene_plan["scenes"]))
            ]
            save_cache(str(cache_dir), image_cache_name, fetch_manifest)
        click.echo(f"  Generated: {len(fetch_manifest)} images")

        # Apply --animate overrides to scene plan
        if animate_mode == "always":
            for scene in scene_plan["scenes"]:
                scene["animate"] = True
                if not scene.get("motion_prompt"):
                    scene["motion_prompt"] = "Slow camera push forward, gentle atmospheric movement"
        elif animate_mode == "never":
            for scene in scene_plan["scenes"]:
                scene["animate"] = False

        # Stage 3.5: Animate scenes with Runway Gen-4
        if animate_mode != "never":
            runway_key = os.environ.get("RUNWAY_API_KEY")
            for entry in fetch_manifest:
                idx = entry["scene_index"]
                scene = scene_plan["scenes"][idx]
                if not scene.get("animate", False):
                    continue
                if not runway_key:
                    click.echo(f"  \u26a0 RUNWAY_API_KEY not set \u2014 Ken Burns fallback for scene {idx + 1}")
                    scene["animate"] = False
                    continue
                animated_path = str(cache_dir / f"animated_scene_{idx:03d}.mp4")
                click.echo(f"  Animating scene {idx + 1}/{len(scene_plan['scenes'])}...")
                try:
                    result_path = animate_image(
                        entry["video_path"],
                        scene.get("motion_prompt", "Slow camera push forward"),
                        duration=5,
                        output_path=animated_path,
                    )
                    entry["video_path"] = result_path
                except Exception as exc:
                    click.echo(f"  \u26a0 Animation failed for scene {idx + 1}: {exc} \u2014 Ken Burns fallback")
                    scene["animate"] = False
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
    )
    click.echo(f"  Done! Output: {output_path}")


def _run_preset_mode(preset, reel_duration, analysis, scene_plan, fetch_manifest,
                     audio_path, output_dir, stem, font, effects, cache_dir, new,
                     logo_path=None, logo_position="top-left", logo_size=None, logo_opacity=0.85):
    """Handle --preset flag: generate full video and/or social reels."""
    generate_full = preset in ("full", "all")
    generate_social = preset in ("social", "all")

    # Social clip selection
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

    # Count total assemblies for progress
    total = (1 if generate_full else 0) + (3 if generate_social else 0)
    assembly_num = 0

    click.echo("[4/4] Monta\u017c:")

    # Stage 4a: Full YouTube video
    if generate_full:
        assembly_num += 1
        pelny_dir = output_dir / "pelny"
        pelny_dir.mkdir(parents=True, exist_ok=True)
        full_output = str(pelny_dir / f"{stem}_youtube.mp4")
        click.echo(f"  \u2192 Pe\u0142ny teledysk YouTube ({assembly_num}/{total})...")
        assemble_video(
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
        )
        click.echo(f"  \u2192 Pe\u0142ny teledysk YouTube ({assembly_num}/{total})... \u2705")

    # Stage 4b-d: Social reels
    if generate_social:
        social_dir = output_dir / "social"
        social_dir.mkdir(parents=True, exist_ok=True)

        for clip_info in social_clips["clips"]:
            assembly_num += 1
            clip_id = clip_info["id"]
            clip_start = clip_info["start"]
            clip_end = clip_info["end"]
            section = clip_info.get("section", "unknown")

            reel_output = str(social_dir / f"{stem}_rolka_{clip_id}_{reel_duration}s.mp4")

            click.echo(f"  \u2192 Rolka {clip_id} \u2014 {section} ({assembly_num}/{total})...")

            # Filter analysis, scene plan, and manifest to clip window
            clip_analysis = _filter_analysis_to_clip(analysis, clip_start, clip_end)
            clip_scene_plan = _filter_scene_plan_to_clip(scene_plan, clip_start, clip_end)

            # Remap horizontal pans to vertical for portrait
            for scene in clip_scene_plan["scenes"]:
                scene["motion"] = _remap_motion_for_portrait(scene.get("motion", "static"))

            clip_manifest = _filter_manifest_to_clip(
                fetch_manifest, scene_plan["scenes"], clip_start, clip_end
            )

            assemble_video(
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
            )
            click.echo(f"  \u2192 Rolka {clip_id} \u2014 {section} ({assembly_num}/{total})... \u2705")

    # Summary
    click.echo(f"\nGotowe! Wygenerowano {total} plik\u00f3w:")
    if generate_full:
        click.echo(f"  {output_dir}/pelny/{stem}_youtube.mp4")
    if generate_social:
        for clip_info in social_clips["clips"]:
            click.echo(f"  {output_dir}/social/{stem}_rolka_{clip_info['id']}_{reel_duration}s.mp4")


if __name__ == "__main__":
    cli()
