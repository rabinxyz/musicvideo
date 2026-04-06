# Idea

# Spec: Naprawa rolek — imread crash i błędny crop 9:16

## Problem 1 — NoneType imread przy montażu rolek

Assembler rolek wywołuje imread() (OpenCV) na asset_path który:
a) Jest None bo find_nearest_scene() zwróciło None
b) Jest plikiem .mp4 a imread() obsługuje tylko obrazy

Napraw w assembler.py dla trybu rolek:

Krok 1 — sprawdź typ pliku przed załadowaniem:
  from pathlib import Path

  def load_asset_clip(asset_path, scene_duration, motion):
      if asset_path is None:
          raise ValueError(f"asset_path is None — brak assetu dla sceny")

      ext = Path(asset_path).suffix.lower()

      if ext == '.mp4':
          clip = VideoFileClip(asset_path)
          if clip.duration < scene_duration:
              clip = clip.loop(duration=scene_duration)
          else:
              clip = clip.subclipped(0, scene_duration)
          clip = clip.without_audio()
          return clip

      elif ext in ('.jpg', '.jpeg', '.png'):
          clip = ImageClip(asset_path, duration=scene_duration)
          clip = apply_ken_burns(clip, motion)
          return clip

      else:
          raise ValueError(f"Nieobsługiwane rozszerzenie: {ext}")

Krok 2 — find_nearest_scene() nigdy nie zwraca None:
  def find_nearest_scene(start, end, fetch_manifest):
      valid = [e for e in fetch_manifest
               if e.get("video_path") and Path(e["video_path"]).exists()]

      if not valid:
          return None  # caller obsługuje

      clip_mid = (start + end) / 2
      best = min(valid, key=lambda e: abs(
          (e.get("start", 0) + e.get("end", 0)) / 2 - clip_mid
      ))
      return best

Krok 3 — gdy find_nearest_scene zwraca None:
  Użyj pierwszego dostępnego assetu z fetch_manifest
  entry = next((e for e in fetch_manifest
                if e.get("video_path") and Path(e["video_path"]).exists()), None)
  if entry is None:
      raise RuntimeError("Brak jakichkolwiek assetów w cache")

## Problem 2 — crop 9:16 resizuje zamiast cropować

Obecny kod dla rolek 9:16 robi resize całego obrazu do 1080x1920
co rozciąga obraz 16:9 — wygląda jak ściśnięty obraz.

Napraw w assembler.py lub smart_crop.py:

Poprawny algorytm konwersji 16:9 → 9:16:

def convert_16_9_to_9_16(clip, target_w=1080, target_h=1920):
    src_w, src_h = clip.size

    # Krok 1: skaluj tak żeby wysokość = target_h
    scale = target_h / src_h
    new_w = int(src_w * scale)
    new_h = target_h

    # Krok 2: resize zachowując proporcje
    clip = clip.resized((new_w, new_h))

    # Krok 3: crop poziomo do target_w (przytnij boki)
    x_center = new_w / 2
    x1 = int(x_center - target_w / 2)
    x2 = int(x_center + target_w / 2)
    clip = clip.cropped(x1=x1, y1=0, x2=x2, y2=new_h)

    return clip

Wariant z wykryciem twarzy (smart crop):
    Użyj OpenCV haar cascade żeby znaleźć twarz
    Wycentruj crop na twarzy zamiast na środku geometrycznym

    import cv2
    def find_face_center(image_path):
        img = cv2.imread(image_path)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        faces = cascade.detectMultiScale(gray, 1.1, 4)
        if len(faces) > 0:
            x, y, w, h = max(faces, key=lambda f: f[2]*f[3])
            return x + w//2  # x centrum twarzy
        return None  # brak twarzy — użyj centrum obrazu

    Gdy twarz wykryta: wycentruj crop na twarzy (x_center = face_x)
    Gdy brak twarzy: wycentruj geometrycznie (x_center = src_w / 2)

Wariant blur-bg (gdy aspect ratio bardzo różne):
    Stwórz rozmyte tło z całego obrazu skalowanego do 9:16
    Nałóż na środku ostry smart crop
    Efekt profesjonalny — nic nie jest ucięte

    def blur_bg_composite(image_path, target_w=1080, target_h=1920):
        # Tło: cały obraz skalowany + mocny blur
        bg = ImageClip(image_path).resized((target_w, target_h))
        bg = bg.image_transform(lambda f: cv2.GaussianBlur(f, (99,99), 30))

        # Foreground: smart crop wycentrowany
        fg = convert_16_9_to_9_16(ImageClip(image_path), target_w, target_h)

        # Kompozyt
        return CompositeVideoClip([bg, fg.with_position("center")])

## Gdzie zastosować konwersję

W assembler.py dla każdego klipu gdy platform == "reels" lub "shorts":
  clip = load_asset_clip(asset_path, scene_duration, motion)
  clip = convert_16_9_to_9_16(clip, 1080, 1920)
  # Dopiero teraz dodaj napisy i efekty

NIE rób resize na całym klipie bez crop — to rozciąga obraz.

## Testy
- load_asset_clip z .mp4: zwraca VideoFileClip bez imread
- load_asset_clip z .jpg: zwraca ImageClip z Ken Burns
- load_asset_clip z None: rzuca ValueError
- convert_16_9_to_9_16: wynik ma wymiary 1080x1920
- convert_16_9_to_9_16: nie rozciąga (zachowuje proporcje przez crop)
- find_nearest_scene z pustym manifest: zwraca None (nie crashuje)

## Acceptance Criteria
- Rolki generują się bez błędu NoneType imread
- Rolki 9:16 mają prawidłowy crop (nie rozciąganie)
- Twarze i główne motywy wycentrowane w kadrze 9:16
- Ken Burns na obrazach, subclipped na wideo
- python3 -m pytest tests/ -v przechodzi
