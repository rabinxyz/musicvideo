# Spec: Filtrowanie materiałów stock — tylko treści chrześcijańskie protestanckie

## Problem
Pexels i Unsplash zwracają materiały na podstawie słów kluczowych
bez filtrowania religijnego. Query "prayer", "worship", "hands praying"
może zwrócić materiały muzułmańskie, hinduskie, katolickie lub inne.

## Rozwiązanie — dwa poziomy filtrowania

### Poziom 1 — bezpieczne query (prewencja)

Zamień query które mogą zwrócić nieodpowiednie treści
na bezpieczne alternatywy które nie są związane z konkretną religią.

Mapping niebezpiecznych query → bezpiecznych w stock_fetcher.py i visual_router.py:

SAFE_QUERY_MAP = {
    # Modlitwa — ogólna może dać muzułmańską
    "prayer hands": "person sitting quietly nature",
    "hands praying": "person peaceful outdoor sunrise",
    "praying hands": "person sitting peaceful morning",
    "muslim": "BLOCKED",
    "mosque": "BLOCKED",
    "quran": "BLOCKED",
    "islamic": "BLOCKED",
    "hindu": "BLOCKED",
    "buddha": "BLOCKED",
    "meditation": "person sitting peaceful nature",

    # Worship — może dać różne religie
    "worship": "outdoor gathering people singing sunset",
    "worship hands raised": "people outdoor arms up sunset",
    "church": "BLOCKED",  # może być katolickie
    "cathedral": "BLOCKED",
    "mosque": "BLOCKED",

    # Bezpieczne zamiast ogólnych
    "prayer outdoor": "person sitting field morning light",
    "spiritual": "peaceful nature landscape morning",
}

Gdy search_query zawiera zablokowane słowo:
  Zastąp całe query bezpieczną alternatywą lub
  Fallback do TYPE_PHOTO_STOCK z innym query lub TYPE_AI

### Poziom 2 — weryfikacja przez Claude przed użyciem

Po pobraniu materiału stock (url lub plik):
Wyślij miniaturę/screenshot do Claude z pytaniem:
"Czy ten materiał wideo/zdjęcie zawiera elementy
muzułmańskie, hinduskie, buddyjskie, katolickie lub
innej religii niechrześcijańskiej protestanckiej?
Odpowiedz tylko: TAK lub NIE"

Jeśli Claude odpowie TAK:
  Odrzuć materiał
  Spróbuj z innym wynikiem Pexels (drugi lub trzeci wynik)
  Jeśli wszystkie odrzucone: fallback do TYPE_AI

Implementacja weryfikacji (opcjonalna, gdy ANTHROPIC_API_KEY dostępny):
  def verify_content_is_protestant(image_url_or_path) -> bool:
      Pobierz miniaturę (thumbnail) z Pexels response
      Wyślij do Claude Vision API
      Sprawdź odpowiedź

### Poziom 3 — whitelist bezpiecznych queries dla Pexels

Zamiast pozwalać Claude na dowolne query do Pexels,
użyj tylko queries z whitelist:

PEXELS_WHITELIST = [
    # Przyroda
    "mountain sunrise", "mountain valley mist", "mountain peak clouds",
    "lake reflection sky", "calm water sunrise", "river forest morning",
    "forest light trees", "sunlight through forest", "pine trees mountain",
    "golden wheat field", "green meadow sunset", "open field morning",
    "ocean waves horizon", "coastal cliffs sunset", "beach sunrise",
    "desert landscape sunset", "rocky canyon landscape",
    "starry night sky", "milky way mountains", "night sky stars",

    # Światło i atmosfera
    "golden hour landscape", "sunrise light rays", "sunset dramatic sky",
    "light through clouds", "fog morning landscape", "mist valley dawn",

    # Ludzie (bezpieczne)
    "person walking mountain", "person sitting cliff view",
    "person standing sunrise", "silhouette person sunset",
    "hands open palms upward", "person arms raised sunset",
    "outdoor gathering singing", "community outdoor event",
    "person reading book outdoor", "person writing journal",

    # Symbole protestanckie
    "wooden cross hilltop", "simple cross sunset", "open book sunlight",
    "candle flame dark", "dove flying sky",
]

