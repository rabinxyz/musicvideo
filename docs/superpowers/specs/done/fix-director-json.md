# Spec: Naprawa uciętego JSON z Claude-reżysera

## Problem
director.py otrzymuje JSONDecodeError: Unterminated string.
Claude generuje plan scen który przekracza limit tokenów i JSON jest urwany.

## Przyczyna
max_tokens w wywołaniu Claude API jest za małe dla długich piosenek
z wieloma scenami. JSON urywa się w środku stringa.

## Poprawki w director.py

### 1. Zwiększ max_tokens
Zmień max_tokens z obecnej wartości na 4096.
Jeśli już jest 4096 — zmień na 8192.

### 2. Dodaj retry z wykrywaniem uciętego JSON
Po otrzymaniu odpowiedzi sprawdź czy JSON jest kompletny przed parsowaniem.
Jeśli json.loads() rzuca JSONDecodeError:
  Spróbuj naprawić JSON przez obcięcie do ostatniego kompletnego obiektu.
  Znajdź ostatnie "}" zamykające tablicę scenes.
  Jeśli naprawa niemożliwa: ponów wywołanie Claude z prośbą o krótsze prompty.

### 3. Ogranicz długość visual_prompt per scena
Dodaj do system prompt dyrektywę:
"Każdy visual_prompt musi mieć maksymalnie 200 znaków.
Bądź zwięzły i konkretny — nie pisz długich opisów."

### 4. Ogranicz liczbę scen
Dla piosenek dłuższych niż 3 minuty: max 10 scen.
Dla piosenek 3-5 minut: max 12 scen.
Dla piosenek powyżej 5 minut: max 15 scen.
Przekaż limit do Claude w prompcie: "Wygeneruj maksymalnie N scen."

### 5. Dodaj strip markdown przed parsowaniem
Przed json.loads() usuń ewentualne markdown backticks:
  text = text.strip()
  if text.startswith("```"):
    text = text.split("```")[1]
    if text.startswith("json"):
      text = text[4:]
  text = text.strip()

## Acceptance Criteria
- Piosenka "Tylko w Bogu" generuje plan scen bez JSONDecodeError
- visual_prompt każdej sceny ma max 200 znaków
- Retry gdy JSON jest ucięty
- python3 -m pytest tests/ -v przechodzi
