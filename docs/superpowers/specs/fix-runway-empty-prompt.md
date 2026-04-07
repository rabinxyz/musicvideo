# Spec: Naprawa Runway — pusty promptText

## Problem
Runway zwraca 400: "Too small: expected string to have >=1 characters"
dla pola promptText.

Oznacza to że motion_prompt jest None lub "" gdy trafia do animate_image().

## Przyczyna
W visual_router.py gdy wywołuje _route_runway():
  motion = scene.get("motion_prompt", "slow camera push forward")

Jeśli scene["motion_prompt"] istnieje ale jest None lub "":
  scene.get() zwraca None lub "" zamiast defaultu

## Poprawka w video_animator.py

W funkcji _submit_animation() przed wysłaniem payload:
  # Upewnij się że promptText nie jest pusty
  if not motion_prompt or not motion_prompt.strip():
      motion_prompt = "Slow cinematic camera movement, natural light"

  payload = {
      "model": "gen4_turbo",
      "promptImage": image_b64,
      "promptText": motion_prompt.strip()[:500],  # max 500 znaków
      "duration": 5,
      "ratio": "1280:720",
  }

## Poprawka w visual_router.py

W _route_runway() przed wywołaniem animate_image():
  motion = scene.get("motion_prompt") or scene.get("visual_prompt") or ""
  if not motion.strip():
      motion = "Slow cinematic camera push forward, natural golden light, peaceful atmosphere"

  # Skróć do 300 znaków — Runway lepiej radzi z krótszymi promptami
  motion = motion.strip()[:300]

## Poprawka w director.py / director_system.txt

Dodaj do promptu Claude:
"WAŻNE: Pole motion_prompt dla TYPE_VIDEO_RUNWAY i TYPE_ANIMATED
MUSI być niepustym stringiem minimum 5 słów.
Jeśli nie masz pomysłu na ruch: użyj 'Slow cinematic camera push forward'"

## Acceptance Criteria
- Runway nie zwraca 400 empty promptText
- Fallback prompt gdy motion_prompt pusty lub None
- animated_scene_NNN.mp4 powstają w cache
