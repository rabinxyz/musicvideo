# Spec: Naprawa wymiarów obrazów dla BFL API

## Problem
BFL flux-dev zwraca błąd 422 dla wymiarów 1280x720.
Curl z wymiarami 1024x768 zwraca poprawną odpowiedź.

## Poprawka
W image_generator.py zmień wymiary w payload z:
  width: 1280, height: 720
na:
  width: 1024, height: 768

To jest jedyna zmiana — reszta kodu jest poprawna.

## Acceptance Criteria
- python3 -m musicvid.musicvid song.mp3 --mode ai --provider flux-dev
  nie zwraca błędu 422
- Obrazy są generowane i zapisywane poprawnie
