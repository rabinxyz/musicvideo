# Idea

# Spec 2: Animowane sceny nie mogą sąsiadować ze sobą

## Kontekst i historia problemu

Runway Gen-4 animuje co N-tą scenę (animate=True).
Problem: Claude-reżyser może wygenerować plan gdzie dwie animowane
sceny są obok siebie. Powoduje to że widz widzi dwa bardzo podobne
ruchy kamery jeden po drugim — wygląda to monotonnie i sztucznie.

Dodatkowo: animowane sceny powinny być rozłożone RÓWNOMIERNIE
przez cały teledysk — nie skupione w jednej części.

## Zasady rozmieszczenia animowanych scen

### Zasada 1: Minimum 2 nieanimowane sceny między każdą animowaną
Nie: [animate, animate, static, animate]
Tak: [animate, static, static, animate, static, static, animate]

### Zasada 2: Animowane sceny przy kulminacyjnych momentach
Priorytet dla animate=True:
  - Pierwsze wystąpienie refrenu (chorus_first)
  - Bridge (emocjonalny szczyt)
  - Ostatni refren przed outro
  - Intro (pierwsze 12s) — jeśli ma silny hook

Nigdy animate=True dla:
  - Outro (ostatnie 15s) — powinno być spokojne
  - Sceny z bardzo krótkim czasem trwania (< 6s) — za krótko dla Runway

### Zasada 3: Maksymalna liczba animowanych scen
max_animated = max(1, total_scenes // 4)
Np. dla 20 scen: max 5 animowanych
Np. dla 8 scen: max 2 animowane

### Zasada 4: Równomierne rozłożenie
Animowane sceny powinny być rozłożone w odstępach:
  ideal_gap = total_scenes / (max_animated + 1)
  Np. dla 20 scen i 5 animowanych: co ~4 sceny

## Implementacja

### Lokalizacja: musicvid/musicvid.py — po otrzymaniu scene_plan od Claude

Funkcja: enforce_animation_rules(scenes: list) -> list
  Modyfikuje listę scen in-place, zwraca poprawioną listę.

Algorytm:
  1. Zbierz indeksy scen z animate=True
  2. Sprawdź zasadę sąsiedztwa:
     for i in range(len(scenes) - 1):
         if scenes[i].get("animate") and scenes[i+1].get("animate"):
             # Wyłącz animację dla sceny o MNIEJSZEJ priorytecie
             # Priorytet: chorus > bridge > verse > intro > outro
             priority_i = get_section_priority(scenes[i]["section"])
             priority_next = get_section_priority(scenes[i+1]["section"])
             if priority_i >= priority_next:
                 scenes[i+1]["animate"] = False
             else:
                 scenes[i]["animate"] = False

  3. Sprawdź maksymalną liczbę animowanych:
     animated_indices = [i for i, s in enumerate(scenes) if s.get("animate")]
     max_animated = max(1, len(scenes) // 4)
     if len(animated_indices) > max_animated:
         # Wyłącz nadmiarowe — zachowaj te o najwyższym priorytecie
         excess = animated_indices[max_animated:]
         for idx in excess:
             scenes[idx]["animate"] = False

  4. Sprawdź czas trwania animowanych scen:
     for scene in scenes:
         if scene.get("animate"):
             duration = scene["end"] - scene["start"]
             if duration < 6.0:
                 scene["animate"] = False
                 print(f"WARN: Scena {scene['section']} za krótka ({duration:.1f}s) — Ken Burns fallback")

  5. Wypisz plan animacji:
     animated = [i for i, s in enumerate(scenes) if s.get("animate")]
     print(f"Plan animacji Runway: {len(animated)} scen z {len(scenes)}")
     for i in animated:
         s = scenes[i]
         print(f"  Scena {i}: {s['section']} @ {s['start']:.1f}-{s['end']:.1f}s")

def get_section_priority(section: str) -> int:
  Mapowanie sekcji na priorytet (wyższy = ważniejszy dla animacji):
    "chorus": 5
    "bridge": 4
    "verse": 3
    "intro": 2
    "outro": 0  (nigdy nie animuj outro)
    default: 1

### Dodaj enforce_animation_rules do pipeline

W musicvid.py po Stage 2 (director) i po Stage 3.5 setup:
  scene_plan["scenes"] = enforce_animation_rules(scene_plan["scenes"])

Wywołaj PRZED pętlą animowania — nie po.

### Zaktualizuj prompt Claude-reżysera w director.py

Dodaj do promptu:
"ZASADY DLA POLA animate:
- animate=True TYLKO dla: pierwszego refrenu, bridge, ostatniego refrenu
- animate=False dla: outro, scen < 6 sekund, dwóch sąsiednich scen
- Maksymalnie co 4. scena może mieć animate=True
- Dwie sceny animate=True nigdy obok siebie
- motion_prompt: opisuje RUCH KAMERY (nie treść obrazu)
  Przykłady dobrych motion_prompt:
  'Slow camera push forward through morning mist, gentle movement'
  'Camera slowly rises revealing valley below, clouds drift'
  'Subtle dolly back, light shifts from left to right gradually'
  Unikaj: 'beautiful scene', 'spiritual moment' — to treść, nie ruch"

## Testy

test_adjacent_animated:
  Input: [animate=True, animate=True, animate=False, animate=True]
  Output: [animate=True, animate=False, animate=False, animate=True]

test_max_animated:
  Input: 20 scen, 8 z animate=True
  Output: max 5 z animate=True (20 // 4 = 5)

test_short_scene:
  Input: scena 4s z animate=True
  Output: scena 4s z animate=False

test_outro_never_animated:
  Input: ostatnia scena (outro) z animate=True
  Output: animate=False

test_priority:
  Input: chorus(animate=True) obok verse(animate=True)
  Output: verse dostaje animate=False (niższy priorytet)

## Acceptance Criteria
- Brak dwóch animowanych scen obok siebie w żadnym teledysku
- Maksymalnie 25% scen animowanych (1 na 4)
- Outro nigdy nie jest animowane
- Sceny < 6s nigdy nie są animowane
- Log pokazuje plan animacji przed uruchomieniem Runway
- python3 -m pytest tests/test_animation_rules.py -v przechodzi
