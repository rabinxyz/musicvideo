# Spec: Zmiana providera obrazów na oficjalne BFL API (Black Forest Labs)

## Kontekst
Zastąp obecny generator obrazów oficjalnym API producenta Flux —
Black Forest Labs dostępnym pod adresem bfl.ai.
Dokumentacja API: https://docs.bfl.ai

## Klucz API
Zmienna środowiskowa: BFL_API_KEY
Usuń z .env.example: FAL_KEY, OPENAI_API_KEY
Dodaj do .env.example: BFL_API_KEY (klucz z bfl.ai/dashboard)

## Modele i flaga --provider

Obsłuż trzy opcje:
- flux-pro → model flux-pro1.1 (najwyższa jakość)
- flux-dev → model flux-dev (domyślny, dobry balans)
- flux-schnell → model flux-schnell (najszybszy, najtańszy)

Domyślna wartość --provider: flux-dev

## Jak działa BFL API

BFL API jest asynchroniczne — trzyetapowy przepływ:
1. Wyślij zadanie POST do /v1/{model-name} z promptem → dostaniesz task id
2. Polluj GET /v1/get_result?id={task-id} co 1-2 sekundy
3. Gdy status == "Ready" → w odpowiedzi jest URL do obrazu → pobierz go

Endpoint bazowy: https://api.bfl.ai
Autoryzacja: nagłówek X-Key z wartością BFL_API_KEY

Parametry żądania:
- prompt: tekst promptu sceny
- width: 1280
- height: 720
- output_format: jpeg

Obsłuż timeout pollingu — jeśli po 120 sekundach status nadal nie Ready,
rzuć błąd z informacją że zadanie się nie ukończyło.

## Strategia promptów (bez zmian względem poprzedniego spec)

Główny prompt: wyłącznie pozytywne opisy, nigdy negatywne.
Nigdy nie używaj w prompcie słów:
Catholic, rosary, Madonna, saint, crucifix, stained glass,
church interior, religious, icon, Byzantine, papal,
prayer beads, monastery, monk, nun, cathedral, shrine, altar

Każdy prompt = [motyw] + [oświetlenie] + [nastrój] + styl techniczny na końcu:
"cinematic 16:9, photorealistic, high quality"

Negative prompt: przekaż jako osobny parametr API jeśli BFL go obsługuje.
Jeśli nie obsługuje — pomiń, polegaj wyłącznie na pozytywnym prompcie.

## Wymagania niefunkcjonalne

- Retry z exponential backoff (max 3 próby) na błędach sieciowych i 5xx
- Nie rób retry na błędach 4xx (zły klucz, zły model) — rzuć od razu
- Każda scena loguje postęp: "Scena N/M gotowa"
- Brak BFL_API_KEY: czytelny błąd z instrukcją gdzie się zarejestrować
- Nieznany --provider: czytelny błąd z listą dostępnych opcji
- Usuń zależność fal-client z requirements.txt

## Testy

Zamockuj requests.post i requests.get.
Pokryj przypadki:
- poprawny przepływ submit → polling → download
- polling z kilkoma odpowiedziami Pending przed Ready
- timeout po 120 sekundach
- brak BFL_API_KEY
- nieznany provider
- błąd 5xx z poprawnym retry

## Acceptance Criteria
- --mode ai --provider flux-dev generuje obrazy przez BFL API
- --mode ai --provider flux-pro i flux-schnell działają analogicznie
- Domyślnie używa flux-dev bez podawania flagi
- Brak fal-client w requirements.txt
- Wszystkie testy przechodzą: python3 -m pytest tests/ -v
