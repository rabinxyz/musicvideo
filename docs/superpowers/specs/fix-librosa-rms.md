# Spec: Naprawa librosa.feature.rms() — nieoczekiwany argument sr

## Problem
librosa.feature.rms() w nowszych wersjach nie przyjmuje parametru sr.
TypeError: rms() got an unexpected keyword argument 'sr'

## Poprawka w audio_analyzer.py

Znajdź wszystkie wywołania librosa.feature.rms() z parametrem sr:
  rms = librosa.feature.rms(y=y, sr=sr, hop_length=512)[0]

Zmień na:
  rms = librosa.feature.rms(y=y, hop_length=512)[0]

Usuń parametr sr z każdego wywołania librosa.feature.rms() w pliku.

## Acceptance Criteria
- analyze_audio() nie rzuca TypeError
- energy_curve jest obliczane poprawnie
