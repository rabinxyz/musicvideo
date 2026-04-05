# Spec: Smart crop dla social media — detekcja punktu zainteresowania

## Problem
Konwersja 16:9 → 9:16 przez zwykły center crop ucina główny motyw.
Np. zdjęcie człowieka pokazuje tylko jego ręce bo człowiek jest z boku kadru.

## Rozwiązanie — dwie metody (użyj obu jako fallback)

### Metoda 1 — detekcja twarzy przez OpenCV (szybka, darmowa)
Użyj OpenCV haar cascade do wykrywania twarzy w obrazie.
Jeśli twarz wykryta: wycentruj crop na twarzy.
Jeśli brak twarzy: przejdź do Metody 2.

Implementacja:
  import cv2
  face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades +
    "haarcascade_frontalface_default.xml")
  faces = face_cascade.detectMultiScale(gray_image, 1.1, 4)
  if len(faces) > 0:
    # Znajdź centrum największej twarzy
    x, y, w, h = max(faces, key=lambda f: f[2]*f[3])
    face_center_x = x + w // 2
    # Wycentruj crop poziomo na twarzy

### Metoda 2 — saliency map przez OpenCV (gdy brak twarzy)
OpenCV ma wbudowany algorytm saliency który wykrywa
"najciekawszy" region obrazu bez użycia ML.

  saliency = cv2.saliency.StaticSaliencyFineGrained_create()
  success, saliency_map = saliency.computeSaliency(image)
  # Znajdź centrum mapy saliency
  # Użyj jako punkt centralny cropowania

### Metoda 3 — fallback do center crop
Gdy obie metody zawiodą: zwykły center crop jak dotychczas.

## Algorytm smart crop

Dla konwersji 16:9 (np. 1024x768) → 9:16 (np. 576x1024):

1. Wykryj punkt zainteresowania (POI) przez Metodę 1 lub 2
   POI = (poi_x, poi_y) — współrzędne w oryginalnym obrazie

2. Oblicz szerokość docelowego crop w oryginalnym obrazie:
   target_ratio = 9/16
   crop_width = int(original_height * target_ratio)
   crop_height = original_height

3. Wycentruj crop poziomo na POI:
   crop_x = poi_x - crop_width // 2
   crop_x = max(0, min(crop_x, original_width - crop_width))

4. Przytnij obraz do crop_width x crop_height
5. Przeskaluj do docelowej rozdzielczości (np. 1080x1920)

## Wariant z rozmytym tłem (polecany)

Zamiast twardego przycięcia:
1. Przeskaluj oryginalny obraz do pełnej wysokości 9:16 (rozmyty background)
2. Zastosuj mocny blur: Gaussian blur sigma=30
3. Na środku nałóż oryginalny obraz przycięty smart cropem
4. Efekt: główny motyw ostry na środku, boki rozmyte w stylu platformy

To wygląda profesjonalnie i żaden motyw nie jest ucięty.
Używane przez profesjonalnych twórców content na IG/TikTok.

Flaga: --reels-style [crop|blur-bg]  (domyślnie: blur-bg)

## Nowy moduł musicvid/pipeline/smart_crop.py

Funkcje:
- detect_poi(image_path) -> (x, y)
  Wykrywa punkt zainteresowania przez face detection lub saliency.
  Zwraca współrzędne POI w oryginalnym obrazie.
  Fallback do centrum (w/2, h/2) gdy nic nie wykryto.

- smart_crop(image_path, target_w, target_h, poi=None) -> PIL.Image
  Przycina obraz do target_w x target_h centrując na POI.
  Gdy poi=None: wywołuje detect_poi() automatycznie.

- blur_bg_composite(image_path, target_w, target_h) -> PIL.Image
  Tworzy kompozyt: rozmyte tło + ostry smart crop na środku.
  Rekomendowana metoda dla reels/shorts.

- convert_for_platform(image_path, platform, style="blur-bg") -> str
  Główna funkcja — konwertuje obraz dla danej platformy.
  platform: "reels" | "shorts" | "square"
  Zapisuje wynik do tmp/ i zwraca ścieżkę.

## Integracja w assembler.py

Gdy platform == "reels" lub "shorts" (format 9:16):
  Zamiast: clip.resized(scale).cropped(center)
  Użyj: convert_for_platform(image_path, "reels", style=reels_style)

Dla Ken Burns na obrazach 9:16:
  Stosuj Ken Burns po konwersji — nie przed.
  Ruchy tylko pionowe (pan_up/pan_down, zoom_in/zoom_out).
  Nie używaj pan_left/pan_right — kadr jest wąski.

## Generowanie obrazów w natywnym formacie 9:16

Najlepsza opcja: generuj obrazy BFL już w formacie 9:16 dla reels.
W image_generator.py gdy platform == "reels":
  width=768, height=1360 (zbliżone do 9:16 w limitach BFL)
Wtedy smart crop jest minimalnys — obraz już ma właściwe proporcje.

Claude-reżyser dostaje informację o platformie i generuje prompty
uwzględniające pionowy kadr:
"Prompt musi opisywać kompozycję pionową (portrait orientation).
Główny motyw wycentrowany, dużo wolnej przestrzeni góra/dół."

## requirements.txt — dodaj
opencv-python>=4.8.0

## Testy
- detect_poi na obrazie z twarzą: POI blisko centrum twarzy
- detect_poi na krajobrazie (brak twarzy): POI w "najciekawszym" miejscu
- smart_crop: wynik ma wymiary target_w x target_h
- blur_bg_composite: wynik ma wymiary target_w x target_h
- smart_crop nie ucina twarzy gdy twarz wykryta
- convert_for_platform "reels": zwraca plik w formacie 9:16

## Acceptance Criteria
- Konwersja 16:9 → 9:16 centruje na wykrytej twarzy lub głównym motywie
- --reels-style blur-bg tworzy kompozyt z rozmytym tłem
- --reels-style crop robi twardy smart crop
- Obrazy generowane dla reels mają natywny format 9:16 gdy możliwe
- Ken Burns na reels używa tylko ruchów pionowych
- Twarze i główne motywy nie są ucinane w rolkach
- python3 -m pytest tests/ -v przechodzi
