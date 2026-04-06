# Idea

# Spec: Filtrowanie nieodpowiednich treści — alkohol, inne religie, nieodpowiednie zachowania

## Problem
Pexels i Unsplash zwracają materiały bez filtrowania treści.
Pojawiają się: alkohol, muzułmańska modlitwa, inne nieodpowiednie treści.

## Rozwiązanie — trzy poziomy

### Poziom 1 — zakazane słowa w search_query

Rozszerz listę BLOCKED_KEYWORDS w visual_router.py o:

BLOCKED_KEYWORDS = [
    # Religie nieprotestanckie
    "muslim", "islamic", "mosque", "quran", "hijab", "prayer rug",
    "hindu", "buddhist", "buddha", "temple", "shrine", "meditation",
    "catholic", "cathedral", "rosary", "pope", "nun", "monk",
    "orthodox", "icon religious",

    # Alkohol i używki
    "alcohol", "beer", "wine", "whiskey", "vodka", "drinking", "bar",
    "pub", "cocktail", "champagne", "toast drinking", "party alcohol",
    "nightclub", "drunk", "bottle alcohol",

    # Inne nieodpowiednie
    "gambling", "casino", "cigarette", "smoking", "drugs",
    "violence", "fight", "party wild", "nightlife",
]

### Poziom 2 — bezpieczne queries dla Pexels

Dodaj do NATURE_ONLY_KEYWORDS (Pexels tylko dla przyrody):
Pexels używamy WYŁĄCZNIE dla:
  krajobrazów, przyrody, nieba, wody, lasów, gór
  BEZ ludzi, BEZ aktywności, BEZ miejsc publicznych

Dla wszystkich scen z ludźmi → TYPE_AI (pełna kontrola promptu)

### Poziom 3 — zakazane elementy w promptach BFL Flux

Dodaj do documentary_suffix w image_generator.py:
", no alcohol, no drinking, no cigarettes, no gambling,
no Catholic imagery, no Islamic imagery, no Buddhist imagery,
no Hindu imagery, Protestant Christian context only,
no inappropriate content, family friendly"

### Poziom 4 — director_system.txt

Dodaj do listy ZAKAZANYCH elementów wizualnych:
"alkohol w jakiejkolwiek formie (piwo, wino, kieliszki, butelki),
palenie papierosów, hazard, narkotyki, przemoc,
imprezy z alkoholem, bary, kluby nocne,
muzułmańska modlitwa, świątynie hinduskie, posągi Buddy"

## Acceptance Criteria
- Żaden materiał z alkoholem nie pojawia się w wideo
- Żaden materiał z nieprotestanckimi symbolami religijnymi
- BLOCKED_KEYWORDS zawiera alkohol i inne religie
- Pexels używany tylko dla przyrody bez ludzi
- BFL prompty zawierają "no alcohol" w suffixie
