# Spec: Naprawa Runway — promptImage jest wymagany

## Problem
Runway Gen-4 API wymaga pola promptImage jako obowiązkowego.
Text-to-video bez obrazu NIE jest obsługiwane przez gen4.5.
Błąd: "Invalid input: expected string, received undefined" dla promptImage.

## Rozwiązanie — TYPE_VIDEO_RUNWAY wraca do image-to-video

Przepływ dla TYPE_VIDEO_RUNWAY:
1. Wygeneruj zdjęcie przez BFL Flux (najtańszy model: flux-dev)
2. Wyślij zdjęcie do Runway jako promptImage + promptText = motion_prompt
3. Runway animuje zdjęcie w 5s wideo

Nie używaj flux-pro dla tego kroku — flux-dev wystarczy ($0.003/obraz).
Koszt TYPE_VIDEO_RUNWAY: $0.003 (BFL dev) + $0.50 (Runway) ≈ $0.50

## Implementacja w visual_router.py

Zmień _route_runway() lub generate_video_from_text():

def _route_runway(self, scene, idx):
    # Krok 1: generuj zdjęcie przez BFL flux-dev (tanie)
    image_path = str(Path(self.cache_dir) / f"scene_{idx:03d}.jpg")
    if not Path(image_path).exists():
        image_path = self._generate_bfl(
            scene.get("visual_prompt", scene.get("motion_prompt", "nature landscape")),
            idx,
            provider="flux-dev"  # zawsze flux-dev dla obrazów Runway
        )

    # Krok 2: animuj przez Runway image-to-video
    animated_path = str(Path(self.cache_dir) / f"animated_scene_{idx:03d}.mp4")
    if Path(animated_path).exists():
        return animated_path

    motion = scene.get("motion_prompt", "slow camera push forward, gentle movement")
    return animate_image(image_path, motion, duration=5, output_path=animated_path)

## Poprawka w animate_image() — video_animator.py

Upewnij się że payload zawiera promptImage jako base64:
  image_bytes = Path(image_path).read_bytes()
  ext = Path(image_path).suffix.lower()
  mime = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png"
  image_b64 = f"data:{mime};base64,{base64.b64encode(image_bytes).decode()}"

  payload = {
      "model": "gen4_turbo",  # sprawdzone że działa
      "promptImage": image_b64,
      "promptText": motion_prompt[:500],
      "duration": 5,
      "ratio": "1280:720",
  }

Model: użyj "gen4_turbo" — to działało wcześniej.
NIE używaj "gen4.5" — może nie być dostępny dla Twojego planu.

## Zmiany w director_system.txt

TYPE_VIDEO_RUNWAY wymaga teraz visual_prompt (dla BFL) + motion_prompt (dla Runway):

"TYPE_VIDEO_RUNWAY:
  visual_prompt: opis zdjęcia które BFL wygeneruje (styl dokumentalny)
  motion_prompt: opis RUCHU KAMERY dla Runway (2-3 zdania)
  Oba pola są wymagane."

## Acceptance Criteria
- Runway otrzymuje promptImage jako base64
- Runway model to "gen4_turbo"
- BFL flux-dev generuje obraz przed Runway
- animated_scene_NNN.mp4 powstaje w cache
- Brak błędu 400 Bad Request
