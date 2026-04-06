# Spec: Naprawa FFmpeg WOW effects — błąd eval_mode

## Problem
FFmpeg 7.1.1 zwraca:
"Expressions with frame variables 'n', 't', 'pos' are not valid in init eval_mode"

Filtr zoompan w wow_effects.py używa zmiennej 't' w wyrażeniu które
FFmpeg próbuje ewaluować w trybie init (przed pierwszą klatką).
To jest niedozwolone w FFmpeg 7.x.

## Poprawka w wow_effects.py

### Błędny filtr (używa 't' w init):
zoompan=z='if(between(t,0,0.1),1+0.08*(t/0.1),1)':...

### Poprawny filtr (używa 'n' z eval=frame):
zoompan=z='if(between(on,0,3),1+0.08*(on/3),if(between(on,3,12),1.08-0.08*((on-3)/9),1))':
d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':
fps=30:s=1920x1080

Gdzie:
  on = numer klatki (output frame number)
  3 klatki = 0.1s przy 30fps
  12 klatek = 0.4s przy 30fps

### Alternatywna strategia — pomiń zoompan, użyj prostszych filtrów

Zamiast skomplikowanego zoompan który crash'uje:
Użyj prostego eq filter dla color grade + vignette przez geq:

Color grade (verse):
  eq=saturation=0.85:brightness=0.02:contrast=1.05

Color grade (chorus):  
  eq=saturation=1.15:brightness=0.0:contrast=1.15

Vignette przez vignette filter (nie geq):
  vignette=angle=PI/4:mode=forward

LUT warm przez curves:
  curves=r='0/0 0.5/0.55 1/1':g='0/0 0.5/0.5 1/0.95':b='0/0 0.5/0.45 1/0.9'

### Najprostsza poprawka — wyłącz zoompan, zostaw resztę

W wow_effects.py gdy budowany jest filter_chain:
Usuń zoompan z filtru — zostaw tylko:
  eq (color grade)
  vignette
  curves (LUT)

Zoompan jest opcjonalny — reszta efektów działa i nie crashuje.
Dodaj flagę: ENABLE_ZOOMPAN = False  (domyślnie wyłączony)

## Fallback gdy WOW effects fail

W assembler.py lub wow_effects.py:
Gdy FFmpeg WOW effects zwraca błąd (rc != 0):
  Użyj oryginalnego pliku MoviePy bez WOW effects
  Wyświetl ostrzeżenie ale NIE rzucaj błędu
  NIE zwracaj "0 plików wygenerowanych"

  try:
      apply_wow_effects(input_path, output_path, ...)
  except Exception as e:
      print(f"WARN: WOW effects failed — używam bez efektów: {e}")
      shutil.copy(input_path, output_path)  # użyj oryginału

To zapewni że wideo ZAWSZE powstaje nawet gdy FFmpeg filtr nie działa.

## Acceptance Criteria
- FFmpeg nie zwraca błędu eval_mode
- Wideo generuje się nawet gdy WOW effects fail (fallback do oryginału)
- "Gotowe! Wygenerowano X plików" pokazuje > 0
- Color grade i vignette działają bez zoompan