Gdy Claude-reżyser generuje search_query który NIE jest na whiteliście:
  Znajdź najbardziej podobny query z whitelisty
  Użyj go zamiast oryginalnego

Alternatywnie: podaj whitelistę Claude-reżyserowi w prompcie:
"Używaj TYLKO tych queries do Pexels: [lista whitelisty]
NIE używaj: prayer hands, worship, church, spiritual, meditation,
muslim, hindu, buddha, islamic, mosque, quran, cathedral"

### Poziom 4 — ogranicz Pexels do przyrody

Najprostsze i najskuteczniejsze rozwiązanie:
TYPE_VIDEO_STOCK używaj TYLKO dla przyrody i krajobrazów.
Dla ludzi i aktywności — zawsze TYPE_AI lub TYPE_PHOTO_STOCK z Unsplash.

Dodaj do director_system.txt:
"TYPE_VIDEO_STOCK search_query: TYLKO przyroda i krajobrazy.
Nigdy nie używaj TYPE_VIDEO_STOCK dla ludzi, modlitwy, kultu,
wspólnoty — to zbyt ryzykowne. Użyj TYPE_AI dla tych scen."

## Implementacja

### Zmiany w visual_router.py

W _fetch_pexels() przed wysłaniem query:
  sanitized = sanitize_query(query)
  if sanitized == "BLOCKED":
      print(f"WARN: query '{query}' zablokowany — fallback TYPE_AI")
      return self._generate_bfl(scene.get("visual_prompt", "peaceful nature landscape"), idx)
  query = sanitized

def sanitize_query(query: str) -> str:
    query_lower = query.lower()
    for blocked_word in ["muslim", "mosque", "islamic", "quran", "hindu",
                          "buddha", "buddhist", "catholic", "cathedral",
                          "shrine", "temple", "prayer rug", "hijab",
                          "church interior", "altar", "rosary", "statue"]:
        if blocked_word in query_lower:
            return "BLOCKED"
    for unsafe, safe in SAFE_QUERY_MAP.items():
        if unsafe in query_lower:
            return safe
    return query

### Zmiany w director_system.txt

Dodaj do sekcji TYPE_VIDEO_STOCK:
"KRYTYCZNE dla search_query:
Nigdy nie używaj słów: muslim, mosque, islamic, quran, hindu, buddha,
buddhist, church interior, cathedral, shrine, altar, rosary, meditation,
prayer rug, hijab, pope, bishop

Dla modlitwy i kultu: opisuj AKCJĘ i MIEJSCE bez kontekstu religijnego:
  NIE: 'prayer hands', 'worship hands'
  TAK: 'person sitting quietly sunrise', 'hands open palms upward outdoor'

Bezpieczne queries dla Pexels:
  - przyroda: mountain, valley, lake, forest, field, ocean, sky, clouds
  - czas: sunrise, sunset, dawn, golden hour, morning mist
  - akcja neutralna: person walking, person sitting, arms raised sunset
  - światło: light rays, sunbeam, golden light, fog morning"

## Testy

test_sanitize_muslim:
    sanitize_query("muslim prayer hands") == "BLOCKED"

test_sanitize_meditation:
    sanitize_query("meditation person") != "meditation person"
    (zamieniony na bezpieczny odpowiednik)

test_sanitize_mountain:
    sanitize_query("mountain sunrise") == "mountain sunrise"
    (bezpieczny query pozostaje bez zmian)

test_blocked_fallback:
    Gdy sanitize_query zwraca "BLOCKED": router używa TYPE_AI
    Brak requestu do Pexels API

## Acceptance Criteria
- Żaden materiał muzułmański/hinduski/buddyjski nie pojawia się w wideo
- Queries zawierające zablokowane słowa automatycznie zastępowane lub blokowane
- Fallback do TYPE_AI gdy query jest niebezpieczny
- director_system.txt zawiera listę zakazanych słów dla queries
- Pexels używany TYLKO dla przyrody i bezpiecznych krajobrazów
- python3 -m pytest tests/test_stock_filtering.py -v przechodzi
