"""MusicVid CLI — Christian Music Video Generator."""

import hashlib
import shutil
from pathlib import Path

import click
from dotenv import load_dotenv

from musicvid.pipeline.audio_analyzer import analyze_audio
from musicvid.pipeline.cache import get_audio_hash, load_cache, save_cache
from musicvid.pipeline.director import create_scene_plan
from musicvid.pipeline.stock_fetcher import fetch_videos
from musicvid.pipeline.image_generator import generate_images
from musicvid.pipeline.assembler import assemble_video
from musicvid.pipeline.font_loader import get_font_path
from musicvid.pipeline.lyrics_parser import parse as parse_lyrics


load_dotenv()


def _video_files_exist(manifest):
    """Check that all video files referenced in the manifest exist on disk."""
    return all(Path(entry["video_path"]).exists() for entry in manifest)


def _image_files_exist(manifest):
    """Check that all image files referenced in the manifest exist on disk."""
    return all(Path(entry["video_path"]).exists() for entry in manifest)


@click.command()
@click.argument("audio_file", type=click.Path(exists=True))
@click.option("--mode", type=click.Choice(["stock", "ai", "hybrid"]), default="stock", help="Video source mode.")
@click.option("--provider", type=click.Choice(["flux-dev", "flux-pro", "flux-schnell"]), default="flux-dev", help="Image provider for --mode ai.")
@click.option("--style", type=click.Choice(["auto", "contemplative", "joyful", "worship", "powerful"]), default="auto", help="Visual style.")
@click.option("--output", type=click.Path(), default="./output/", help="Output directory.")
@click.option("--resolution", type=click.Choice(["720p", "1080p", "4k"]), default="1080p", help="Output resolution.")
@click.option("--lang", default="auto", help="Language for transcription.")
@click.option("--new", is_flag=True, default=False, help="Force recalculation, ignore cache.")
@click.option("--font", "font_path", type=click.Path(), default=None, help="Custom .ttf font file for subtitles.")
@click.option("--lyrics", "lyrics_path", type=click.Path(), default=None, help="Path to .txt lyrics file (skips Whisper).")
def cli(audio_file, mode, provider, style, output, resolution, lang, new, font_path, lyrics_path):
    """Generate a music video from AUDIO_FILE."""
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
        click.echo("  ⚠ Znaleziono wiele plików .txt — użyj --lyrics aby wybrać")

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
    # Replace lyrics from file if available
    if lyrics_file:
        parsed_lyrics = parse_lyrics(str(lyrics_file), analysis["duration"])
        analysis["lyrics"] = parsed_lyrics
        line_count = len(parsed_lyrics)
        if lyrics_path:
            click.echo(f"[1/4] Tekst: wczytano z pliku ({line_count} linijek)")
        else:
            click.echo(f"[1/4] Tekst: znaleziono automatycznie → {lyrics_file.name} ({line_count} linijek)")

    click.echo(f"  BPM: {analysis['bpm']}, Duration: {analysis['duration']}s, "
               f"Sections: {len(analysis['sections'])}, Mood: {analysis['mood_energy']}")

    # Stage 2: Direct Scenes
    style_override = style if style != "auto" else None
    scene_plan = load_cache(str(cache_dir), "scene_plan.json") if not new else None
    if scene_plan:
        click.echo("[2/4] Scene planning... CACHED (skipped)")
    else:
        click.echo("[2/4] Creating scene plan...")
        scene_plan = create_scene_plan(analysis, style_override=style_override, output_dir=str(cache_dir))
        save_cache(str(cache_dir), "scene_plan.json", scene_plan)
    click.echo(f"  Style: {scene_plan['overall_style']}, Scenes: {len(scene_plan['scenes'])}")

    # Stage 3: Fetch Videos or Generate Images
    if mode == "ai":
        image_manifest = load_cache(str(cache_dir), "image_manifest.json") if not new else None
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
            save_cache(str(cache_dir), "image_manifest.json", fetch_manifest)
        click.echo(f"  Generated: {len(fetch_manifest)} images")
    else:
        fetch_manifest = load_cache(str(cache_dir), "video_manifest.json") if not new else None
        if fetch_manifest and _video_files_exist(fetch_manifest):
            click.echo("[3/4] Fetching videos... CACHED (skipped)")
        else:
            click.echo("[3/4] Fetching stock videos...")
            fetch_manifest = fetch_videos(scene_plan, output_dir=str(cache_dir))
            save_cache(str(cache_dir), "video_manifest.json", fetch_manifest)
        fetched = sum(1 for f in fetch_manifest if f["video_path"].endswith(".mp4"))
        click.echo(f"  Fetched: {fetched}/{len(fetch_manifest)} videos")

    # Resolve font
    font = get_font_path(custom_path=font_path)

    # Stage 4: Assemble Video
    click.echo("[4/4] Assembling video...")
    output_filename = audio_path.stem + "_musicvideo.mp4"
    output_path = str(output_dir / output_filename)
    assemble_video(
        analysis=analysis,
        scene_plan=scene_plan,
        fetch_manifest=fetch_manifest,
        audio_path=str(audio_path),
        output_path=output_path,
        resolution=resolution,
        font_path=font,
    )
    click.echo(f"  Done! Output: {output_path}")


if __name__ == "__main__":
    cli()
