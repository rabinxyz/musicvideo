"""MusicVid CLI — Christian Music Video Generator."""

from pathlib import Path

import click
from dotenv import load_dotenv

from musicvid.pipeline.audio_analyzer import analyze_audio
from musicvid.pipeline.director import create_scene_plan
from musicvid.pipeline.stock_fetcher import fetch_videos
from musicvid.pipeline.assembler import assemble_video


load_dotenv()


@click.command()
@click.argument("audio_file", type=click.Path(exists=True))
@click.option("--mode", type=click.Choice(["stock", "ai", "hybrid"]), default="stock", help="Video source mode.")
@click.option("--style", type=click.Choice(["auto", "contemplative", "joyful", "worship", "powerful"]), default="auto", help="Visual style.")
@click.option("--output", type=click.Path(), default="./output/", help="Output directory.")
@click.option("--resolution", type=click.Choice(["720p", "1080p", "4k"]), default="1080p", help="Output resolution.")
@click.option("--lang", default="auto", help="Language for transcription.")
def cli(audio_file, mode, style, output, resolution, lang):
    """Generate a music video from AUDIO_FILE."""
    audio_path = Path(audio_file).resolve()
    output_dir = Path(output).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir = output_dir / "tmp"
    tmp_dir.mkdir(exist_ok=True)

    # Stage 1: Analyze Audio
    click.echo("[1/4] Analyzing audio...")
    analysis = analyze_audio(str(audio_path), output_dir=str(tmp_dir))
    click.echo(f"  BPM: {analysis['bpm']}, Duration: {analysis['duration']}s, "
               f"Sections: {len(analysis['sections'])}, Mood: {analysis['mood_energy']}")

    # Stage 2: Direct Scenes
    click.echo("[2/4] Creating scene plan...")
    style_override = style if style != "auto" else None
    scene_plan = create_scene_plan(analysis, style_override=style_override, output_dir=str(tmp_dir))
    click.echo(f"  Style: {scene_plan['overall_style']}, Scenes: {len(scene_plan['scenes'])}")

    # Stage 3: Fetch Videos
    click.echo("[3/4] Fetching stock videos...")
    fetch_manifest = fetch_videos(scene_plan, output_dir=str(tmp_dir))
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
