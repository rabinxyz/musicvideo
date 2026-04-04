# Spec: Nakładka logo na wideo (SVG/PNG) — rynkowy standard pozycjonowania

## Cel
Dodać możliwość nałożenia logo na wideo z profesjonalnym marginesem
opartym na proporcji do rozdzielczości (standard Netflix, YouTube, BBC).

## Nowe flagi CLI
--logo PATH                                                     (opcjonalna)
--logo-position [top-left|top-right|bottom-left|bottom-right]   (domyślnie: top-left)
--logo-size INT       szerokość w px, domyślnie: auto (12% szerokości kadru)
--logo-opacity FLOAT  domyślnie: 0.85

## Standard rynkowy — safe zone margin

Margines = 5% krótszego wymiaru kadru (broadcast action safe zone):
  margin = int(min(frame_width, frame_height) * 0.05)

Przykłady:
  1920x1080 → margin = 54px
  1080x1920 → margin = 54px
  1080x1080 → margin = 54px
  3840x2160 → margin = 108px

Margines jest identyczny ze wszystkich stron i dla wszystkich orientacji.
Skaluje się automatycznie dla każdej rozdzielczości.

## Rozmiar logo — auto skalowanie

Gdy --logo-size nie podane (tryb auto):
  logo_width = int(frame_width * 0.12)

Przykłady trybu auto:
  1920x1080 → logo 230px szeroki
  1080x1920 → logo 130px szeroki
  1080x1080 → logo 130px szeroki

Gdy --logo-size podane: użyj wartości bezwzględnej w px.
Wysokość zawsze skalowana proporcjonalnie do szerokości.

## Pozycjonowanie (lewy górny róg logo)

top-left     → x=margin,                       y=margin
top-right    → x=width - logo_width - margin,  y=margin
bottom-left  → x=margin,                       y=height - logo_height - margin
bottom-right → x=width - logo_width - margin,  y=height - logo_height - margin

Domyślnie: top-left

## Obsługa formatów

SVG:
Konwertuj przez cairosvg do PNG przed użyciem.
Renderuj w rozmiarze logo_width × logo_height × 2 (retina DPI),
potem skaluj w dół — zapewnia ostrość krawędzi wektorowych.
Zachowaj przezroczyste tło RGBA.

PNG/JPG:
Wczytaj przez Pillow, przeskaluj do logo_width zachowując proporcje.
Zachowaj kanał alpha jeśli istnieje.

Wykryj format po rozszerzeniu pliku (.svg vs .png/.jpg).
Jeśli SVG i brak cairosvg: spróbuj svglib, jeśli oba niedostępne
rzuć błąd z instrukcją: "pip install cairosvg"

## Opacity

Zastosuj przez Pillow putalpha przed przekazaniem do MoviePy:
  alpha = int(255 * logo_opacity)
  image.putalpha(alpha)

Domyślna opacity 0.85 — logo widoczne ale nie dominuje nad treścią.

## Kolejność warstw

Logo nakładane jako ostatnia warstwa — nad wszystkim:
1. Obraz/video z Ken Burns
2. Efekty (warm grade, vignette, film grain)
3. Napisy
4. Cinematic bars
5. Logo ← na samym wierzchu

Logo widoczne przez cały czas trwania klipu.

## Nowy moduł musicvid/pipeline/logo_overlay.py

Funkcje:
- compute_margin(frame_width, frame_height) -> int
  Zwraca int(min(w, h) * 0.05)

- compute_logo_size(frame_width, frame_height, requested_size=None) -> (int, int)
  Gdy requested_size None: logo_width = int(frame_width * 0.12)
  Wysokość skalowana proporcjonalnie z oryginalnego obrazu.
  Zwraca (logo_width, logo_height).

- load_logo(path, logo_width, logo_height, opacity) -> PIL.Image (RGBA)
  Obsługuje SVG i PNG/JPG.
  Stosuje opacity przez putalpha.
  Zwraca obraz gotowy do nałożenia.

- get_logo_position(position, logo_size, frame_size) -> (x, y)
  Oblicza współrzędne używając compute_margin.
  position: "top-left" | "top-right" | "bottom-left" | "bottom-right"

- apply_logo(clip, logo_path, position, size, opacity) -> clip
  Główna funkcja łącząca powyższe.
  Zwraca MoviePy clip z logo nałożonym przez ImageClip + with_position().

## requirements.txt — dodaj
cairosvg>=2.7.0

## Testy
- compute_margin(1920, 1080) == 54
- compute_margin(1080, 1920) == 54
- compute_margin(3840, 2160) == 108
- compute_logo_size(1920, 1080, None) == (230, proporcjonalna_wysokość)
- compute_logo_size(1920, 1080, 200) == (200, proporcjonalna_wysokość)
- get_logo_position("top-left", ...) → x==54, y==54 dla 1920x1080
- get_logo_position("top-right", ...) → x==width-logo_width-54, y==54
- get_logo_position("bottom-right", ...) → poprawne współrzędne
- load_logo SVG: zwraca PIL Image RGBA
- load_logo PNG: zwraca PIL Image RGBA
- opacity 0.85 → alpha channel == 216
- Brak pliku logo: FileNotFoundError z czytelnym komunikatem
- Brak cairosvg dla SVG: ImportError z instrukcją instalacji

## Acceptance Criteria
- --logo logo.svg nakłada logo w lewym górnym rogu z marginesem 54px dla 1920x1080
- Margines 5% skaluje się automatycznie dla każdej rozdzielczości
- Logo auto-skaluje się do 12% szerokości kadru gdy --logo-size nie podane
- --logo-position zmienia pozycję
- --logo-size nadpisuje auto skalowanie
- --logo-opacity zmienia przezroczystość
- SVG i PNG obsługiwane
- Logo nad wszystkimi warstwami przez cały czas klipu
- Działa dla wszystkich platform: youtube, reels, square
- python3 -m pytest tests/ -v przechodzi
