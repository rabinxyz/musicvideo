# Spec: Naprawa timingu napisów i Runway 400

## Problem 1 — napisy zaczynają się od 0.0s zamiast od ~30s

merge_whisper_with_lyrics_file() przypisuje linie z pliku
do segmentów Whisper ale timing wychodzi 0.0s bo:

Przypadek N_seg >= N_lines:
  group[0]["start"] pochodzi z Whispera — powinien być ~30s
  ALE gdy N_seg=20 i N_lines=36: wchodzimy w przypadek N_seg < N_lines
  gdzie tworzymy nowe timestamps proporcjonalnie zamiast używać Whisper timingów

Sprawdź w lyrics_parser.py:
  Wypisz N_seg i N_lines żeby zobaczyć który przypadek jest używany

Piosenka ma 20 segmentów Whisper i 36 linii w pliku:
  N_seg=20 < N_lines=36 → przypadek C
  Kod tworzy timestamps proporcjonalnie od 0 zamiast od vocal_start

Napraw przypadek C:
  Gdy N_seg < N_lines: podziel linie proporcjonalnie do segmentów Whisper
  Każda grupa linii dostaje timing odpowiadającego segmentu
  NIE twórz nowych timestamps od zera — używaj Whisper start/end

  ratio = N_lines / N_seg
  for i, seg in enumerate(whisper_lyrics):
      line_start = round(i * ratio)
      line_end = min(round((i + 1) * ratio), N_lines)
      group_lines = file_lines[line_start:line_end]
      if not group_lines:
          continue
      seg_duration = seg["end"] - seg["start"]
      time_per = seg_duration / len(group_lines)
      for j, line in enumerate(group_lines):
          merged.append({
              "start": round(seg["start"] + j * time_per, 2),
              "end": round(seg["start"] + (j + 1) * time_per - 0.15, 2),
              "text": line,
              "words": []
          })

Wynik: napisy zaczynają się od ~30s (timing Whispera) z tekstem z pliku.

## Problem 2 — Runway 400 Bad Request

Runway text-to-video wysyła zły payload.
Sprawdź video_animator.py funkcję generate_video_from_text().

Poprawny payload dla Runway Gen-4.5 text-to-video:
  POST https://api.dev.runwayml.com/v1/image_to_video
  {
    "model": "gen4.5",
    "promptText": "...",
    "duration": 5,
    "ratio": "1280:720"
  }
  BEZ pola "promptImage"

Częste przyczyny 400:
  a) promptText za długi (max ~500 znaków) — skróć do 200 znaków
  b) ratio nieprawidłowe — użyj "1280:720" nie "1280:768"
  c) model nieprawidłowy — sprawdź czy "gen4.5" jest prawidłowe,
     spróbuj "gen4_turbo" jako alternatywa
  d) brak wymaganego pola

Dodaj logowanie pełnego błędu API:
  except requests.HTTPError as e:
      print(f"Runway error body: {e.response.text}")
      raise

To pokaże dokładnie co Runway odrzuca.

Przetestuj curl bezpośrednio:
  curl -X POST https://api.dev.runwayml.com/v1/image_to_video \
    -H "Authorization: Bearer $RUNWAY_API_KEY" \
    -H "Content-Type: application/json" \
    -H "X-Runway-Version: 2024-11-06" \
    -d '{"model":"gen4.5","promptText":"Mountain at sunrise","duration":5,"ratio":"1280:720"}'

## Acceptance Criteria
- Pierwszy napis: tekst z pliku @ ~30s (nie 0.0s)
- lyrics[0]["start"] >= 25.0
- lyrics[0]["text"] == pierwsza linia z pliku tekst.txt
- Runway curl nie zwraca 400
- generate_video_from_text() loguje pełny błąd API gdy 400
