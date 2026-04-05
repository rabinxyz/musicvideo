# Idea

# Spec 4: Dynamika teledysku — zróżnicowanie długości, ruchów, przejść

## Kontekst i historia problemu

Obecny teledysk jest monotonny bo:
1. Wszystkie sceny mają podobną długość (~równe odcinki)
2. Dominuje slow_zoom_in dla wszystkich scen
3. Wszystkie przejścia są takie same (fade lub cut)
4. Brak poczucia "oddechu" i kulminacji

Dobry teledysk muzyczny ma dynamiczną krzywą napięcia:
intro (spokój) → zwrotka (budowanie) → refren (szczyt) → ...

## Problem 1: Zróżnicowanie długości scen

### Zasada: długość sceny zależy od sekcji i energii

Mapowanie sekcja → docelowa długość (w taktach muzycznych):

  "intro":   6-8 taktów (spokojne, długie)
  "verse":   4-6 taktów (budowanie, średnie)
  "chorus":  2-3 takty (energia, krótkie i dynamiczne)
  "bridge":  4-8 taktów (emocjonalny szczyt, zmienne)
  "outro":   6-10 taktów (wyciszenie, długie)
  default:   4 takty

Dla BPM=84: 1 takt = 4 × (60/84) = 2.86s
  chorus: 2-3 takty = 5.7s - 8.6s (krótkie cięcia!)
  verse:  4-6 taktów = 11.4s - 17.1s
  intro:  6-8 taktów = 17.1s - 22.8s

### Implementacja w director.py

Oblicz przed promptem Claude:
  bar_duration = 4 * (60 / bpm)
  section_lengths = {
      "intro":  (6*bar_duration, 8*bar_duration),
      "verse":  (4*bar_duration, 6*bar_duration),
      "chorus": (2*bar_duration, 3*bar_duration),
      "bridge": (4*bar_duration, 8*bar_duration),
      "outro":  (6*bar_duration, 10*bar_duration),
  }

Dodaj do promptu Claude:
"DŁUGOŚCI SCEN (KRYTYCZNE — stosuj się dokładnie):
BPM={bpm}, jeden takt = {bar_duration:.2f}s

Każda sekcja ma narzuconą długość:
- intro: {section_lengths['intro'][0]:.1f}s - {section_lengths['intro'][1]:.1f}s
- verse: {section_lengths['verse'][0]:.1f}s - {section_lengths['verse'][1]:.1f}s
- chorus: {section_lengths['chorus'][0]:.1f}s - {section_lengths['chorus'][1]:.1f}s (KRÓTKIE = ENERGIA)
- bridge: {section_lengths['bridge'][0]:.1f}s - {section_lengths['bridge'][1]:.1f}s
- outro: {section_lengths['outro'][0]:.1f}s - {section_lengths['outro'][1]:.1f}s

NIE rób równych odcinków. Refren MUSI być krótszy niż zwrotka."

### Post-processing: snap do downbeatów

Po otrzymaniu planu od Claude:
  for scene in scenes:
      scene["start"] = snap_to_downbeat(scene["start"], downbeats, window=0.8)
      scene["end"] = snap_to_downbeat(scene["end"], downbeats, window=0.8)

def snap_to_downbeat(t, downbeats, window=0.8):
    candidates = [(abs(d - t), d) for d in downbeats if abs(d - t) <= window]
    if candidates:
        return min(candidates)[1]
    return t

## Problem 2: Zróżnicowanie ruchów kamery

### Zasada: nigdy dwa razy ten sam ruch pod rząd

Mapowanie sekcja → dozwolone ruchy:
  "intro":  ["static", "slow_zoom_in", "pan_right"]
  "verse":  ["slow_zoom_in", "slow_zoom_out", "pan_left", "pan_right"]
  "chorus": ["slow_zoom_in", "cut_zoom", "pan_left", "pan_right"]
  "bridge": ["slow_zoom_out", "static", "diagonal_drift"]
  "outro":  ["slow_zoom_out", "static"]

### Implementacja

Walidacja po otrzymaniu planu:
  last_motion = None
  for scene in scenes:
      if scene.get("motion") == last_motion:
          # Wybierz inny ruch z dozwolonych dla tej sekcji
          allowed = motion_map.get(scene["section"], ["slow_zoom_in", "pan_left"])
          alternative = [m for m in allowed if m != last_motion]
          if alternative:
              scene["motion"] = alternative[0]
      last_motion = scene["motion"]

### Dodaj nowe typy ruchów w assembler.py

