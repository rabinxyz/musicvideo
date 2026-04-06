# Spec: WOW efekty — CapCut style, dynamika, energia

## Cel
Teledysk ma robić wrażenie. Nie "ok" — WOW.
Wzorzec: profesjonalne lyric video Hillsong, Elevation Worship, Bethel Music.
Narzędzie: FFmpeg filtry (szybkie, nie frame-by-frame Python).

## Efekt 1 — Energy-reactive cuts (cięcia na peak energii)

Obecny problem: cięcia co równe odcinki — monotonia.
Rozwiązanie: wykryj momenty peak energii w audio i tnij tam.

W audio_analyzer.py dodaj energy_peaks:
  onset_env = librosa.onset.onset_strength(y=y, sr=sr)
  peaks = librosa.util.peak_pick(onset_env, pre_max=3, post_max=3,
                                  pre_avg=3, post_avg=5, delta=0.5, wait=10)
  peak_times = librosa.frames_to_time(peaks, sr=sr)
  analysis["energy_peaks"] = [float(t) for t in peak_times]

Użyj peak_times jako preferowane punkty cięcia w director.py.
Sceny MUSZĄ zaczynać się i kończyć na nearest peak (±0.3s).

## Efekt 2 — Zoom punch na beat (CapCut signature)

Na każdym mocnym uderzeniu (downbeat refrenu):
Szybki zoom in 1.0 → 1.08 w ciągu 0.1s potem powrót 1.08 → 1.0 w 0.3s.
Efekt "uderzenia" zsynchronizowany z muzyką.

Implementacja przez FFmpeg zoompan filter:
  Dla każdego downbeat w refrenie dodaj:
  zoompan=z='if(between(t,{t},{ t+0.1}),1+0.08*((t-{t})/0.1),
             if(between(t,{t+0.1},{t+0.4}),1.08-0.08*((t-{t+0.1})/0.3),1))'

Stosuj TYLKO przy refrenie — nie przy zwrotce (zbyt agresywne).
Maksymalnie na co 2. downbeat żeby nie przesadzić.

## Efekt 3 — Color grade reaktywny na energię

Dwie palety kolorów przełączające się zależnie od energii sekcji:

Paleta VERSE (spokojna, ciepła):
  Lekko desaturowana, ciepły amber, subtelna
  FFmpeg: eq=saturation=0.85:brightness=0.02:contrast=1.05,
          colorbalance=rs=0.05:gs=0.02:bs=-0.03

Paleta CHORUS (dynamiczna, intensywna):
  Wyższy kontrast, żywsze kolory, bardziej nasycona
  FFmpeg: eq=saturation=1.15:brightness=0.0:contrast=1.15,
          colorbalance=rs=0.08:gs=0.03:bs=-0.05

Przejście między paletami: 0.5s cross-fade żeby nie było skoku.

## Efekt 4 — Light flash na pierwsze uderzenie refrenu

Przy pierwszym uderzeniu każdego refrenu:
Błysk białego światła który znika w 0.3s.
Efekt "wejście w refren" — bardzo popularny w worship music.

Implementacja: nakładka białego ColorClip z opacity:
  t=0: opacity 0
  t=0.05s: opacity 0.7 (peak flash)
  t=0.3s: opacity 0 (zanika)

Tylko raz per refren — nie na każdym uderzeniu.

## Efekt 5 — Motion blur na szybkich cięciach

Przy cut transitions (verse→chorus):
Dodaj motion blur 0.05s przed i po cięciu.
Efekt: cięcie wygląda bardziej kinowo, mniej twardo.

FFmpeg: minterpolate z motion blur na 2 klatki przed/po cięciu.
Alternatywnie: krótki zoom 1.0→1.03 na ostatniej klatce przed cięciem.

## Efekt 6 — Vignette dynamiczny

Obecny vignette: stały przez cały film.
Nowy: vignette intensywniejszy przy spokojnych momentach,
      słabszy przy energetycznych (więcej przestrzeni, więcej oddechu).

  VERSE: vignette sigma=0.6 (mocniejszy, intymny)
  CHORUS: vignette sigma=0.3 (słabszy, otwarty, energetyczny)

FFmpeg vignette filter z parametrami per sekcja.

## Efekt 7 — Tekst animowany CapCut style

Zamiast prostego fade dla napisów przy refrenie:

Efekt SCALE POP:
  Napis wjeżdża z scale 1.3 → 1.0 w 0.15s (pop effect)
  Jednocześnie opacity 0 → 1 w 0.15s

