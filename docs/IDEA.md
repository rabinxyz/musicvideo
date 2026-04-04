# Idea

# Christian Music Video Generator

## Cel
Aplikacja CLI przyjmuje jeden plik audio i generuje teledysk MP4 zsynchronizowany z muzyka.

## Uzycie
musicvid song.mp3
musicvid song.mp3 --mode ai
musicvid song.mp3 --mode stock
musicvid song.mp3 --mode hybrid
musicvid song.mp3 --style contemplative
musicvid song.mp3 --output ./output/
musicvid song.mp3 --resolution 1080p

## Stack
openai-whisper — transkrypcja z word-level timestamps
librosa — BPM, beat tracking, detekcja sekcji intro/verse/chorus/outro
Claude API claude-sonnet-4 — rezyseria, plan scen, prompty obrazow
DALL-E 3 — generowanie obrazow (tryb ai)
Pexels API — stock footage darmowy (tryb domyslny, klucz na pexels.com/api)
MoviePy + FFmpeg — montaz wideo
Click — CLI

## Zmienne srodowiskowe
ANTHROPIC_API_KEY
OPENAI_API_KEY
PEXELS_API_KEY

## Struktura projektu
musicvid/
  musicvid.py
  pipeline/
    audio_analyzer.py
    director.py
    image_generator.py
    stock_fetcher.py
    assembler.py
  prompts/
    director_system.txt
  requirements.txt
  .env.example

## Stage 1 audio_analyzer.py
Whisper model=base lub small, word_timestamps=True
Zwraca segmenty z polami start/end/text/words
librosa beat_track -> tempo i beat_times w sekundach
librosa recurrence_matrix -> detekcja sekcji
Wyjscie dict: lyrics, beats, bpm, duration, sections, mood_energy, language

## Stage 2 director.py
Claude dostaje pelna analize audio i zwraca plan scen jako czysty JSON bez markdown.
System prompt z pliku prompts/director_system.txt:
  styl protestancki bez wizerunków Marii swietych figur
  dopuszczalne: przyroda swiatlo krzyz-prosty ludzie-w-uwielbieniu abstrakcja-duchowa
Struktura JSON:
  overall_style: contemplative|joyful|worship|powerful
  color_palette: [hex hex hex]
  subtitle_style: font_size color outline_color position animation
  scenes: lista z polami section/start/end/visual_prompt/motion/transition/overlay

## Stage 3A image_generator.py tryb ai
DALL-E 3 rozmiar 1792x1024
Do kazdego promptu dodaj: Protestant Christian aesthetic no Catholic imagery no saints cinematic 16:9
Fallback Replicate Stable Diffusion jesli brak OPENAI_API_KEY

## Stage 3B stock_fetcher.py tryb domyslny
Pexels API GET https://api.pexels.com/videos/search orientation=landscape size=large
Mapowanie styl -> query:
  contemplative: mountain sunrise / calm water reflection / forest light
  joyful: sunlight meadow / golden fields / bright sky clouds
  worship: hands raised light / crowd worship / candles warm
  powerful: storm clouds dramatic / ocean waves / mountain peak
Backup Pixabay API

## Stage 4 assembler.py
Ken Burns na ImageClip: slow_zoom_in scale 1.0->1.15 / slow_zoom_out 1.15->1.0 / pan crop window
Napisy TextClip z Whisper: Arial-Bold stroke_width=2 fade 0.3s pozycja center-bottom margines 80px
Ciecia synchronizowane z beat_times z librosa
Overlays: particles biale punkty opacity 0.3 / light_rays gradient z gory / bokeh rozmyte kola
Eksport H.264 bitrate=8000k fps=30 audio=AAC

## CLI musicvid.py Click
Argumenty: audio_file wymagany
Opcje: --mode stock/ai/hybrid (domyslnie stock)
       --style auto/contemplative/joyful/worship/powerful (domyslnie auto)
       --output ./output/ (domyslnie)
       --resolution 720p/1080p/4k (domyslnie 1080p)
       --lang auto (domyslnie)
Logowanie: tqdm + print z prefixem [1/4] [2/4] [3/4] [4/4]
Kazdy stage zapisuje wyniki posrednie do output/tmp/

## requirements.txt
anthropic>=0.40.0
openai>=1.50.0
openai-whisper>=20231117
librosa>=0.10.0
moviepy>=1.0.3
click>=8.1.0
requests>=2.31.0
Pillow>=10.0.0
numpy>=1.24.0
soundfile>=0.12.0
ffmpeg-python>=0.2.0
pyyaml>=6.0
python-dotenv>=1.0.0
tqdm>=4.66.0
tenacity>=8.2.0

macOS: brew install ffmpeg imagemagick

## Priorytety MVP
1. audio_analyzer.py
2. director.py
3. stock_fetcher.py
4. assembler.py podstawowy Ken Burns + napisy
5. musicvid.py CLI

## V2 po MVP
6. image_generator.py DALL-E 3
7. tryb hybrid
8. overlays particles/light_rays/bokeh
9. cache tmp/

## Wymagania niefunkcjonalne
Czas: <5min tryb stock <15min tryb AI dla 4-minutowej piosenki
Jakosc: 1080p H.264 8000k kompatybilne z YouTube
Formaty wejsciowe: MP3 WAV FLAC M4A OGG
Graceful degradation: placeholder jesli API nie odpowiada
Retry exponential backoff tenacity na wszystkich API
Smoke test test_pipeline.py z 10-sekundowym plikiem audio
