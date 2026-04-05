# Idea

# Spec: Zmiana domyślnej długości rolek na 30 sekund

## Uzasadnienie
Analiza danych z 2025-2026 pokazuje że dla muzyki chrześcijańskiej
optymalny czas rolki promującej teledysk to 30 sekund:
- 15s za krótko żeby pieśń uwielbienia "weszła" emocjonalnie
- 30s pozwala pokazać pełny refren z napisami i obrazem AI
- 30s mieści się w "Goldilocks zone" algorytmu Instagram/FB
- Wyższy completion rate niż 60s przy zachowaniu pełnego przekazu

## Zmiana w musicvid.py

Zmień domyślną wartość --reel-duration z 15 na 30:
  --reel-duration [15|20|25|30|45|60]  default=30

Dodaj do dostępnych opcji: 45 i 60 sekund.

## Zmiana w clip_selections — logika wyboru fragmentu

Gdy reel_duration=30 Claude wybiera fragment który zawiera:
- Pełny refren (priorytet najwyższy)
- Wyraźny hook melodyczny
- Kompletną myśl tekstową (nie urwane zdanie)
- Zaczyna się na początku frazy muzycznej
- Kończy na naturalnej pauzie lub końcu frazy

## Zmiana w komunikacie startowym

Zaktualizuj _print_startup_summary():
  "Rolki social:   3 × 30s z różnych fragmentów"
  zamiast:
  "Rolki social:   3 × 15s z różnych fragmentów"

## Acceptance Criteria
- python3 -m musicvid.musicvid --help pokazuje domyślnie 30 dla --reel-duration
- Generowane rolki mają długość ~30 sekund
- Dostępne opcje: 15, 20, 25, 30, 45, 60
- Komunikat startowy pokazuje poprawną długość
