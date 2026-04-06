# Spec: Domyślny mix — AI video (Runway) + przyroda stock (Pexels)

## Zmiana filozofii
Obecny default: zdjęcia BFL Flux + Ken Burns (statyczne, tendencyjne)
Nowy default: Runway text-to-video + Pexels przyroda (dynamiczne, realistyczne)

Rezygnujemy z TYPE_AI (statyczne zdjęcia BFL) jako domyślnego.
BFL Flux zostaje tylko gdy użytkownik jawnie poda --provider flux-pro/dev.

## Nowe domyślne mapowanie typów

TYPE_VIDEO_RUNWAY (NOWY — domyślny dla scen kulminacyjnych):
  Runway Gen-4.5 text-to-video bez obrazu wejściowego
  Dla: chorus, bridge, kluczowe sceny verse
  Koszt: ~$0.50 per 5s video
  Efekt: prawdziwy ruch, realistyczny, unikalny

TYPE_VIDEO_STOCK (domyślny dla przyrody):
  Pexels API — TYLKO przyroda bez ludzi
  Dla: intro, outro, spokojne verse
  Koszt: $0 darmowy
  Queries: mountain, lake, forest, sky, sunrise, ocean

TYPE_PHOTO_STOCK (dla statycznych momentów):
  Unsplash API — przyroda i neutralne obiekty
  Dla: kontemplacyjne momenty, Biblia, krzyż
  Koszt: $0 darmowy

TYPE_AI (opcjonalny — tylko gdy jawnie wybrany):
  BFL Flux Pro — statyczne zdjęcie + Ken Burns
  Wyłączony domyślnie bo tendencyjny wizualnie
  Dostępny przez: --source-ai lub gdy brak RUNWAY_API_KEY

## Nowy domyślny rozkład per sekcja

intro:   60% TYPE_VIDEO_STOCK + 40% TYPE_VIDEO_RUNWAY
verse:   50% TYPE_VIDEO_STOCK + 30% TYPE_VIDEO_RUNWAY + 20% TYPE_PHOTO_STOCK
chorus:  70% TYPE_VIDEO_RUNWAY + 30% TYPE_VIDEO_STOCK
bridge:  60% TYPE_VIDEO_RUNWAY + 40% TYPE_VIDEO_STOCK
outro:   70% TYPE_VIDEO_STOCK + 30% TYPE_VIDEO_RUNWAY

## Wytyczne dla Claude-reżysera — nowy director_system.txt

Zmień zasady doboru visual_source:

"DOSTĘPNE TYPY ŹRÓDEŁ:

TYPE_VIDEO_RUNWAY — AI wideo z tekstu (Runway Gen-4.5)
Kiedy używać:
  - Refren i bridge ZAWSZE
  - Verse gdy tekst opisuje ruch, emocję, działanie
  - Gdy chcesz unikalnej wizji której stock nie odda
motion_prompt: pełny opis sceny wideo 2-3 zdania
  Zawiera: co się dzieje + ruch kamery + nastrój + styl
  Styl: documentary, authentic, cinematic, natural light
  Przykład: 'Slow camera rise over misty mountain valley,
  person silhouette on ridge with arms open at dawn,
  documentary style, natural golden light, film grain'

TYPE_VIDEO_STOCK — prawdziwe wideo Pexels (TYLKO przyroda)
Kiedy używać:
  - Intro i outro
  - Verse z tekstem o przyrodzie
  - Gdy potrzebujesz spokojnego tła bez głównego motywu
search_query: 3-5 angielskich słów, TYLKO przyroda:
  mountain, valley, lake, forest, sky, ocean, river, field,
  sunrise, sunset, fog, mist, clouds, stars, waterfall
NIGDY: people, hands, prayer, worship, church

TYPE_PHOTO_STOCK — zdjęcie Unsplash (statyczne + Ken Burns)
Kiedy używać:
  - Bardzo spokojne, kontemplacyjne momenty
  - Gdy motyw to konkretny przedmiot (Biblia, krzyż)
search_query: 3-5 angielskich słów, przyroda lub neutralne obiekty

ZAKAZANE TYPY domyślnie:
TYPE_AI (BFL Flux) — generuje tendencyjne i cukierkowe zdjęcia
TYPE_ANIMATED (BFL + Runway) — zastąpiony przez TYPE_VIDEO_RUNWAY

