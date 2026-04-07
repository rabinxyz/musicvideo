# Spec: Naprawa rozmiaru promptu dla director — za dużo tokenów

## Problem
user_message do Claude ma 220505 tokenów > 200000 maksimum.
Winowajca: analysis zawiera energy_curve z tysiącami punktów
(jeden punkt co 512 sampli przy 44100Hz = ~86 punktów/sekundę).
Dla 5-minutowej piosenki: 300s * 86 = ~25800 punktów = tysiące tokenów.

## Poprawka w director.py w funkcji _build_user_message()

Przed wysłaniem analysis do Claude — wyczyść dane które nie są potrzebne
dyrektorowi do planowania scen:

def _build_user_message(analysis, style_override=None, mode=None):
    # Stwórz kopię analysis bez ciężkich pól
    analysis_for_director = {k: v for k, v in analysis.items()
                              if k != "energy_curve"}

    # Ogranicz beats do maksymalnie 100 wartości (co N-ty beat)
    beats = analysis_for_director.get("beats", [])
    if len(beats) > 100:
        step = len(beats) // 100
        analysis_for_director["beats"] = beats[::step][:100]

    # Ogranicz energy_peaks do maksymalnie 20 wartości
    peaks = analysis_for_director.get("energy_peaks", [])
    if len(peaks) > 20:
        analysis_for_director["energy_peaks"] = peaks[:20]

    # Ogranicz lyrics do maksymalnie 50 segmentów
    lyrics = analysis_for_director.get("lyrics", [])
    if len(lyrics) > 50:
        analysis_for_director["lyrics"] = lyrics[:50]

    # Użyj okrojonego analysis
    msg = f"Audio analysis:\n\n{json.dumps(analysis_for_director, indent=2)}"

    # reszta funkcji bez zmian...

## Acceptance Criteria
- Prompt do Claude < 50000 tokenów
- director nie dostaje energy_curve (niepotrzebne do planowania scen)
- beats ograniczone do 100 wartości
- energy_peaks ograniczone do 20 wartości
- lyrics ograniczone do 50 segmentów
- Brak BadRequestError 400 prompt too long
