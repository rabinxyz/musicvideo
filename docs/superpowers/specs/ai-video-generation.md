# Spec: AI Image Generation Mode

## Goal
Implement --mode ai in the pipeline so DALL-E 3 generates one image per scene,
then MoviePy assembles them into the final video with Ken Burns effect and subtitles.

## Context
Project: musicvid CLI tool
Existing pipeline: audio_analyzer -> director -> stock_fetcher -> assembler
New stage: image_generator replaces stock_fetcher when --mode ai is passed

## Implementation

### musicvid/pipeline/image_generator.py (new file)
- Function: generate_images(scene_plan: dict, output_dir: str) -> list[str]
- For each scene in scene_plan["scenes"]:
  - Take scene["visual_prompt"] from director output
  - Append to every prompt: "Protestant Christian aesthetic, no religious figures,
    no Catholic symbols, no rosary, no stained glass with figures, no crucifix,
    no Madonna, no saints, no monks, no papal imagery, no incense burner,
    no tabernacle, no confessional, no Byzantine icons, cinematic 16:9,
    photorealistic, high quality"
  - Call DALL-E 3: client.images.generate(model="dall-e-3", size="1792x1024", quality="standard")
  - Download image to output_dir/scene_NNN.png
  - Return list of image file paths in scene order
- Use tenacity: @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
  on the API call
- Raise clear error if OPENAI_API_KEY not set in environment

### musicvid/pipeline/assembler.py (modify)
- Already handles ImageClip — verify it accepts PNG paths from image_generator
- Ken Burns effect on each ImageClip:
  - slow_zoom_in: scale from 1.0 to 1.15 over scene duration using transform()
  - Use moviepy 2.x API: transform(), with_position(), with_effects()
  - NOT the old API: fl(), set_position(), crossfadein()
- Subtitles from Whisper timestamps via TextClip(text=..., font_size=52)
- Concatenate all scene clips, set audio from original file
- Export: H.264, fps=30, bitrate=8000k, audio=AAC

### musicvid/musicvid.py (modify)
- When --mode ai: import and call image_generator.generate_images()
  instead of stock_fetcher
- Cache the image paths list in output/tmp/{hash}/image_manifest.json
- Skip generation if cache exists and all PNG files are present on disk

### prompts/director_system.txt (create if missing)
Create this file with Protestant-only visual guidelines:

BANNED (never include in prompts):
rosary, prayer beads, crucifix, Madonna, Virgin Mary, saints, stained glass with figures,
tabernacle, monstrance, confessional, incense burner, censer, thurifer, holy water,
scapular, religious statuettes, figurines, Byzantine icons, papal imagery,
Sacred Heart with thorns, IHS symbol with rays, Lourdes grotto, wayside shrine with figure,
Marian lily, baroque church interior with figures, bishop in liturgical vestments

ALLOWED (preferred Protestant motifs):
empty cross (no figure), open Bible, dove as Holy Spirit symbol,
mountains and mountain peaks, sunrise and sunset with light rays through clouds,
calm water lakes rivers ocean, forests meadows golden fields,
starry sky, abstract light rays and lens flares, golden light at dawn and dusk,
silhouettes of people with hands raised in worship, community gathered together,
hands folded in prayer (no rosary), someone reading Bible,
particles bokeh watercolor warm colors gold white blue green

RULE: every prompt must end with the full disclaimer above.
RULE: if a motif could be read as Catholic, replace it with nature or light.
RULE: return ONLY clean JSON, no markdown, no comments.

### .env.example (add line)
OPENAI_API_KEY=sk-...

### tests/test_image_generator.py (new file)
- Mock openai.OpenAI and requests.get
- Test: generate_images() returns correct number of file paths
- Test: every prompt contains the Protestant disclaimer suffix
- Test: retry logic fires on openai.APIError
- Test: raises EnvironmentError when OPENAI_API_KEY missing
- Use python3 -m pytest tests/ -v to run

## Acceptance Criteria
- python3 -m musicvid.musicvid song.mp3 --mode ai runs without error
- Each scene produces one PNG in output/tmp/{hash}/
- Final MP4 has Ken Burns motion on every scene
- No Catholic imagery keywords appear in any generated prompt
- All new tests pass: python3 -m pytest tests/test_image_generator.py -v

## Notes
- Python 3.11+, no type annotations
- moviepy 2.1.2 installed — use new 2.x API only
- Use python3 not python on this macOS system
- ffmpeg and imagemagick available via Homebrew
