# Spec: Naprawa Runway API — błąd 400

## Problem
video_animator.py zwraca 400 Bad Request z dwóch powodów:

## Poprawka 1 — ratio
Zmień: "ratio": "1280:768"  (niestandardowy, Runway odrzuca)
Na:    "ratio": "1280:720"  (standardowe 16:9)

## Poprawka 2 — nazwa modelu
Zmień: "model": "gen4_turbo"
Na:    "model": "gen4.5"
To aktualnie najnowszy model Runway według dokumentacji.

## Poprawka 3 — wyświetl pełny błąd API
W bloku except w musicvid.py zmień:
  click.echo(f"Animation failed for scene {idx + 1}: {exc}")
Na:
  if hasattr(exc, 'response') and exc.response is not None:
      click.echo(f"  Runway error: {exc.response.status_code} {exc.response.text[:300]}")
  click.echo(f"  Animation failed for scene {idx + 1}: {exc}")

Dzięki temu przyszłe błędy będą widoczne zamiast cichego fallbacku.

## Acceptance Criteria
- animate_image() wysyła ratio "1280:720" i model "gen4.5"
- Test curl potwierdza 200 OK zamiast 400
- animated_scene_NNN.mp4 powstają w cache po uruchomieniu
