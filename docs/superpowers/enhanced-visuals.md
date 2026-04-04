# Spec: Lepsza jakość zdjęć + dopasowanie do tekstu + ożywione video (1/3 scen)

## Trzy ulepszenia w jednym spec

---

## Ulepszenie 1 — lepsza jakość i trafność zdjęć

### Problem
Prompty generowane przez Claude-reżysera są zbyt ogólne — nie nawiązują
konkretnie do treści danej linijki tekstu piosenki.

### Rozwiązanie — prompty kontekstowe

Claude-reżyser przy planowaniu każdej sceny dostaje:
- tekst linijek które pojawią się w tej scenie
- nastrój i energię całej piosenki
- styl wizualny ustalony dla całości
- tekst linijek poprzedniej i następnej sceny (kontekst)

Prompt dla Claude-reżysera musi generować visual_prompt który:
1. Nawiązuje bezpośrednio do metafory lub obrazu z tekstu danej sceny
2. Zachowuje spójność kolorystyczną z całym teledyskiem (master palette)
3. Jest bardzo szczegółowy i opisowy — minimum 3 zdania
4. Zawiera: główny motyw + światło + nastrój + kompozycja kadru + głębia

Przykład dobrego promptu dla linijki "Tylko w Bogu jest moja dusza":
"A lone silhouette of a person standing on a vast rocky cliff overlooking
an infinite ocean at golden hour. Warm amber and deep orange light bathes
the entire scene, with rays of sunlight breaking through scattered clouds
above. The composition uses rule of thirds with the figure small against
the immense landscape, conveying human smallness before the divine.
Shallow depth of field, cinematic 16:9, photorealistic, high quality."

### Model BFL — użyj flux-pro-1.1 zamiast flux-dev
flux-pro-1.1 daje znacząco lepszą jakość detali i realizm.
Zmień domyślny model dla trybu ai na flux-pro-1.1.
Endpoint BFL: /v1/flux-pro-1.1

### Master style prompt
Claude-reżyser na początku generuje jeden master_style który
jest dołączany do KAŻDEGO visual_prompt:
Przykład: "Consistent cinematic color grade, warm golden tones,
soft atmospheric haze, photorealistic photography style"
To zapewnia spójność wizualną między scenami.

### Prompt director_system.txt — dodaj zasady jakości
- Każdy visual_prompt musi opisywać konkretny obraz nawiązujący do tekstu
- Minimum 2 zdania opisu
- Zawsze opisz kompozycję kadru (close-up / medium / wide shot)
- Zawsze opisz kierunek i jakość światła
- Zawsze opisz głębię i atmosferę sceny
- Dołącz master_style na końcu każdego promptu

---

## Ulepszenie 2 — ożywione video dla 1/3 scen (Runway Gen-4)

### Koncepcja
Zamiast Ken Burns na wszystkich scenach — co trzecia scena jest
prawdziwym krótkim video wygenerowanym przez Runway Gen-4 (image-to-video).
Pozostałe 2/3 scen to nadal zdjęcia z Ken Burns i efektami.

Wybór które sceny animować:
Claude-reżyser w planie scen dodaje pole "animate": true/false.
Animuj sceny przy refrenie i kluczowych emocjonalnie momentach.
Maksymalnie co trzecia scena ma "animate": true.

### Provider video — Runway Gen-4

API: https://api.dev.runwayml.com
Dokumentacja: https://docs.dev.runwayml.com
Klucz: RUNWAY_API_KEY w .env

Przepływ image-to-video:
1. Wygeneruj zdjęcie przez BFL API jak zwykle
2. Wyślij zdjęcie do Runway Gen-4 image-to-video
3. Parametry: duration=5s, ratio=1280:768 (16:9)
4. Runway zwraca URL do video MP4
5. Pobierz video i użyj zamiast ImageClip z Ken Burns