PROPORCJE:
  Minimum 40% scen to TYPE_VIDEO_RUNWAY
  Minimum 30% scen to TYPE_VIDEO_STOCK
  Maksimum 20% scen to TYPE_PHOTO_STOCK
  TYPE_AI: 0% domyślnie"

## Zmiany w visual_router.py

Usuń lub zdeprecjonuj _route_animated() (BFL + Runway)
Dodaj _route_runway_text_to_video() jako główną metodę dla TYPE_VIDEO_RUNWAY

Nowa hierarchia routingu:
  TYPE_VIDEO_RUNWAY → generate_video_from_text(motion_prompt)
    Fallback gdy brak RUNWAY_API_KEY → TYPE_VIDEO_STOCK
  TYPE_VIDEO_STOCK → fetch_pexels_nature(search_query)
    Fallback gdy Pexels brak wyników → TYPE_VIDEO_RUNWAY
  TYPE_PHOTO_STOCK → fetch_unsplash(search_query)
    Fallback → TYPE_VIDEO_STOCK
  TYPE_AI → generate_bfl_image(visual_prompt) [tylko gdy jawnie]

## Zmiany w musicvid.py — nowe domyślne flagi

Obecny default --mode: "ai" (BFL Flux)
Nowy default --mode: "runway" (Runway text-to-video mix)

Dodaj nowy tryb:
  --mode runway: TYPE_VIDEO_RUNWAY + TYPE_VIDEO_STOCK mix (NOWY DEFAULT)
  --mode ai: TYPE_AI BFL Flux (stary tryb, dostępny jawnie)
  --mode stock: tylko Pexels (darmowy, bez AI)
  --mode hybrid: mix wszystkich

Komunikat startowy gdy --mode runway:
  "Obrazy:      Runway Gen-4.5 AI video + Pexels przyroda"

## Zmiany w motion_prompt — jakość dla Runway

Dodaj do director_system.txt wzorce dobrych motion_prompt:

Dla refrenu (worship, chwała):
'Slow camera rise revealing vast mountain landscape at golden hour,
person with arms raised toward sky on ridge, warm natural backlight,
documentary worship photography style, authentic emotion, film grain'

Dla zwrotki (kontemplacja, spokój):
'Gentle push through morning mist in mountain valley,
soft diffused light, peaceful atmosphere, no people,
documentary nature cinematography, natural colors'

Dla bridge (kulminacja):
'Dramatic slow pull-back revealing endless ocean horizon,
waves catching golden sunset light, emotional peak moment,
cinematic documentary style, handheld camera feel'

Dla intro (spokój, narastanie):
'Static wide shot of misty forest at dawn,
light slowly breaking through trees, birds visible,
nature documentary style, peaceful and contemplative'

## Szacowany koszt dla typowego teledysku (20 scen)

Mix: 8 × Runway ($0.50) + 9 × Pexels ($0) + 3 × Unsplash ($0)
Łącznie: $4.00 per teledysk

Vs stary tryb AI: 20 × BFL ($0.04) = $0.80
Runway jest droższy ale jakość nieporównywalna.

Opcja ekonomiczna --mode stock: $0.00 (tylko Pexels)

## Testy
- --mode runway: visual_router wywołuje generate_video_from_text dla TYPE_VIDEO_RUNWAY
- Minimum 40% scen to TYPE_VIDEO_RUNWAY w planie
- TYPE_VIDEO_STOCK queries zawierają tylko słowa przyrodnicze
- Fallback gdy brak RUNWAY_API_KEY: TYPE_VIDEO_STOCK bez błędu
- motion_prompt dla TYPE_VIDEO_RUNWAY ma minimum 2 zdania

## Acceptance Criteria
- python3 -m musicvid.musicvid piosenka.mp3 domyślnie używa Runway mix
- Przynajmniej 40% scen to prawdziwe AI video z Runway
- Reszta to realistyczne wideo z Pexels (przyroda)
- Brak statycznych zdjęć BFL w domyślnym trybie
- Brak tendencyjnych/cukierkowych obrazów
- --mode stock działa jako darmowa alternatywa
- --mode ai używa starego BFL Flux (dla kompatybilności)
- python3 -m pytest tests/ -v przechodzi
