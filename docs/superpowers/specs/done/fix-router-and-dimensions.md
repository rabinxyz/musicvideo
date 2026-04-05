# Spec: Naprawa visual_router i wymiarów BFL

## Problem 1 — wymiary 1360x768 odrzucane przez BFL (błąd 422)

BFL flux-pro-1.1 nie akceptuje niestandardowych wymiarów.
Przywróć sprawdzone wymiary które działały: width=1024, height=768.
Zmień w image_generator.py: width=1024, height=768.
Nie używaj 1360x768 — BFL to odrzuca.

## Problem 2 — _route_photo_stock robi fallback do BFL zamiast Pexels

Gdy brak UNSPLASH_ACCESS_KEY, _route_photo_stock() wywołuje
_generate_bfl() co kosztuje kredyty. Zamiast tego:

Fallback hierarchy dla TYPE_PHOTO_STOCK:
1. Unsplash (gdy UNSPLASH_ACCESS_KEY dostępny)
2. Pexels wideo z tym samym search_query (gdy PEXELS_API_KEY dostępny)
3. BFL Flux (tylko gdy oba klucze stock niedostępne)

Zmień _route_photo_stock() na:
  if unsplash_key:
      return _fetch_unsplash(query, idx)
  elif pexels_key:
      return _fetch_pexels(query, idx, duration)
  else:
      print(f"WARN: Brak kluczy stock — fallback TYPE_AI dla sceny {idx}")
      return _generate_bfl(visual_prompt or query, idx)

## Problem 3 — fallback hierarchy dla wszystkich typów

Zaimplementuj pełną hierarchię fallback w visual_router.py:

TYPE_VIDEO_STOCK:
  1. Pexels z search_query
  2. Pexels z uproszczonym query (pierwsze 2 słowa)
  3. BFL Flux z visual_prompt (gdy visual_prompt nie None)
  4. BFL Flux z "nature landscape peaceful" jako domyślny prompt

TYPE_PHOTO_STOCK:
  1. Unsplash z search_query
  2. Pexels z search_query
  3. BFL Flux z visual_prompt lub search_query

TYPE_AI:
  1. BFL Flux z visual_prompt
  (brak fallback — jeśli BFL nie działa rzuć błąd)

TYPE_ANIMATED:
  1. BFL Flux + Runway
  2. Fallback: BFL Flux + Ken Burns (gdy brak RUNWAY_API_KEY)

## Problem 4 — loguj który typ i query używa każda scena

Przed route() każdej sceny wypisz:
  source = scene.get("visual_source", "TYPE_AI")
  query = scene.get("search_query", "")
  prompt_preview = (scene.get("visual_prompt") or "")[:50]
  print(f"  [{idx+1}/{total}] {scene['section']} | {source} | "
        f"{'query: ' + query if query else 'prompt: ' + prompt_preview}")

## Acceptance Criteria
- BFL wywołania używają width=1024, height=768 (bez 422)
- TYPE_PHOTO_STOCK bez Unsplash klucza: fallback do Pexels nie do BFL
- Każda scena loguje source, query lub prompt przed generowaniem
- Pipeline nie crashuje gdy brakuje któregokolwiek klucza API
