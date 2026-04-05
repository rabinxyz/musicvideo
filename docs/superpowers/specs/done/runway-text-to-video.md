# Spec: Runway text-to-video — bez generowania zdjęcia przez BFL

## Kontekst
Obecny TYPE_ANIMATED: BFL Flux generuje zdjęcie → Runway animuje je
Nowe podejście: Runway Gen-4.5 generuje wideo wprost z tekstu

Oszczędność: ~$0.04 per scenę (brak kroku BFL)
Szybkość: ~30s mniej na scenę
Jakość: Runway sam interpretuje prompt — dobra dla dynamicznych scen

## Zmiany w video_animator.py

### Nowa funkcja: generate_video_from_text()

def generate_video_from_text(
    prompt: str,
    duration: int = 5,
    output_path: str = None
) -> str:
    Generuje wideo z tekstu przez Runway Gen-4.5 bez obrazu wejściowego.

    Payload do API (bez promptImage):
    {
        "model": "gen4.5",
        "promptText": prompt,
        "duration": 5,
        "ratio": "1280:720"
    }

    Przepływ identyczny jak animate_image():
    1. POST /v1/image_to_video z promptText ale BEZ promptImage
    2. Polling GET /v1/tasks/{task_id} co 3s aż SUCCEEDED
    3. Pobierz wideo z output[0] (string URL)
    4. Zapisz do output_path
    5. Zwróć output_path

    Obsługa błędów:
    - Brak RUNWAY_API_KEY: RuntimeError z instrukcją
    - Timeout 300s: TimeoutError
    - FAILED/CANCELLED: RuntimeError z statusem
    - Retry max 2 próby na błędy sieciowe i 5xx

## Zmiany w visual_router.py

### Zmień TYPE_ANIMATED na text-to-video

Stary kod (_route_animated):
    1. Generuj zdjęcie przez BFL (_generate_bfl)
    2. Animuj zdjęcie przez Runway (animate_image)

Nowy kod (_route_animated):
    1. Zbuduj video_prompt z visual_prompt + motion_prompt sceny
    2. Wywołaj generate_video_from_text(video_prompt, duration=5, output_path)
    3. Zwróć output_path

Budowanie video_prompt:
    visual = scene.get("visual_prompt", "")
    motion = scene.get("motion_prompt", "slow camera push forward")
    video_prompt = f"{visual} {motion}".strip()

    Jeśli video_prompt jest za długi (> 500 znaków):
        Skróć visual_prompt do pierwszych 400 znaków
        Zawsze zachowaj motion_prompt w całości

### Fallback gdy Runway text-to-video się nie powiedzie

Gdy generate_video_from_text() rzuca wyjątek:
    Fallback do TYPE_AI (statyczne zdjęcie BFL + Ken Burns)
    print(f"WARN: Runway text-to-video failed dla sceny {idx} — fallback TYPE_AI")

## Zmiany w director.py / director_system.txt

### Nowe wytyczne dla motion_prompt przy TYPE_ANIMATED

Teraz motion_prompt opisuje CAŁĄ scenę wideo (nie tylko ruch kamery)
bo Runway generuje wszystko z tekstu.

Dodaj do promptu Claude:
"Dla scen TYPE_ANIMATED pole motion_prompt opisuje CAŁĄ scenę wideo:
- Co się dzieje w kadrze (motyw + akcja + nastrój)
- Ruch kamery
- Oświetlenie i atmosfera
- Maksymalnie 2-3 zdania, konkretnie

Przykłady dobrych motion_prompt dla TYPE_ANIMATED:
'Slow camera rise over misty mountain valley at dawn,
golden light breaking through clouds, person silhouette on ridge,
documentary cinematic style, natural colors'

'Gentle push forward through outdoor worship gathering,
people with hands raised at sunset, warm golden backlight,
authentic documentary feel, real emotion'

'Camera slowly pulls back revealing vast ocean horizon,
waves in foreground, light dancing on water surface,
contemplative mood, film grain aesthetic'"

## Prompt dla Claude — dobór visual_source TYPE_ANIMATED

Zaktualizuj kryteria w director_system.txt:

TYPE_ANIMATED używaj gdy:
- Scena jest kulminacyjna (pierwszy/ostatni refren, bridge)
- Tekst opisuje moment wymagający autentycznego ruchu
- Scena trwa >= 3s
- Maksymalnie co 4. scena

motion_prompt musi być pełnym opisem sceny wideo (nie tylko ruch kamery)
visual_prompt może być null (nie jest już potrzebny dla TYPE_ANIMATED)

## requirements.txt
Bez zmian — requests i tenacity już są

## Testy

test_text_to_video_payload:
    generate_video_from_text() wysyła POST bez promptImage
    Payload zawiera: model="gen4.5", promptText=..., duration=5, ratio="1280:720"

test_text_to_video_no_image:
    generate_video_from_text() NIE wywołuje _generate_bfl()
    Brak pliku scene_NNN.jpg gdy source=TYPE_ANIMATED

test_video_prompt_building:
    visual="Golden light" + motion="slow camera rise" →
    video_prompt="Golden light slow camera rise"

test_long_prompt_truncation:
    visual_prompt > 500 znaków → skrócony do 400 + motion_prompt

test_fallback_on_runway_error:
    Runway rzuca RuntimeError → fallback do TYPE_AI + Ken Burns

test_output_file_exists:
    generate_video_from_text() zwraca ścieżkę do istniejącego .mp4

## Acceptance Criteria
- TYPE_ANIMATED nie wywołuje BFL Flux (brak scene_NNN.jpg dla animowanych)
- Runway dostaje promptText bez promptImage
- Animowane sceny to prawdziwe wideo z Runway (nie Ken Burns na zdjęciu BFL)
- Fallback do TYPE_AI gdy Runway się nie powiedzie
- Koszt TYPE_ANIMATED: ~$0.50 zamiast ~$0.54
- python3 -m pytest tests/test_video_animator.py -v przechodzi
