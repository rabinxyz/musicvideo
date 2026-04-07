# Spec: Balans efektów — mniej migania, więcej klasy

## Problem
Za dużo efektów jednocześnie powoduje chaos wizualny na rolkach:
- zoom punch + light flash + dynamic grade + WOW wszystko naraz = miganie
- Efekty kolidują ze sobą
- Wygląda amatorsko zamiast profesjonalnie

## Zasada: jeden mocny efekt na raz

Profesjonalne teledyski używają JEDNEGO dominującego efektu per moment.
Nie stackują wszystkiego naraz.

## Nowa hierarchia efektów

### Poziom NONE (brak efektów)
  Czyste wideo, tylko LUT kolorystyczny
  Dla: intro, outro, spokojne verse

### Poziom SUBTLE (subtelne)
  LUT worship-warm + vignette
  Bez zoom punch, bez flash
  Dla: verse, bridge

### Poziom DYNAMIC (dynamiczne)
  LUT + vignette + zoom punch (0.05 scale max) LUB light flash
  NIGDY oba naraz
  Wybór: zoom punch dla scen z ruchem, flash dla statycznych
  Dla: chorus

### Poziom PEAK (szczyt)
  Tylko dla PIERWSZEGO wejścia refrenu i kulminacji bridge
  LUT + zoom punch 0.08 scale + jeden flash
  Maksymalnie 2x przez cały teledysk

## Konkretne zmiany w wow_effects.py

### zoom_punch — zmniejsz intensywność
  Stary: scale 1.0 → 1.12 (za agresywny)
  Nowy:  scale 1.0 → 1.05 (subtelny, profesjonalny)
  Czas animacji: 3 klatki in, 12 klatek out (łagodniejszy powrót)

### light_flash — ogranicz do 2x per teledysk
  Obecny: każde wejście refrenu
  Nowy: tylko pierwsze i ostatnie wejście refrenu
  Opacity: max 0.4 (nie 0.7 — za jasne)
  Czas: 0.08s peak, 0.4s zanik (wolniejszy)

### dynamic_grade — płynne przejście między sekcjami
  Obecny: skokowa zmiana verse→chorus
  Nowy: interpolacja 1s między paletami (nie skokowa zmiana)
  Różnica saturacji: verse=0.88 vs chorus=1.05 (nie 1.15 — za duże)

### WOW flag — wyłącz domyślnie dla rolek
  Rolki 9:16 mają już zoom punch z blur-bg composite
  Dodatkowy WOW jest za dużo
  Gdy platform==reels/shorts: --wow automatycznie wyłączone
  Chyba że użytkownik jawnie poda --wow

## Nowy domyślny preset efektów

Zamiast wszystkich flag osobno — jeden spójny preset:

--effects-preset [clean|subtle|dynamic|wow]

clean:   tylko LUT worship-warm, zero efektów ruchu
         Dla minimalistycznego profesjonalnego look

subtle:  LUT + vignette + zoom punch 1.05 na chorus
         REKOMENDOWANY DEFAULT dla pełnego teledysku

dynamic: subtle + light flash (2x max) + section grade
         Dla energetycznych pieśni (joyful/powerful)

wow:     dynamic + particles + agresywniejszy zoom
         Dla specjalnych produkcji — nie default

Gdy --effects-preset podane: ignoruj osobne --zoom-punch, --light-flash itd.

## Dla rolek (9:16) osobny preset

Rolki mają inne potrzeby niż pełny teledysk:
- Szybsze tempo (widz scrolluje)
- Mocniejszy hook w pierwszych 2s
- Ale NIE miganie — to wygląda tanio

Domyślny preset dla rolek: "reel-pro"
  blur-bg composite (już działa)
  LUT worship-warm lekko mocniejszy (lut-intensity=0.95)
  gradient overlay dolny (czytelność napisów)
  zoom punch 1.04 na downbeat (subtelny)
  BEZ light flash
  BEZ particles
  Napisy font_size+10 większe niż w pełnym filmie

## Konkretne wartości do zmiany w kodzie

W wow_effects.py:
  ZOOM_PUNCH_SCALE = 1.05          # było 1.12
  ZOOM_PUNCH_IN_FRAMES = 3         # bez zmian
  ZOOM_PUNCH_OUT_FRAMES = 15       # było 8 (wolniejszy powrót)
  FLASH_MAX_OPACITY = 0.35         # było 0.7
  FLASH_PEAK_TIME = 0.06           # było 0.05
  FLASH_FADE_TIME = 0.5            # było 0.3 (wolniejszy zanik)
  MAX_FLASHES_PER_VIDEO = 2        # nowe ograniczenie
  DYNAMIC_GRADE_TRANSITION = 1.0   # sekundy interpolacji między sekcjami
  CHORUS_SATURATION = 1.05         # było 1.10-1.15
  VERSE_SATURATION = 0.90          # było 0.88

W assembler.py dla rolek:
  Gdy platform in ['reels', 'shorts', 'tiktok']:
      wow = False           # wyłącz WOW
      light_flash = False   # wyłącz flash
      zoom_punch_scale = 1.04  # subtelniejszy
      lut_intensity = 0.95     # lekko mocniejszy kolor

## Testy
- zoom_punch_scale == 1.05 (nie 1.12)
- MAX_FLASHES_PER_VIDEO == 2 w całym teledysku
- Rolki: wow=False, light_flash=False automatycznie
- dynamic_grade przejście interpolowane (nie skokowe)
- flash_opacity <= 0.35

## Acceptance Criteria
- Rolki nie migają
- Zoom punch subtelny ale zauważalny (1.05)
- Light flash max 2x przez cały teledysk
- Płynne przejście color grade między sekcjami
- Pełny teledysk: subtle preset domyślnie
- Rolki: reel-pro preset domyślnie (bez WOW)
