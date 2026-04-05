# Idea

# Spec: Naprawa montażu rolek — brak social_clips.json i mieszane typy assetów

## Problem 1 — brak social_clips.json

clip_selector.py nie zapisuje wybraných fragmentów do cache.
Rolki nie mogą znaleźć jakie fragmenty wybrać → błąd imread.

Napraw w musicvid.py lub preset_runner.py:
Gdy social_clips.json nie istnieje w cache_dir:
  1. Wywołaj select_social_clips(analysis, scene_plan, reel_duration)
  2. Zapisz wynik do cache_dir / "social_clips.json"
  3. Zaloguj: "Social clips wybrane: A={start}-{end}s, B=..., C=..."

Gdy social_clips.json istnieje i --new NIE jest podane:
  Wczytaj z cache (nie generuj ponownie)

Gdy --new podane:
  Usuń social_clips.json przed regenerowaniem

## Problem 2 — assembler rolek nie obsługuje .mp4 assetów

Assembler rolek wywołuje imread() (OpenCV) na wszystkich assetach.
imread() działa tylko dla .jpg/.png — crashuje na .mp4.

Napraw w assembler.py dla trybu rolek:
Gdy asset_path kończy się na .mp4:
  clip = VideoFileClip(asset_path).subclipped(0, scene_duration)
  clip = clip.without_audio()
Gdy asset_path kończy się na .jpg lub .png:
  clip = ImageClip(asset_path, duration=scene_duration)
  clip = apply_ken_burns(clip, motion)

Sprawdź rozszerzenie pliku przed załadowaniem:
  ext = Path(asset_path).suffix.lower()
  if ext == '.mp4':
      clip = VideoFileClip(asset_path)
  elif ext in ('.jpg', '.jpeg', '.png'):
      clip = ImageClip(asset_path)
  else:
      raise ValueError(f"Nieobsługiwane rozszerzenie: {ext}")

## Problem 3 — rolki szukają scen poza zakresem

fetch_manifest zawiera scene_index dla pełnego teledysku (0-41).
Rolka szuka scen w przedziale czasowym np. 44s-74s.
Jeśli żadna scena nie pokrywa tego przedziału → video_path=None → imread crash.

Napraw find_nearest_scene() w assembler.py lub preset_runner.py:
def find_nearest_scene(start, end, fetch_manifest):
    best = None
    best_score = float('inf')

    for entry in fetch_manifest:
        if not entry.get("video_path"):
            continue
        path = entry["video_path"]
        if not Path(path).exists():
            continue

        scene_start = entry.get("start", 0)
        scene_end = entry.get("end", 0)
        scene_mid = (scene_start + scene_end) / 2
        clip_mid = (start + end) / 2

        # Preferuj sceny których środek jest bliski środkowi klipu
        overlap = min(end, scene_end) - max(start, scene_start)
        distance = abs(scene_mid - clip_mid)

        # Score: nakładanie ważniejsze niż odległość
        score = distance - (overlap * 10 if overlap > 0 else 0)

        if score < best_score:
            best_score = score
            best = entry

    return best

Gdy find_nearest_scene() zwraca None:
  Użyj pierwszego dostępnego assestu z fetch_manifest który istnieje na dysku
  Nigdy nie zwracaj None — zawsze jest jakiś asset

## Problem 4 — Ken Burns na wideo (nie tylko obrazach)

Gdy asset to .mp4 z Pexels/Runway:
  NIE stosuj Ken Burns (to już wideo z ruchem)
  Przytnij do scene_duration przez subclipped()
  Jeśli wideo krótsze niż scene_duration: zapętl przez loop=True lub
  przytnij scene_duration do długości wideo

Gdy asset to .jpg/.png z BFL/Unsplash:
  Stosuj Ken Burns normalnie

## Acceptance Criteria
- social_clips.json tworzony przed montażem rolek
- assembler obsługuje .mp4 i .jpg/.png bez crashowania
- find_nearest_scene() nigdy nie zwraca None
- Ken Burns tylko na obrazach, nie na wideo
- Rolki A, B, C generują się bez błędu imread
- python3 -m pytest tests/ -v przechodzi
