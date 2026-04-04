# Spec: Generator obrazów z wyborem providera + naprawa strategii promptów

## Problem 1 — DALL-E generuje katolickie obrazy
DALL-E 3 ignoruje negatywne prompty — opisywanie czego NIE generować
powoduje że właśnie to generuje. Trzeba przejść na modele z osobnym
parametrem negative_prompt i zmienić strategię na pozytywną.

## Problem 2 — brak wyboru providera
Użytkownik powinien móc wybrać z czego korzysta przez flagę --provider.

## Nowa flaga CLI
--provider [dalle|flux-dev|flux-pro|schnell]  (domyślnie: flux-dev)

Użycie:
python3 -m musicvid.musicvid song.mp3 --mode ai --provider flux-dev
python3 -m musicvid.musicvid song.mp3 --mode ai --provider flux-pro
python3 -m musicvid.musicvid song.mp3 --mode ai --provider schnell
python3 -m musicvid.musicvid song.mp3 --mode ai --provider dalle

## Providery i ich konfiguracja

### flux-dev (domyślny, rekomendowany)
API: fal.ai — fal-ai/flux/dev
Klucz: FAL_KEY
Koszt: ~$0.003/obraz
Rozdzielczość: 1280x720 (16:9 natywnie)
Rejestracja i darmowe $10 kredytów: https://fal.ai

### flux-pro (najwyższa jakość)
API: fal.ai — fal-ai/flux-pro
Klucz: FAL_KEY (ten sam co flux-dev)
Koszt: ~$0.05/obraz
Rozdzielczość: 1280x720

### schnell (najszybszy i najtańszy)
API: fal.ai — fal-ai/flux/schnell
Klucz: FAL_KEY (ten sam co flux-dev)
Koszt: ~$0.001/obraz
Rozdzielczość: 1280x720

### dalle (legacy, odradzany)
API: OpenAI images.generate model=dall-e-3
Klucz: OPENAI_API_KEY
Koszt: ~$0.04/obraz
Rozdzielczość: 1792x1024
Uwaga: nie obsługuje negative_prompt — używa tylko pozytywnego promptu

## Naprawa strategii promptów

### Stara strategia (błędna)
Opisywanie tego czego NIE chcemy w głównym prompcie:
"no rosary, no Madonna, no Catholic imagery"
Efekt: DALL-E i inne modele generują dokładnie to bo o tym "myślą"

### Nowa strategia (pozytywna)
Główny prompt opisuje TYLKO to co chcemy — nigdy nie wspominamy
o tym czego unikamy. Lista wykluczeń idzie jako osobny parametr
negative_prompt (obsługiwany przez Flux, ignorowany przez DALL-E).

Claude-reżyser dostaje nowe instrukcje w director_system.txt:

ZAKAZANE SŁOWA w głównym prompcie (nigdy ich nie pisz):
Catholic, rosary, Madonna, saint, cross with figure, stained glass,
church interior, religious, icon, Byzantine, papal, crucifix,
prayer beads, Maria, monastery, monk, nun, cathedral, chapel,
shrine, altar, candle altar, sacred heart, IHS

ZASADA BUDOWANIA PROMPTU:
Każdy prompt = [główny motyw] + [oświetlenie] + [nastrój] + [styl techniczny]
Nigdy nie opisuj czego nie ma — opisuj tylko to co jest.

Zamiast: "mountain without church" → "dramatic mountain peaks at golden hour"
Zamiast: "no religious figures" → "vast empty landscape, cinematic wide shot"
Zamiast: "empty cross not Catholic" → "simple wooden cross on hilltop at sunrise"

Przykłady dobrych promptów:
- "Golden wheat fields stretching to horizon, warm afternoon light, peaceful and serene, cinematic 16:9, photorealistic, high quality"
- "Mountain peaks emerging from morning mist, rays of sunlight breaking through clouds, majestic and awe-inspiring, cinematic 16:9, photorealistic, high quality"
- "Calm lake reflecting blue sky and white clouds, gentle ripples on water surface, tranquil and meditative, cinematic 16:9, photorealistic, high quality"
- "Ancient forest with light filtering through tall trees, green and golden tones, spiritual and peaceful, cinematic 16:9, photorealistic, high quality"
- "Open Bible on wooden table, warm window light from the side, soft focus background, intimate atmosphere, cinematic 16:9, photorealistic, high quality"
- "Silhouette of person standing on hilltop with hands raised toward sky, dramatic sunset behind, cinematic 16:9, photorealistic, high quality"
- "Abstract golden light rays on dark background, particles of light floating, divine and transcendent atmosphere, cinematic 16:9, photorealistic, high quality"
- "Simple wooden empty cross on green hillside, blue sky with clouds, peaceful and hopeful, cinematic 16:9, photorealistic, high quality"
- "Dove in flight against bright sky, wings spread wide, freedom and grace, cinematic 16:9, photorealistic, high quality"