Prompt dla Runway (motion prompt) — Claude generuje go w planie scen
jako pole "motion_prompt":
Opisuje RUCH który ma nastąpić w scenie — nie treść obrazu.
Przykłady:
- "Slow camera push forward, gentle wind moves the trees, golden light shifts"
- "Camera slowly rises revealing the landscape below, clouds drift gently"
- "Subtle zoom out, light rays move across the scene, peaceful stillness"
Unikaj gwałtownych ruchów — muzyka uwielbienia wymaga spokojnego ruchu.

### Nowy moduł musicvid/pipeline/video_animator.py
Funkcja: animate_image(image_path, motion_prompt, duration, output_path) -> str
- Wczytaj obraz z image_path
- Wyślij do Runway Gen-4 API jako image-to-video
- Polluj status aż gotowe (Runway też jest async)
- Pobierz video MP4 do output_path
- Zwróć output_path

Runway API przepływ:
POST /v1/image_to_video z body:
  model: "gen4_turbo"
  promptImage: base64 obrazu lub URL
  promptText: motion_prompt
  duration: 5
  ratio: "1280:768"
→ zwraca {id: task_id}
GET /v1/tasks/{task_id}
→ polluj co 3s aż status == "SUCCEEDED"
→ output[0].url to URL do video MP4

Timeout: 300 sekund (Runway jest wolniejszy niż BFL)
Retry: max 2 próby na błędy sieciowe

### Integracja w pipeline
W director_plan każda scena ma pola:
  "animate": bool
  "motion_prompt": string (tylko gdy animate: true)

W image_generator / assembler:
Gdy scene["animate"] == True:
  1. Wygeneruj zdjęcie przez BFL normalnie
  2. Wyślij do Runway → pobierz video MP4
  3. Użyj VideoFileClip zamiast ImageClip z Ken Burns
  4. Przytnij video do długości sceny (subclipped)
  Gdy Runway niedostępny (brak RUNWAY_API_KEY):
  Fallback do Ken Burns na zdjęciu bez błędu

Gdy scene["animate"] == False:
  Zwykłe zdjęcie z Ken Burns jak dotychczas

### Cachowanie video
Cache animowanych klipów w: output/tmp/{hash}/animated_scene_NNN.mp4
Nie generuj ponownie jeśli plik istnieje.

### Koszt i czas
BFL flux-pro-1.1: ~$0.05/obraz
Runway Gen-4 turbo: ~$0.05 za 5s video
Dla 8 scen z 1/3 animowanych (3 sceny):
  5 zdjęć × $0.05 = $0.25
  3 video × $0.05 = $0.15
  Łącznie: ~$0.40 za teledysk

Czas generowania: +2-3 minuty na animowane sceny.

### Nowa flaga CLI
--animate [auto|always|never]  (domyślnie: auto)
auto   — Claude decyduje które sceny animować (co trzecia, przy refrenie)
always — animuj wszystkie sceny (drożej, wolniej)
never  — żadnych animacji, tylko Ken Burns (szybko, tanio)

---

## .env.example — dodaj
RUNWAY_API_KEY=...   # klucz z app.runwayml.com → Settings → API Keys

## requirements.txt — dodaj
runwayml>=0.1.0  # oficjalna biblioteka Python Runway

---

## Testy
- visual_prompt zawiera konkretne nawiązanie do tekstu sceny
- master_style dołączony do każdego promptu
- animate_image: mockuj Runway API, sprawdź że zwraca ścieżkę MP4
- Polling Runway: symuluj PENDING → SUCCEEDED
- Timeout 300s: TimeoutError
- Fallback gdy brak RUNWAY_API_KEY: Ken Burns bez błędu
- Maksymalnie 1/3 scen ma animate=True gdy --animate auto
- Cache: nie wywołuj Runway ponownie jeśli MP4 istnieje

## Acceptance Criteria
- Prompty zdjęć nawiązują do tekstu konkretnej sceny
- Każdy prompt zawiera opis kompozycji i światła
- Co trzecia scena to prawdziwe video z Runway (gdy --animate auto)
- --animate never generuje tylko Ken Burns (bez Runway)
- --animate always animuje każdą scenę
- Animowane sceny cachowane w tmp/
- Fallback do Ken Burns gdy brak RUNWAY_API_KEY
- python3 -m pytest tests/ -v przechodzi
