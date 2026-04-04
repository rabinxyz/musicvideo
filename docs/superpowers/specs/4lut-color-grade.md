# Spec: LUT (Look Up Table) — cinematyczny color grade

## Cel
Dodać profesjonalną korektę kolorów przez LUT do każdego wideo.
LUT to plik .cube który mapuje kolory wejściowe na wyjściowe —
ten sam standard używany w Hollywood i przez profesjonalnych
twórców teledysków.

## Nowa flaga CLI
--lut PATH   Ścieżka do pliku .cube z LUT (opcjonalna)
--lut-style [warm|cold|cinematic|natural|faded]  (domyślnie: warm)
             Wbudowany LUT gdy --lut nie podane

## Wbudowane LUT style

Gdy --lut nie podane, użyj wbudowanego LUT generowanego przez kod:

### warm (domyślny — rekomendowany dla worship music)
Shadows: lekki shift w kierunku amber/brąz
Midtones: ocieplenie, boost żółtego i pomarańczowego
Highlights: delikatny cream/ivory zamiast czystej bieli
Kontrast: lekko podniesiony (+10%)
Nasycenie: lekko obniżone (-8%) — bardziej filmowy look
Efekt: ciepły, intymny, jak filmy A24

### cinematic
Shadows: lift do ciemnoszarego (nie czarny — typowy dla kina)
Midtones: lekka desaturacja, shift w chłodny kierunek
Highlights: rolloff — nie przepalone, miękkie przejście
Kontrast: S-curve — głębsze cienie, jaśniejsze środki
Nasycenie: -15% dla filmowego, mniej nasycenia look
Efekt: jak współczesny film fabularny

### cold
Shadows: shift w niebieski
Midtones: chłodny, niebieskoszary
Highlights: biały z lekkim błękitem
Efekt: nowoczesny, kontemplacyjny

### natural
Minimalne zmiany — tylko łagodny kontrast i lekki lift cieni
Zachowuje naturalne kolory bez wyraźnego grade
Efekt: czyste, realistyczne

### faded
Klasyczny faded film look
Lift czarnych (cienie nie są czarne, tylko ciemnoszare)
Obniżone nasycenie -20%
Delikatne ocieplenie
Efekt: vintage, artystyczny

## Jak zaimplementować LUT

### Opcja A — plik .cube (gdy --lut podane)
Format .cube to standard branżowy — tekstowy plik z tabelą 3D mapowania RGB.
Wczytaj przez bibliotekę colour-science lub własny parser.
Zastosuj na każdej klatce przez numpy interpolację 3D.

### Opcja B — wbudowany LUT (gdy --lut-style)
Generuj LUT programowo przez numpy jako tablicę 3D (33x33x33 punkty).
Zastosuj transformacje kolorów matematycznie na tablicy LUT.
Aplikuj przez trilinear interpolation na każdej klatce.

### Implementacja przez FFmpeg (rekomendowana — szybsza)
Zamiast przetwarzać przez Python frame-by-frame (wolno),
przekaż LUT do FFmpeg jako filter przy eksporcie:

Dla pliku .cube:
  ffmpeg_params=["-vf", f"lut3d={lut_path}"]

Dla wbudowanego LUT: zapisz tymczasowo do pliku .cube w tmp/
i przekaż do FFmpeg tak samo.

FFmpeg obsługuje lut3d natively — to najszybsze podejście.

## Kolejność zastosowania

LUT aplikowany jest jako ostatni krok korekty kolorów:
1. Ken Burns / ruch
2. Warm grade (podstawowe ocieplenie z efektów)
3. Vignette
4. Napisy i logo
5. Cinematic bars
6. LUT ← na samym końcu przez FFmpeg przy eksporcie

LUT powinien być stosowany PO wszystkich innych efektach —
to standard w postprodukcji (grade na końcu pipeline'u).

## Intensywność LUT
--lut-intensity FLOAT  (domyślnie: 0.85, zakres 0.0-1.0)
Blend między oryginalnym kolorem (0.0) a pełnym LUT (1.0).
0.85 daje subtelny profesjonalny efekt bez przesady.

Implementacja przez FFmpeg:
  f"lut3d={lut_path}:interp=trilinear,blend=all_opacity={intensity}"

## Nowy moduł musicvid/pipeline/color_grade.py

Funkcje:
- generate_builtin_lut(style, size=33) -> numpy.ndarray
  Generuje tablicę LUT 33x33x33x3 dla danego stylu.
  Zapisuje do tmp/ jako plik .cube.
  Zwraca ścieżkę do pliku .cube.

- load_lut_file(path) -> str
  Waliduje że plik istnieje i ma rozszerzenie .cube.
  Zwraca ścieżkę (FFmpeg wczyta sam).

- get_ffmpeg_lut_filter(lut_path, intensity) -> str
  Zwraca string filtru FFmpeg dla lut3d.

- apply_lut_to_export(clip, lut_path, intensity) -> ffmpeg_params
  Zwraca parametry do przekazania MoviePy write_videofile jako
  ffmpeg_params aby LUT był aplikowany przez FFmpeg przy eksporcie.

## Gdzie użyć w pipeline

W assembler.py przy wywołaniu write_videofile:
  Pobierz ffmpeg_params z color_grade.apply_lut_to_export()
  Przekaż jako dodatkowy parametr do write_videofile()

## Gotowe darmowe pliki .cube dla użytkownika

Dodaj do README.md sekcję z linkami do darmowych LUT:
- https://luts.iwltbap.com (darmowe kinowe LUT)
- https://www.rocketstock.com/free-after-effects-templates/35-free-luts/
- Filmic Pro LUT Pack (darmowy)

## requirements.txt — dodaj
colour-science>=0.4.0   (opcjonalne — do parsowania .cube)

## Testy
- generate_builtin_lut("warm"): zwraca tablicę 33x33x33x3
- generate_builtin_lut("cinematic"): wartości różne od "warm"
- load_lut_file: waliduje rozszerzenie .cube
- load_lut_file nieistniejący plik: FileNotFoundError
- get_ffmpeg_lut_filter: zwraca string zawierający "lut3d"
- --lut-intensity 0.5: intensity w filtrze FFmpeg == 0.5

## Acceptance Criteria
- --lut-style warm generuje wideo z ciepłym cinematycznym grade
- --lut-style cinematic generuje wideo z filmowym look
- --lut plik.cube stosuje zewnętrzny LUT
- --lut-intensity 0.5 zmniejsza intensywność efektu
- LUT aplikowany przez FFmpeg (nie frame-by-frame Python)
- Czas generowania nie wzrasta o więcej niż 10% (FFmpeg jest szybki)
- Działa dla wszystkich platform: youtube, reels, square
- python3 -m pytest tests/ -v przechodzi