## Zmiany w kodzie

### musicvid/pipeline/image_generator.py (przepisz całkowicie)

NEGATIVE_PROMPT (stała używana przez wszystkie Flux providery):
"catholic church interior, religious figures, icon, stained glass with people,
cross with body crucifix, statue figurine, rosary prayer beads, altar tabernacle,
monastery nun monk pope bishop, cathedral chapel shrine, byzantine painting,
sacred heart with thorns, watermark text logo, ugly blurry low quality, nsfw"

Funkcje:
- generate_images(scene_plan, output_dir, provider="flux-dev") -> list[str]
- _generate_flux(prompt, model_id, output_path) — wspólna logika dla flux-dev/pro/schnell
- _generate_dalle(prompt, output_path) — legacy DALL-E 3
- _detect_provider(requested) — waliduje czy klucz dla danego providera jest dostępny,
  rzuca EnvironmentError z instrukcją gdzie się zarejestrować jeśli brak klucza

Mapowanie provider -> model_id fal.ai:
flux-dev   -> "fal-ai/flux/dev"
flux-pro   -> "fal-ai/flux-pro"
schnell    -> "fal-ai/flux/schnell"

Parametry wywołania fal_client.run dla każdego Flux:
prompt: [główny prompt ze sceny]
negative_prompt: NEGATIVE_PROMPT
image_size: {"width": 1280, "height": 720}
num_inference_steps: 28 (flux-dev/pro), 4 (schnell)
guidance_scale: 3.5
num_images: 1
output_format: "jpeg"

Retry: @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
na każdym wywołaniu API.
Pobierz obraz przez requests.get i zapisz do output_dir/scene_NNN.jpg

### musicvid/musicvid.py
Dodaj opcję:
--provider [dalle|flux-dev|flux-pro|schnell]  default="flux-dev"
Przekaż provider do generate_images().
Wyświetl w logach: "[3/4] Generowanie obrazów (provider: flux-dev)"

### prompts/director_system.txt (przepisz)
Usuń wszystkie negatywne instrukcje.
Zastąp pozytywnymi wzorcami jak opisano wyżej.
Zawiera: rola + lista pozytywnych motywów + przykłady promptów + zasada budowania.
Zawiera listę zakazanych SŁÓW (nie motywów) których nie wolno używać w promptach.
Format wyjścia: czysty JSON bez markdown.

### .env.example (zaktualizuj)
FAL_KEY=...              # fal.ai — flux-dev, flux-pro, schnell (darmowe $10 na start)
OPENAI_API_KEY=sk-...    # tylko dla --provider dalle (opcjonalne)

### requirements.txt (dodaj)
fal-client>=0.10.0

### tests/test_image_generator.py (nowy lub zaktualizuj)
- Test każdego providera: flux-dev, flux-pro, schnell, dalle (mockowane)
- Test że NEGATIVE_PROMPT jest przekazywany jako osobny parametr do Flux
- Test że NEGATIVE_PROMPT nie jest w głównym prompcie
- Test że żaden prompt nie zawiera zakazanych słów z listy
- Test fallback i czytelny błąd gdy brak klucza API
- Test retry na błędzie API

## .env dla testów manualnych
Zarejestruj się na https://fal.ai → API Keys → skopiuj klucz → dodaj do .env:
FAL_KEY=twoj-klucz-tutaj

## Acceptance Criteria
- --provider flux-dev generuje obrazy przez fal.ai Flux Dev
- --provider flux-pro generuje przez Flux Pro (wyższa jakość)
- --provider schnell generuje przez Flux Schnell (najszybszy)
- --provider dalle generuje przez DALL-E 3 (legacy)
- Domyślnie używa flux-dev bez podawania flagi
- Żaden prompt wysyłany do API nie zawiera zakazanych słów
- negative_prompt jest osobnym parametrem (nie w głównym prompcie)
- Czytelny błąd z instrukcją gdy brak FAL_KEY
- Wszystkie testy: python3 -m pytest tests/ -v