Efekt SLIDE UP z bounce:
  Napis wjeżdża z dołu, overshoots o 5px, wraca na miejsce
  Czas: 0.2s wejście + 0.05s bounce

Implementacja przez ASS subtitle format (już mamy):
  Chorus: {\t(0,150,\fscx130\fscy130\alpha&HFF&)
           \t(0,150,\fscx100\fscy100\alpha&H00&)} text
  Verse: standardowy fade

## Efekt 8 — Rolki EXTRA dynamiczne (9:16)

Dla rolek social media dodaj:
- Szybsze cięcia (2x krótsze sceny niż w pełnym filmie)
- Hook w pierwszych 2s: najlepszy moment z refrenu + flash
- Tekst większy i bardziej agresywny (font_size=72 dla chorus)
- Gradient overlay na dole (czarny 60% opacity) pod napisami
- Efekt zoom punch na każdym downbeat (agresywniejszy niż film)

## Efekt 9 — Cinematic LUT zamiast prostego warm grade

Zamiast ręcznego warm grade użyj prawdziwego LUT filmowego.
Generuj LUT programowo który symuluje popularne filmowe look:

"Teal and Orange" (standard Hollywood):
  Shadows: shift w kierunku teal (#008080)
  Highlights: shift w kierunku orange (#FF8C00)
  Midtones: lekko desaturowane

"Bleach Bypass" (kontrast + desaturacja):
  Kontrast +20%, saturacja -25%
  Zimne shadows, ciepłe highlights

Wybór LUT przez Claude-reżysera per overall_style:
  contemplative → Teal and Orange (ciepły, filmowy)
  worship → Warm Golden (amber shadows, cream highlights)
  powerful → Bleach Bypass (dramatyczny, kontrastowy)
  joyful → Vibrant (lekko nasycony, jasny)

## Efekt 10 — Particles overlay

Na klipach TYPE_AI i TYPE_ANIMATED dodaj subtelne particles:
Małe białe/złote punkty unoszące się powoli w górę.
Opacity: 0.15 — ledwo widoczne ale dodają "magic touch".

Implementacja: generuj particles jako numpy array overlay
lub użyj gotowego particles video z Pexels jako multiply blend.

## Implementacja — kolejność

1. Energy peaks w audio_analyzer (baza dla wszystkiego)
2. Zoom punch na downbeat refrenu (największy WOW efekt)
3. Light flash na wejście refrenu
4. Color grade reaktywny (verse vs chorus)
5. Cinematic LUT per styl
6. Tekst animowany CapCut style (scale pop)
7. Dynamiczny vignette
8. Motion blur na cięciach
9. Rolki extra dynamiczne
10. Particles overlay (opcjonalne)

## Nowa flaga CLI
--wow    Włącza wszystkie WOW efekty naraz (zoom punch, flash, dynamic grade)
         Domyślnie: włączone gdy --effects minimal lub full

## Nowe flagi szczegółowe
--zoom-punch [on|off]     domyślnie: on
--light-flash [on|off]    domyślnie: on
--dynamic-grade [on|off]  domyślnie: on
--particles [on|off]      domyślnie: off (droższe obliczeniowo)

## Implementacja techniczna

Wszystkie efekty przez FFmpeg filtry (nie Python frame-by-frame):
  Szybciej: FFmpeg jest ~20x szybszy niż MoviePy dla efektów per-frame
  Jakość: lepsza niż numpy manipulacje

Nowy moduł: musicvid/pipeline/wow_effects.py
  build_ffmpeg_filter_chain(analysis, scene_plan, effects_config) -> str
  Zwraca string filter_complex dla FFmpeg z wszystkimi efektami.

Integracja w assembler.py:
  Po złączeniu wszystkich scen przez MoviePy:
  Wywołaj FFmpeg z filter_chain na gotowym pliku MP4.
  Finalny output = MoviePy MP4 → FFmpeg WOW effects → gotowy plik.

## Testy
- energy_peaks: lista float z wartościami w zakresie 0 do duration
- zoom_punch: klatki przy downbeat mają zoom > 1.0
- light_flash: klatka przy wejściu chorus ma wyższy brightness
- color_grade: klatki chorus mają wyższy kontrast niż verse
- Czas generowania: nie wzrasta o więcej niż 30% (FFmpeg jest szybki)

## Acceptance Criteria
- Wideo ma wyraźne zoom punch przy każdym downbeat refrenu
- Light flash przy wejściu w refren
- Różny color grade dla verse i chorus
- Napisy refrenu mają efekt scale pop
- Rolki mają hook w pierwszych 2s
- Całość wygląda jak profesjonalne worship lyric video
- python3 -m pytest tests/ -v przechodzi
