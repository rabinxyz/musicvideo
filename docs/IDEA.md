# Idea

# Spec: Pro wizualizacje — filtry, efekty, przejścia, brak duplikatów

## Problem 1 — brak filtrów kolorów dla pełnego teledysku

Social media mają LUT — pełny teledysk nie.
Ujednolicić: oba formaty dostają ten sam domyślny filtr kolorów.

Domyślny LUT "Worship Warm":
  Shadows: lekki shift w kierunku deep blue (#1a1a2e)
  Midtones: ciepły amber, lekko desaturowane
  Highlights: cream/ivory (#fffff0)
  Kontrast: +12%
  Saturacja: -8% (filmowy look)

Implementacja przez FFmpeg curves filter (szybkie, nie frame-by-frame):
  curves=r='0/0 0.3/0.28 0.7/0.75 1/1':
        g='0/0 0.3/0.29 0.7/0.72 1/0.97':
        b='0/0.05 0.3/0.32 0.7/0.68 1/0.92'

Dodaj do KAŻDEGO eksportu przez FFmpeg jako ostatni krok:
  Pełny teledysk: curves filter + eq=saturation=0.92:contrast=1.12
  Rolki: ten sam filter + eq=saturation=1.05:contrast=1.15 (lekko mocniej)

Nowa flaga: --color-grade [worship-warm|teal-orange|bleach|natural]
Domyślnie: worship-warm

Mapowanie styli do LUT:
  worship-warm: ciepły amber, filmowy — dla contemplative/worship
  teal-orange:  teal shadows + orange highlights — dla powerful/joyful
  bleach:       desaturacja +kontrast — dla bridge/dramatycznych scen
  natural:      minimalne zmiany — dla intro/outro

Claude-reżyser wybiera color_grade w overall_style:
  "color_grade": "worship-warm"

## Problem 2 — duplikaty filmów stock

Pexels zwraca te same filmy przy podobnych queries.
Efekt: kilka scen ma identyczne tło — wygląda amatorsko.

Rozwiązanie — globalny rejestr pobranych URL:

W stock_fetcher.py:
  _downloaded_urls = set()  # globalny na cały run

  def fetch_video_by_query(query, min_duration, output_path):
      resp = requests.get(pexels_url, params={...})
      videos = resp.json()['videos']

      # Odfiltruj już pobrane
      fresh_videos = [v for v in videos
                      if v['url'] not in _downloaded_urls]

      if not fresh_videos:
          # Spróbuj z innym zapytaniem (dodaj synonim)
          fresh_videos = videos  # fallback — weź pierwszy

      video = fresh_videos[0]
      _downloaded_urls.add(video['url'])
      # pobierz i zapisz...

Dodatkowo: przy każdym zapytaniu dodaj losowy element różnicujący:
  QUERY_VARIANTS = {
      "mountain sunrise": ["mountain sunrise morning", "mountain peak dawn", "alpine sunrise"],
      "lake reflection":  ["calm lake mirror", "mountain lake reflection", "lake dawn still"],
      "forest light":     ["forest sunbeam", "forest morning rays", "pine forest light"],
  }
  Rotuj między wariantami per run używając hash audio jako seed.

## Problem 3 — więcej dynamiki i efektów

### 3A — Więcej typów przejść dla rolek

Rolki muszą być 2x bardziej dynamiczne niż pełny film.

Dla rolek dodaj:
  SLIDE_LEFT: scena B wjeżdża z prawej
    FFmpeg: xfade=transition=slideleft:duration=0.3
  SLIDE_UP: scena B wjeżdża z dołu (naturalny dla 9:16)
    FFmpeg: xfade=transition=slideup:duration=0.3
  ZOOM_IN_HARD: agresywny zoom 1.0→1.3 na ostatnich 3 klatkach przed cięciem
  WIPE_RIGHT: poziome przejście jak w CapCut
    FFmpeg: xfade=transition=wipeleft:duration=0.2

Mapa przejść dla rolek (bardziej dynamiczna niż pełny film):
  verse→chorus:  SLIDE_UP (wejście w refren z dołu — energetyczne)
  chorus→verse:  ZOOM_IN_HARD + fade
  chorus→chorus: WIPE_RIGHT (szybkie, dynamiczne)
  verse→verse:   SLIDE_LEFT
  bridge→chorus: SLIDE_UP z flash

### 3B — Zoom punch na rolkach

Na każdym downbeat refrenu w rolkach:
Agresywniejszy zoom punch niż w pełnym filmie:
  scale 1.0 → 1.12 w 2 klatkach, powrót 1.12 → 1.0 w 8 klatkach

Implementacja przez MoviePy transform():
  def zoom_punch(get_frame, t, punch_times, fps=30):
      frame = get_frame(t)
      for pt in punch_times:
          if 0 <= t - pt < 0.067:  # pierwsze 2 klatki
              scale = 1.0 + 0.12 * ((t - pt) / 0.067)
              return zoom_frame(frame, scale)
          elif 0.067 <= t - pt < 0.333:  # kolejne 8 klatek
              scale = 1.12 - 0.12 * ((t - pt - 0.067) / 0.267)
              return zoom_frame(frame, scale)
      return frame

### 3C — Text flash na rolkach

Przy wejściu każdej linijki napisu w rolce:
Krótki white flash 0.05s (3 klatki) na początku napisu.

Implementacja: ColorClip biały z opacity animowaną:
  t=0: opacity 0.6
  t=0.05: opacity 0 (zanika)

### 3D — Gradient overlay dolny dla rolek

Stały gradient czarny na dole ekranu (30% wysokości):
  opacity: 0.5
Poprawia czytelność napisów na jasnych klipach.

Implementacja: ImageClip z numpy gradient array, with_position('bottom').

### 3E — Intro hook dla rolek (pierwsze 2s)

Rolka MUSI zaczynać się od najlepszego momentu wizualnie:
Pierwsze 2s = najlepsza klatka z całej rolki (peak visual moment).

Implementacja:
  Weź środkową klatkę pierwszego klipu jako thumbnail
  Wyświetl ją przez 0.5s przed startem wideo (freeze frame)
  Fade in 0.3s z tej klatki do normalnego wideo

## Problem 4 — LUT automatyczny per sekcja

Nie jeden LUT dla całości — różny kontrast per sekcja:

Verse:   eq=saturation=0.88:contrast=1.08:brightness=0.01  (spokojny)
Chorus:  eq=saturation=1.10:contrast=1.18:brightness=0.0   (energetyczny)
Bridge:  eq=saturation=0.80:contrast=1.25:brightness=-0.02 (dramatyczny)
Intro:   eq=saturation=0.85:contrast=1.05:brightness=0.02  (delikatny)
Outro:   eq=saturation=0.82:contrast=1.03:brightness=0.01  (wyciszenie)

Implementacja w assembler.py:
Każdy klip dostaje swój eq filter przez MoviePy image_transform()
zanim zostanie złączony z resztą.

def apply_section_grade(clip, section):
    grades = {
        'verse':  (0.88, 1.08, 0.01),
        'chorus': (1.10, 1.18, 0.0),
        'bridge': (0.80, 1.25, -0.02),
        'intro':  (0.85, 1.05, 0.02),
        'outro':  (0.82, 1.03, 0.01),
    }
    sat, cont, bright = grades.get(section, (0.92, 1.10, 0.0))
    def grade_frame(frame):
        # Brightness
        f = frame.astype(float) + bright * 255
        # Contrast
        f = (f - 128) * cont + 128
        # Saturation przez HSV
        import cv2
        f = np.clip(f, 0, 255).astype(np.uint8)
        hsv = cv2.cvtColor(f, cv2.COLOR_RGB2HSV).astype(float)
        hsv[:,:,1] *= sat
        hsv = np.clip(hsv, 0, 255).astype(np.uint8)
        return cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)
    return clip.image_transform(grade_frame)

## Problem 5 — Global LUT przez FFmpeg na końcu (szybko)

Po złożeniu całego wideo przez MoviePy:
Przepuść przez FFmpeg z globalnym LUT jako ostatni krok:

def apply_global_lut(input_path, output_path, color_grade):
    lut_filters = {
        'worship-warm': "curves=r='0/0 0.3/0.28 0.7/0.75 1/1':g='0/0 0.3/0.29 0.7/0.72 1/0.97':b='0/0.05 0.3/0.32 0.7/0.68 1/0.92',eq=saturation=0.92:contrast=1.12",
        'teal-orange':  "curves=r='0/0 0.5/0.58 1/1':g='0/0 0.5/0.50 1/0.96':b='0/0.08 0.5/0.45 1/0.88',eq=saturation=1.05:contrast=1.15",
        'bleach':       "eq=saturation=0.75:contrast=1.30:brightness=-0.01",
        'natural':      "eq=saturation=0.95:contrast=1.05",
    }
    vf = lut_filters.get(color_grade, lut_filters['worship-warm'])

    cmd = [
        'ffmpeg', '-i', input_path,
        '-vf', vf,
        '-c:v', 'libx264', '-preset', 'fast',
        '-c:a', 'copy',  # audio bez re-encodingu
        '-y', output_path
    ]
    subprocess.run(cmd, check=True)

Gdy FFmpeg LUT fail: użyj oryginału (fallback — nie crashuj).

## Acceptance Criteria
- Pełny teledysk i rolki mają ten sam domyślny LUT worship-warm
- Brak duplikatów filmów Pexels w jednym run
- Rolki mają slide-up/slide-left/wipe przejścia (nie tylko fade)
- Zoom punch na downbeat refrenu dla rolek
- Gradient overlay dolny dla rolek
- Per-sekcja color grade (chorus jaśniejszy niż verse)
- Global LUT przez FFmpeg na końcu każdego eksportu
- python3 -m pytest tests/ -v przechodzi
