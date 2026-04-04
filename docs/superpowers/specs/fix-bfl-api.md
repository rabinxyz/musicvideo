# Spec: Naprawa wywołania BFL API (błąd 422)

## Problem
Kod wysyła błędne parametry do BFL API co powoduje błąd 422 Unprocessable Entity.
Dwa konkretne błędy do naprawy:

## Błąd 1 — złe nazwy endpointów
Obecny kod używa: /v1/flux-dev, /v1/flux-pro, /v1/flux-schnell
Poprawne nazwy endpointów według oficjalnej dokumentacji BFL:
- flux-dev     → /v1/flux-dev (to akurat poprawne)
- flux-pro     → /v1/flux-pro-1.1
- flux-schnell → brak w aktualnym API — zastąp przez /v1/flux-2-klein-4b

Zaktualizuj mapowanie MODEL_MAP w image_generator.py.

## Błąd 2 — polling przez zły URL
Obecny kod polluje: GET /v1/get_result?id={task_id}
Poprawne podejście: BFL API zwraca pole polling_url w odpowiedzi na POST.
Należy użyć tego polling_url do sprawdzania statusu — nie konstruować URL ręcznie.

Zmień _poll_result tak żeby przyjmował polling_url (string) zamiast task_id.
Zmień _submit_task tak żeby zwracał krotkę (task_id, polling_url).

## Błąd 3 — nieprawidłowe parametry żądania
Usuń z body żądania parametry których BFL nie obsługuje:
- safety_tolerance
- output_format
- prompt_upsampling

Zostaw tylko parametry które BFL akceptuje:
- prompt (string, wymagany)
- width (int)
- height (int)

## Poprawny przepływ
1. POST https://api.bfl.ai/v1/{model} z {prompt, width, height}
   → zwraca {id, polling_url}
2. GET {polling_url} z nagłówkiem x-key
   → polluj co 1.5s aż status == "Ready"
   → gdy Ready: result.sample zawiera URL obrazu
3. Pobierz obraz przez requests.get(result.sample)

## Nagłówek autoryzacji
Używaj: x-key: {BFL_API_KEY}
Nie używaj: Authorization: Bearer

## Testy
Zaktualizuj mocki żeby odpowiadały nowemu przepływowi:
- POST zwraca {id: "uuid", polling_url: "https://..."}
- GET polling_url zwraca kolejno {status: "Pending"} potem {status: "Ready", result: {sample: "https://..."}}

## Acceptance Criteria
- python3 -m musicvid.musicvid song.mp3 --mode ai --provider flux-dev
  nie zwraca błędu 422
- Obrazy są pobierane i zapisywane poprawnie
- python3 -m pytest tests/ -v przechodzi