Obecne: slow_zoom_in, slow_zoom_out, pan_left, pan_right, static
Dodaj:
  "diagonal_drift": powolne przesunięcie po skosie (x i y jednocześnie)
  "cut_zoom": szybszy zoom (1.0 → 1.25 zamiast 1.15) dla refrenu

def apply_diagonal_drift(clip, direction="tl_to_br"):
  Przesuwa crop window po skosie przez czas trwania klipu.
  direction: "tl_to_br" (góra-lewo → dół-prawo) lub odwrotnie.

def apply_cut_zoom(clip):
  Agresywniejszy zoom in (1.0 → 1.25) dla dynamicznych scen refrenu.

## Problem 3: Zróżnicowanie przejść

### Mapowanie sekcja→sekcja → typ przejścia

transitions_map = {
    ("intro", "verse"):   "cross_dissolve",  # płynne wejście
    ("verse", "chorus"):  "cut",              # uderzenie w refren
    ("chorus", "verse"):  "fade",             # oddech po refrenie
    ("chorus", "chorus"): "dip_white",        # świetlisty między refrenem
    ("verse", "verse"):   "cross_dissolve",   # płynność w zwrotce
    ("verse", "bridge"):  "cross_dissolve",   # narastanie
    ("bridge", "chorus"): "cut",              # dramatyczne wejście
    ("chorus", "outro"):  "fade",             # wyciszenie
    ("outro", "outro"):   "cross_dissolve",   # spokojne zakończenie
}

default_transition = "cross_dissolve"

### Implementacja

Po snapowaniu scen do downbeatów:
  for i in range(len(scenes) - 1):
      current_section = scenes[i]["section"]
      next_section = scenes[i+1]["section"]
      key = (current_section, next_section)
      scenes[i]["transition_to_next"] = transitions_map.get(key, default_transition)

### Czas trwania przejść zależny od BPM

  beat_duration = 60 / bpm
  transitions_duration = {
      "cut":           0.0,
      "cross_dissolve": round(beat_duration / 2, 2),  # pół beatu
      "fade":          round(beat_duration, 2),         # jeden beat
      "dip_white":     round(beat_duration * 0.75, 2), # 3/4 beatu
  }
  Wszystkie czasy w zakresie 0.2s - 0.8s (min/max clamp)

## Problem 4: Dynamika napisów

### Rozmiar fontu zależy od sekcji

  font_sizes = {
      "chorus":  64,  # duże — energia refrenu
      "verse":   54,  # standardowe
      "bridge":  48,  # mniejsze — intymność
      "intro":   50,  # wstęp
      "outro":   46,  # wyciszenie
  }
  default_font_size = 54

### Animacja wejścia zależy od sekcji

  "chorus": animacja "pop" (scale 0→1.05→1.0, fade 0.2s)
  "verse":  animacja "fade" (0.3s)
  "bridge": animacja "slide_up" (0.4s)
  "outro":  animacja "fade" (0.5s — wolniejsze)

### Implementacja w assembler.py

Pobierz section dla danego timestamp:
def get_section_for_time(t, sections):
    for section in sections:
        if section["start"] <= t < section["end"]:
            return section["label"]
    return "verse"

Przy tworzeniu TextClip:
    section = get_section_for_time(lyric["start"], analysis["sections"])
    font_size = font_sizes.get(section, 54)
    # Użyj font_size przy tworzeniu TextClip

## Testy

test_chorus_shorter_than_verse:
  Dla dowolnej piosenki: avg(chorus_durations) < avg(verse_durations)

test_no_same_motion_twice:
  Żadne dwie sąsiednie sceny nie mają tego samego motion

test_transitions_map:
  verse→chorus daje "cut"
  chorus→verse daje "fade"
  bridge→chorus daje "cut"

test_font_sizes:
  Scena chorus: TextClip ma font_size=64
  Scena verse: TextClip ma font_size=54

test_snap_to_downbeat:
  t=44.3, downbeats=[44.0, 44.7] → returns 44.0 (bliższy)
  t=10.0, downbeats=[8.0, 13.0] → returns 10.0 (poza oknem 0.8)

## Acceptance Criteria
- Sceny refrenu są wyraźnie krótsze niż sceny zwrotki
- Każda sąsiednia para scen ma inny typ ruchu kamery
- Przejście verse→chorus to cut (nie fade)
- Napisy refrenu są większe niż napisy zwrotki
- Cięcia trafiają w downbeat muzyczny (±0.8s)
- python3 -m pytest tests/test_dynamics.py -v przechodzi
