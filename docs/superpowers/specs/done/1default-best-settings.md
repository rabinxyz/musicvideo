# Spec: Domyślne ustawienia dla najlepszego teledysku

## Cel
Zmiana domyślnych wartości flag CLI tak żeby samo:
python3 -m musicvid.musicvid piosenka.mp3
generowało najbardziej rozbudowany i profesjonalny teledysk bez żadnych
dodatkowych opcji.

## Zmiany domyślnych wartości w musicvid.py

Zmień default= dla każdej opcji Click:

--mode:            "stock"   → "ai"
--provider:        "flux-dev" → "flux-pro"
--preset:          None      → "all"
--effects:         "none"    → "minimal"
--animate:         "never"   → "auto"
--subtitle-style:  "fade"    → "karaoke"
--transitions:     "cut"     → "auto"
--lut-style:       None      → "warm"
--lut-intensity:   0.85      → 0.85 (bez zmian)
--beat-sync:       "off"     → "auto"
--resolution:      "1080p"   → "1080p" (bez zmian)
--reel-duration:   15        → 15 (bez zmian)

## Komunikat startowy

Gdy użytkownik odpala bez żadnych flag wyświetl czytelne podsumowanie
co będzie generowane:

  MusicVid — tryb pełny
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Obrazy:      BFL Flux Pro (AI)
  Animacje:    Runway Gen-4 (co 3. scena)
  Preset:      Pełny teledysk + 3 rolki 15s
  Efekty:      Warm grade + vignette
  Napisy:      Karaoke style
  Przejścia:   Auto (Claude dobiera)
  Color grade: LUT Warm
  Beat sync:   Włączony
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Szacowany czas: ~15-20 minut
  Szacowany koszt: ~$0.80 (Flux Pro + Runway)
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Kontynuować? [T/n]:

Flaga --yes lub --batch-yes pomija potwierdzenie.

## Tryb szybki --quick

Dodaj nową flagę --quick która ustawia szybkie ale gorsze ustawienia:
  --mode stock (Pexels, bez kosztów API)
  --preset full (tylko pełny teledysk, bez rolek)
  --effects none
  --animate never
  --subtitle-style fade
  --transitions cut
  --lut-style None
  --beat-sync off

Użycie: python3 -m musicvid.musicvid piosenka.mp3 --quick
Dla testów i podglądów bez wydawania kredytów API.

## Tryb ekonomiczny --economy

Dodaj flagę --economy dla niższych kosztów przy dobrej jakości:
  --mode ai
  --provider flux-dev (tańszy niż pro)
  --preset full (tylko pełny teledysk)
  --effects minimal
  --animate never (bez Runway)
  --subtitle-style karaoke
  --transitions auto
  --lut-style warm
  --beat-sync auto

Koszt: ~$0.15 zamiast ~$0.80

## Zachowanie gdy brak kluczy API

Gdy BFL_API_KEY brak a --mode ai (domyślny):
Wyświetl czytelny komunikat:
  "Brak BFL_API_KEY — przełączam na tryb stock (Pexels).
   Aby używać AI obrazów: dodaj BFL_API_KEY do .env
   Rejestracja: https://bfl.ai/dashboard"
Kontynuuj z --mode stock zamiast rzucać błąd.

Gdy RUNWAY_API_KEY brak a --animate auto (domyślny):
Wyświetl:
  "Brak RUNWAY_API_KEY — animacje wyłączone (Ken Burns zamiast Runway).
   Aby używać Runway: dodaj RUNWAY_API_KEY do .env
   Rejestracja: https://app.runwayml.com"
Kontynuuj z --animate never zamiast rzucać błąd.

## Acceptance Criteria
- python3 -m musicvid.musicvid piosenka.mp3 używa flux-pro, preset all,
  karaoke, warm LUT, beat-sync, effects minimal
- Komunikat startowy wyświetla podsumowanie ustawień i pyta o potwierdzenie
- --quick przełącza na szybki tryb stock bez kosztów
- --economy używa flux-dev bez Runway
- Brak BFL_API_KEY: automatyczny fallback do stock z komunikatem
- Brak RUNWAY_API_KEY: automatyczny fallback do Ken Burns z komunikatem
- --yes pomija potwierdzenie
- python3 -m pytest tests/ -v przechodzi
