# Idea

# Spec: Naprawa core pipeline — synchronizacja, cache, rytm, trafność zdjęć

## Problem 1 — --new nie czyści cache zdjęć

Obecny --new kasuje scene_plan.json ale nie kasuje scene_NNN.jpg.
Assembler używa starych zdjęć mimo że BFL wygenerował nowe.

Napraw w musicvid.py gdy --new=True:
Usuń WSZYSTKIE pliki z cache_dir przed startem pipeline:
  if new and cache_dir.exists():
      for f in cache_dir.iterdir():
          if f.is_file():
              f.unlink()
      print(f"Cache wyczyszczony: {cache_dir}")

Usuń w szczególności:
  scene_NNN.jpg / scene_NNN.png
  animated_scene_NNN.mp4
  scene_plan.json
  audio_analysis.json
  video_manifest.json

## Problem 2 — synchronizacja tekstu

Whisper zwraca timestamps ale assembler nakłada napisy w złym czasie.
Sprawdź i napraw w assembler.py:

Napisy muszą być nakładane względem LOKALNEGO czasu klipu sceny
a nie globalnego czasu piosenki.

Gdy scena zaczyna się o t=44s a napis ma start=44.5s:
  lokalny_start = 44.5 - 44.0 = 0.5s  ← POPRAWNE
  nie używaj: start=44.5s na klipie który zaczyna się od 0

Sprawdź czy txt_clip.with_start() używa czasu lokalnego czy globalnego.
Jeśli globalnego — odejmij scene["start"] od każdego napisu.

Dodatkowo: napisy powinny pojawiać się 0.1s PRZED faktycznym słowem
żeby widz zdążył przeczytać. Odejmij 0.1s od każdego start.

## Problem 3 — brak rytmu i za długie sceny

Sceny są za długie i nie są cięte na beat.
Obecna implementacja beat_sync nie działa.

Napraw podział scen w director.py:
Claude dostaje BPM i beat_times ale nie używa ich do planowania długości scen.

Dodaj do promptu Claude-reżysera:
"BPM piosenki: {bpm}
Czas jednego taktu (4 beaty): {bar_duration:.2f}s
Dostępne downbeaty (co 4. beat): {downbeats_list}

ZASADY DŁUGOŚCI SCEN:
- Minimalna długość sceny: 2 takty = {bar_duration*2:.2f}s
- Optymalna długość: 4 takty = {bar_duration*4:.2f}s
- Maksymalna długość: 8 taktów = {bar_duration*8:.2f}s
- Każda scena MUSI zaczynać się i kończyć na downbeat z listy
- Dla BPM={bpm} optymalna scena trwa {bar_duration*4:.1f}s"

Po otrzymaniu planu scen od Claude:
Snapnij każdy scene["start"] i scene["end"] do najbliższego downbeatu
w oknie ±0.5s. To zapewni że cięcia trafią w rytm nawet jeśli
Claude nie idealnie trafił w downbeat.

Implementacja snap_to_downbeat:
  def snap_to_downbeat(t, downbeats, window=0.5):
      candidates = [d for d in downbeats if abs(d - t) <= window]
      if candidates:
          return min(candidates, key=lambda d: abs(d - t))
      return t

## Problem 4 — zdjęcia nie pasują do treści

Claude-reżyser generuje zbyt ogólne prompty niezwiązane z tekstem.

Zmień prompt w director.py — dla każdej sceny Claude MUSI:
1. Przytoczyć konkretną linijkę tekstu która pojawia się w tej scenie
2. Wyjaśnić metaforę wizualną nawiązującą DO TEKSTU
3. Visual prompt MUSI nawiązywać do słów piosenki

Dodaj do promptu Claude:
"Dla każdej sceny:
- Pole 'lyrics_in_scene': lista linijek tekstu które pojawią się w tej scenie
- Visual prompt MUSI nawiązywać do metafory lub obrazu z tych linijek
- NIE generuj ogólnych krajobrazów — generuj obrazy które ilustrują SŁOWA

Przykład dobrego promptu dla linijki 'Tylko w Bogu jest moja dusza':
'A single human silhouette standing on vast rocky cliff, arms open wide,
golden light streaming from above, vast infinite ocean below, sense of
complete surrender and trust, photorealistic, cinematic 16:9'

Przykład złego promptu (zbyt ogólny):
'Beautiful mountain landscape at golden hour, photorealistic'

Każdy prompt musi być KONKRETNĄ ilustracją tekstu, nie dekoracją."

Dodatkowo: zwiększ max_tokens dla Claude do 8192 żeby JSON nie był ucinany.

## Problem 5 — za mało scen, za długie

Dla 4-minutowej piosenki przy BPM=84:
  bar_duration = 4 * (60/84) = 2.86s
  optymalna scena = 4 takty = 11.4s
  liczba scen = 240s / 11.4s ≈ 21 scen

Obecny kod generuje ~8-15 scen co daje sceny po 20-30s — za długo.
Poinformuj Claude ile scen powinno być:
  suggested_scene_count = int(audio_duration / (bar_duration * 4))
  "Sugerowana liczba scen: {suggested_scene_count} (po ~{bar_duration*4:.1f}s każda)"

## Kolejność napraw

Implementuj w tej kolejności:
1. Naprawa --new (kasowanie całego cache) — krytyczna
2. Naprawa liczby i długości scen (BPM-based) — krytyczna
3. Snapping do downbeatów — ważna
4. Naprawa promptów (tekst → obraz) — ważna
5. Naprawa synchronizacji napisów — ważna

## Testy
- --new: po uruchomieniu brak scene_NNN.jpg starszych niż 1 minuta
- Sceny dla BPM=84: długość każdej sceny ~11s (±3s)
- snap_to_downbeat: każde cięcie w oknie ±0.5s od downbeatu
- Visual prompt zawiera nawiązanie do tekstu sceny
- Napisy zsynchronizowane z Whisper timestamps (offset lokalny)

## Acceptance Criteria
- --new kasuje WSZYSTKIE pliki cache przed regenerowaniem
- Sceny trwają 8-15s (nie 20-30s)
- Cięcia trafiają w downbeat muzyczny
- Każdy visual prompt nawiązuje do tekstu sceny
- Napisy pojawiają się zsynchronizowane z muzyką
- python3 -m pytest tests/ -v przechodzi
