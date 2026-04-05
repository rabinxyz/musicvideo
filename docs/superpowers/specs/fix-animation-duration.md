# Spec: Naprawa progu długości sceny dla animacji Runway

## Problem
Próg minimalnej długości sceny dla animate=True wynosi 6s.
Sceny refrenu przy wolniejszym BPM naturalnie wychodzą 4-5s.
Efekt: sceny chorus i bridge nigdy nie są animowane — fallback do Ken Burns.

## Poprawka w musicvid.py — funkcja enforce_animation_rules()

Zmień próg minimalnej długości:
  Stary próg: duration < 6.0
  Nowy próg:  duration < 3.0

Runway Gen-4 akceptuje wideo od 2 do 16 sekund.
Dla scen 4-5s Runway działa poprawnie.

## Poprawka — duration dla Runway

W _animate_runway() lub animate_image():
Gdy scena trwa mniej niż 5s użyj duration=5 (minimum Runway).
Gdy scena trwa 5-10s użyj duration=5.
Gdy scena trwa > 10s użyj duration=10 (maksimum sensowne).

  runway_duration = 5  # zawsze 5s — Runway generuje stałą długość
  Assembler przytnie wideo do faktycznej długości sceny przez subclipped()

## Acceptance Criteria
- Sceny >= 3s mogą być animowane przez Runway
- Sceny chorus 4-5s są animowane (nie Ken Burns fallback)
- Runway zawsze dostaje duration=5 niezależnie od długości sceny
- Assembler przycina wideo Runway do faktycznej długości sceny
