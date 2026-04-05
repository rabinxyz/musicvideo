# Spec: Naprawa parsowania odpowiedzi Runway API

## Problem
_poll_animation() w video_animator.py rzuca:
"string indices must be integers, not 'str'"
Oznacza to że data["output"][0] zwraca string zamiast dict,
więc data["output"][0]["url"] nie działa.

## Przyczyna
Runway API Gen-4 zwraca output jako lista stringów (URLi) a nie
lista dictów z polem "url".

Prawdopodobna struktura odpowiedzi:
{
  "status": "SUCCEEDED",
  "output": ["https://...video_url..."]  ← lista stringów, nie dictów
}

Zamiast:
{
  "status": "SUCCEEDED",
  "output": [{"url": "https://..."}]   ← tego oczekuje kod
}

## Poprawka w video_animator.py w funkcji _poll_animation()

Zmień:
  return data["output"][0]["url"]

Na kod który obsługuje oba formaty:
  output = data["output"]
  if isinstance(output, list) and len(output) > 0:
      first = output[0]
      if isinstance(first, str):
          return first           # lista stringów — bezpośredni URL
      elif isinstance(first, dict):
          return first.get("url") or first.get("uri") or first.get("link")
  raise RuntimeError(f"Nieoczekiwana struktura output: {output}")

## Dodaj logowanie odpowiedzi API dla debugowania

W _poll_animation() gdy status == "SUCCEEDED" dodaj:
  print(f"DEBUG Runway output: {data.get('output')}")
przed zwróceniem URL — żeby zobaczyć dokładną strukturę.

Usuń ten print po weryfikacji że działa.

## Acceptance Criteria
- animate_image() nie rzuca "string indices must be integers"
- animated_scene_NNN.mp4 powstają w cache
- Runway generuje wideo dla scen z animate=True
