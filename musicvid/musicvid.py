"""MusicVid CLI — Christian Music Video Generator."""

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
@click.option("--provider", type=click.Choice(["dalle", "flux-dev", "flux-pro", "schnell"]), default="flux-dev", help="Image provider for --mode ai.")
@click.option("--style", type=click.Choice(["auto", "contemplative", "joyful", "worship", "powerful"]), default="auto", help="Visual style.")
@click.option("--output", type=click.Path(), default="./output/", help="Output directory.")
@click.option("--resolution", type=click.Choice(["720p", "1080p", "4k"]), default="1080p", help="Output resolution.")
@click.option("--lang", default="auto", help="Language for transcription.")
@click.option("--new", is_flag=True, default=False, help="Force recalculation, ignore cache.")
def cli(audio_file, mode, provider, style, output, resolution, lang, new):
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

    # Stage 1: Analyze Audio
    analysis = load_cache(str(cache_dir), "audio_analysis.json") if not new else None
    if analysis:
        click.echo("[1/4] Audio analysis... CACHED (skipped)")
    else:
        click.echo("[1/4] Analyzing audio...")
        analysis = analyze_audio(str(audio_path), output_dir=str(cache_dir))
        save_cache(str(cache_dir), "audio_analysis.json", analysis)
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
    )
    click.echo(f"  Done! Output: {output_path}")


if __name__ == "__main__":
    cli()
