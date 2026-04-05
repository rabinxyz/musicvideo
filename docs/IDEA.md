# Idea

# Spec: Naprawa montażu rolek — NoneType imread

## Problem
Montaż rolek (rolka_A, rolka_B, rolka_C) rzuca:
'NoneType' object has no attribute 'imread'

Przyczyna: assembler szuka zdjęcia dla sceny w określonym przedziale
czasowym ale video_path w fetch_manifest dla tej sceny jest None
lub plik nie istnieje na dysku.

## Poprawki

### 1. Walidacja video_path przed montażem rolek
W _run_preset_mode() lub assembler.py przed montażem każdej rolki:

for entry in fetch_manifest:
    if entry.get("video_path") is None:
        print(f"WARN: brak video_path dla sceny {entry.get('scene_index')}")
        continue
    if not os.path.exists(entry["video_path"]):
        print(f"WARN: plik nie istnieje: {entry['video_path']}")
        continue

### 2. Fallback gdy brak zdjęcia dla sceny rolki
Gdy scena wymagana przez rolkę nie ma zdjęcia:
- Użyj najbliższej dostępnej sceny z fetch_manifest
- Znajdź scenę której przedział czasowy najbardziej pokrywa się
  z żądanym przedziałem rolki

def find_nearest_scene(start, end, fetch_manifest):
    best = None
    best_overlap = 0
    for entry in fetch_manifest:
        if not entry.get("video_path"):
            continue
        if not os.path.exists(entry["video_path"]):
            continue
        scene_start = entry.get("start", 0)
        scene_end = entry.get("end", 0)
        overlap = min(end, scene_end) - max(start, scene_start)
        if overlap > best_overlap:
            best_overlap = overlap
            best = entry
    return best

### 3. Logowanie przed każdą rolką
Przed montażem każdej rolki wypisz:
  print(f"Rolka {name}: start={clip_start:.1f}s end={clip_end:.1f}s")
  print(f"  Dostępne sceny: {[(e['scene_index'], e['video_path']) for e in fetch_manifest]}")

Pomoże to zdiagnozować dokładnie które sceny brakuje.

### 4. Sprawdź clip_selections.json
Plik output/tmp/{hash}/clip_selections.json może wskazywać
na przedziały czasowe które nie pokrywają się z żadną sceną.

Gdy clip start/end nie pokrywa się z żadną sceną w fetch_manifest:
  Rozszerz okno szukania: znajdź scenę której środek jest
  najbliżej środka clip (start+end)/2.

## Acceptance Criteria
- --preset all nie rzuca 'NoneType' imread dla żadnej rolki
- Gdy brak idealnego dopasowania: użyj najbliższej dostępnej sceny
- Logowanie pokazuje które sceny są używane dla każdej rolki
- python3 -m pytest tests/ -v przechodzi
