# Spec: Efekty wizualne dla obrazów AI

## Cel
Dodać estetyczne efekty wizualne do generowanych obrazów w assembler.py,
które nadadzą teledyskowi profesjonalny, kinowy look typowy dla
współczesnych teledysków chrześcijańskich.

## Nowa flaga CLI
--effects [none|minimal|full]  (domyślnie: minimal)

none    — tylko Ken Burns, bez żadnych efektów
minimal — warm grade + vignette + cinematic bars (rekomendowane)
full    — minimal + film grain + light leak

## Efekty do zaimplementowania

### 1. Warm grade (obowiązkowy w minimal i full)
Lekkie ocieplenie kolorów całego obrazu.
Zwiększ kanał R o 15, kanał G o 5, kanał B zmniejsz o 10.
Clamp wartości do 0-255.
Implementacja: numpy na każdej klatce przez transform() MoviePy.

### 2. Vignette (obowiązkowy w minimal i full)
Przyciemnienie krawędzi kadru, skupia oko na centrum.
Gaussowska maska ciemności — centrum jasne, krawędzie przyciemnione o 40%.
Rozmiar: dopasowany do rozdzielczości klipu.
Implementacja: numpy maska nałożona na każdą klatkę przez transform().

### 3. Cinematic bars (obowiązkowy w minimal i full)
Czarne pasy góra i dół symulujące format 2.35:1.
Wysokość pasa: 12% wysokości klipu każdy (góra i dół).
Implementacja: ColorClip czarny z with_position() nałożony przez
CompositeVideoClip na gotowy klip.
Napisy muszą być renderowane PRZED nałożeniem pasów — żeby pasy
przykryły ewentualne napisy wychodzące poza bezpieczną strefę.

### 4. Film grain (tylko full)
Subtelne ziarno filmowe dodające tekstury.
Losowy szum gaussowski, sigma=8, nałożony z opacity 0.15.
Generuj nową warstwę szumu dla każdej klatki (animowane ziarno).
Implementacja: numpy random na każdej klatce przez transform().

### 5. Light leak (tylko full)
Jeden rozbłysk światła przechodzący przez kadr w trakcie sceny.
Gradient pomarańczowo-złoty, opacity 0.2, animowany przez czas trwania sceny.
Pojawia się raz na scenę — w losowym momencie między 20% a 60% czasu sceny.
Przemieszcza się z lewej do prawej lub z prawej do lewej (losowo).
Implementacja: ImageClip z gradientem numpy + with_start/with_end + with_position().

## Kolejność nakładania efektów na klip

1. Załaduj obraz (ImageClip) lub wideo (VideoFileClip)
2. Zastosuj Ken Burns (transform)
3. Zastosuj warm grade (transform na każdej klatce)
4. Zastosuj vignette (transform na każdej klatce)
5. Nałóż light leak jeśli full (CompositeVideoClip)
6. Nałóż napisy (CompositeVideoClip)
7. Nałóż cinematic bars (CompositeVideoClip)
8. Zastosuj film grain jeśli full (transform na każdej klatce)

## Gdzie zaimplementować
Nowy plik: musicvid/pipeline/effects.py
Eksportuje funkcje:
- apply_warm_grade(clip) -> clip
- apply_vignette(clip) -> clip
- apply_film_grain(clip) -> clip
- create_light_leak(duration, size) -> clip
- create_cinematic_bars(width, height, duration) -> clip
- apply_effects(clip, level="minimal") -> clip
  (level: "none" | "minimal" | "full")

W assembler.py zaimportuj apply_effects i wywołaj po Ken Burns
a przed napisami, przekazując poziom efektów z parametru CLI.

## Wydajność
Efekty numpy są kosztowne dla długich klipów.
Ogranicz transform() do rozdzielczości roboczej (max 1080p) —
finalne skalowanie robi FFmpeg przy eksporcie.
Film grain i light leak są opcjonalne (tylko --effects full) właśnie
ze względu na czas renderowania.

## Testy
- apply_warm_grade: kanał R większy, B mniejszy po zastosowaniu
- apply_vignette: piksele na krawędziach ciemniejsze niż centrum
- apply_effects "none": klip niezmieniony
- apply_effects "minimal": warm grade + vignette + bars zastosowane
- apply_effects "full": wszystkie efekty zastosowane
- create_cinematic_bars: zwraca klip o poprawnych wymiarach

## Acceptance Criteria
- --effects minimal generuje wideo z ciepłymi kolorami, vignette i pasami
- --effects full dodaje grain i light leak
- --effects none wideo bez żadnych dodatkowych efektów
- Napisy są widoczne nad pasami (renderowane przed pasami)
- Czas generowania dla --effects minimal nie wydłuża się o więcej niż 30%
- python3 -m pytest tests/ -v przechodzi
