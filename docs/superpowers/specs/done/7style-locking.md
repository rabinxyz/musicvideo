# Spec: Style Locking — Visual Bible dla spójności kolorystycznej

## Problem
BFL generuje każde zdjęcie niezależnie — bez wiedzy o poprzednich scenach.
Efekt: każda scena może mieć inny klimat, paletę kolorów i nastrój.
Teledysk wygląda jak zlepek niepasujących obrazów zamiast spójnej całości.

## Rozwiązanie — Visual Bible

Przed generowaniem jakichkolwiek obrazów Claude tworzy "Visual Bible" —
szczegółowy dokument opisujący wygląd całego teledysku.
Każdy prompt obrazu jest budowany na bazie Visual Bible.

## Przepływ

Stage 1 — analiza audio (bez zmian)
Stage 1.5 — NOWY: Claude generuje Visual Bible
Stage 2 — reżyseria Claude (używa Visual Bible)
Stage 3 — generowanie obrazów (każdy prompt zawiera Visual Bible suffix)

## Struktura Visual Bible

Claude generuje JSON z polami:

{
  "overall_mood": string,
  Ogólny nastrój teledysku w 1 zdaniu.
  Przykład: "Contemplative and hopeful, like dawn breaking after a long night"

  "color_palette": {
    "primary": string,      hex dominujący kolor
    "secondary": string,    hex drugi kolor
    "accent": string,       hex kolor akcentu
    "shadows": string,      opis cieni (np. "deep blue-black, never pure black")
    "highlights": string,   opis świateł (np. "warm ivory, golden at peaks")
    "description": string   opis palety w 2 zdaniach
  },

  "lighting": {
    "quality": string,      np. "soft, diffused, golden hour"
    "direction": string,    np. "side lighting, rays from upper right"
    "time_of_day": string,  np. "golden hour, dawn, or dusk — never midday"
    "description": string   opis oświetlenia w 2 zdaniach
  },

  "composition": {
    "preferred_shots": [string],  np. ["wide establishing", "medium", "never close-up"]
    "depth": string,              np. "always foreground + background layers"
    "rule_of_thirds": bool,       czy stosować
    "description": string
  },

  "texture_and_atmosphere": string,
  Opis tekstury i atmosfery w 2 zdaniach.
  Przykład: "Slight haze and atmospheric depth. Soft bokeh in backgrounds.
  Photorealistic with painterly quality, never HDR or oversaturated."

  "forbidden_elements": [string],
  Lista elementów których absolutnie nie wolno używać w tej piosence.
  Claude wypełnia na podstawie tekstu i nastroju.

  "style_suffix": string
  Gotowy suffix do doklejenia do KAŻDEGO promptu obrazu.
  Maksymalnie 3 zdania — esencja Visual Bible w formie promptu.
  Przykład: "Consistent warm color grade with golden amber tones and
  soft blue shadows. Atmospheric haze and cinematic depth of field.
  Photorealistic, contemplative mood, golden hour lighting throughout."
}

## Prompt dla Claude przy generowaniu Visual Bible

System: używaj istniejącego director_system.txt

User:
Na podstawie tekstu i analizy muzycznej piosenki stwórz Visual Bible —
spójny przewodnik wizualny który zapewni że wszystkie sceny teledysku
tworzą harmonijną całość.

Visual Bible musi być:
- Spójna wewnętrznie (paleta kolorów pasuje do nastroju)
- Odpowiednia dla protestantzkiej muzyki uwielbienia
- Konkretna i opisowa — każdy element musi być mierzalny
  (nie "ciepłe kolory" ale "amber #B8860B jako dominanta")

Tekst piosenki: {lyrics_text}
BPM: {bpm}
Nastrój energetyczny: {mood_energy} (0=spokojny, 1=dynamiczny)
Sekcje: {sections}

Zwróć WYŁĄCZNIE czysty JSON bez markdown.

## Użycie Visual Bible w promptach

W director.py przy budowaniu visual_prompt dla każdej sceny:
  full_prompt = scene_prompt + " " + visual_bible["style_suffix"]

W image_generator.py:
  Przed wysłaniem do BFL sprawdź że prompt kończy się style_suffix.
  Nie modyfikuj style_suffix — doklejaj w całości.

## Cachowanie

Visual Bible cachowana w: output/tmp/{hash}/visual_bible.json
Zmiana audio invaliduje cache.
Visual Bible generowana PRZED planem scen — director używa jej jako kontekstu.

## Przekazanie do Claude-reżysera

Gdy director.py generuje plan scen, dostaje Visual Bible jako dodatkowy kontekst:

"Używaj poniższej Visual Bible przy planowaniu każdej sceny.
Każdy visual_prompt musi być spójny z opisaną paletą, oświetleniem
i kompozycją. Nie odchodź od ustalonego stylu.

Visual Bible: {visual_bible_json}"

## Walidacja promptów

Po wygenerowaniu planu scen przez Claude sprawdź każdy visual_prompt:
- Czy zawiera style_suffix (string matching)
- Czy nie zawiera elementów z forbidden_elements
Jeśli nie: dołącz style_suffix automatycznie.
Jeśli zawiera forbidden element: zaloguj ostrzeżenie
(nie blokuj — Claude wie co robi).

## Nowy moduł musicvid/pipeline/visual_bible.py

Funkcje:
- generate_visual_bible(analysis, lyrics_text) -> dict
  Wywołuje Claude API, zwraca dict Visual Bible.
  Cachuje w tmp/visual_bible.json.

- get_style_suffix(visual_bible) -> str
  Zwraca visual_bible["style_suffix"] — gotowy do doklejenia.

- validate_prompt(prompt, visual_bible) -> (bool, str)
  Sprawdza prompt pod kątem forbidden_elements i style_suffix.
  Zwraca (is_valid, reason).

- apply_style_to_plan(scene_plan, visual_bible) -> scene_plan
  Dla każdej sceny w planie: doklejа style_suffix do visual_prompt
  jeśli jeszcze go nie zawiera.

## Integracja w musicvid.py

Nowa kolejność Stage 2:
  visual_bible = generate_visual_bible(analysis, lyrics_text)
  scene_plan = director.create_plan(analysis, visual_bible)
  scene_plan = apply_style_to_plan(scene_plan, visual_bible)

Wyświetl po wygenerowaniu Visual Bible:
  "[2/4] Visual Bible: {overall_mood}"
  "       Paleta: {primary} + {secondary} + {accent}"

## Nowa flaga CLI
--no-style-lock  Wyłącz Visual Bible (szybciej, mniej spójnie)

## Testy
- generate_visual_bible: mockuj Claude API, sprawdź strukturę JSON
- get_style_suffix: zwraca niepusty string
- validate_prompt: prompt bez style_suffix → is_valid=False
- validate_prompt: prompt z forbidden_element → ostrzeżenie w logach
- apply_style_to_plan: każdy visual_prompt zawiera style_suffix po wywołaniu
- Cache: drugi run nie wywołuje Claude (wczytuje z pliku)
- --no-style-lock: visual_bible nie generowana, prompty bez suffix

## Acceptance Criteria
- Visual Bible generowana przed planem scen
- Każdy prompt obrazu kończy się style_suffix z Visual Bible
- Wszystkie sceny mają spójną paletę kolorów i nastrój
- Visual Bible cachowana — nie generuje się ponownie przy --new nie podanym
- "[2/4] Visual Bible: ..." wyświetlane w logach z nazwą nastroju i paletą
- --no-style-lock wyłącza mechanizm
- python3 -m pytest tests/ -v przechodzi
