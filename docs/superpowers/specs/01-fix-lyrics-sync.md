# Spec 1: Synchronizacja tekstu — sekwencyjne dopasowanie Whisper + plik lyrics

## Kontekst i historia problemu

Mamy dwa źródła danych:
- Whisper: niedokładny tekst ale DOBRY timing (start/end każdego segmentu)
- plik tekst.txt: DOKŁADNY tekst ale brak timingu

Poprzednie próby rozwiązania:
1. Tylko Whisper — tekst błędny (szczególnie polskie słowa)
2. AI matching (Claude dopasowuje) — niedokładny, gubił kolejność
3. Sekwencyjne grupowanie — gubił linie gdy N segmentów != M linii

Obecny problem: napisy pojawiają się ale w złym czasie względem muzyki.

## Wymaganie

Zsynchronizować DOKŁADNY tekst z pliku z DOBRYM timingiem z Whisper.
Napisy muszą pojawiać się dokładnie gdy słyszysz daną frazę w muzyce.

## Algorytm — sekwencyjne proporcjonalne dopasowanie

### Krok 1: Przygotowanie danych

Whisper segments (po filtracji pustych):
  segments = [s for s in whisper_result["segments"] if s["text"].strip()]
  Każdy segment: {start: float, end: float, text: str}

Linie z pliku (po filtracji pustych i whitespace):
  lines = [l.strip() for l in file_content.split('\n') if l.strip()]
  Ignoruj linie które są tylko interpunkcją lub mają < 2 znaki

### Krok 2: Przypadek A — N_segments == N_lines (idealne)
Przypisz 1:1:
  result = []
  for i, (seg, line) in enumerate(zip(segments, lines)):
      result.append({
          "start": seg["start"],
          "end": seg["end"],
          "text": line
      })

### Krok 3: Przypadek B — N_segments > N_lines (więcej segmentów niż linii)
Np. Whisper wykrył 20 segmentów ale plik ma 12 linii.
Każda linia dostaje grupę segmentów proporcjonalnie:

  segments_per_line = N_segments / N_lines  # może być float np. 1.67

  result = []
  for i, line in enumerate(lines):
      seg_start_idx = round(i * segments_per_line)
      seg_end_idx = round((i + 1) * segments_per_line)
      seg_end_idx = min(seg_end_idx, N_segments)

      group = segments[seg_start_idx:seg_end_idx]
      if not group:
          continue

      result.append({
          "start": group[0]["start"],
          "end": group[-1]["end"],
          "text": line
      })

### Krok 4: Przypadek C — N_segments < N_lines (więcej linii niż segmentów)
Np. Whisper wykrył 8 segmentów ale plik ma 20 linii.
Podziel każdy segment na podgrupy linii proporcjonalnie:

  result = []
  lines_per_seg = N_lines / N_segments

  for i, seg in enumerate(segments):
      line_start_idx = round(i * lines_per_seg)
      line_end_idx = round((i + 1) * lines_per_seg)
      line_end_idx = min(line_end_idx, N_lines)

      group_lines = lines[line_start_idx:line_end_idx]
      if not group_lines:
          continue

      seg_duration = seg["end"] - seg["start"]
      time_per_line = seg_duration / len(group_lines)

      for j, line in enumerate(group_lines):
          result.append({
              "start": seg["start"] + j * time_per_line,
              "end": seg["start"] + (j + 1) * time_per_line,
              "text": line
          })

### Krok 5: Korekta timingu

Po zbudowaniu result:

1. Minimum gap między napisami: 0.15s
   Jeśli result[i]["end"] > result[i+1]["start"] - 0.15:
       result[i]["end"] = result[i+1]["start"] - 0.15

2. Napis nie może trwać krócej niż 0.8s:
   Jeśli duration < 0.8s: rozszerz end do start + 0.8

3. Napis nie może trwać dłużej niż 8s (jeśli tak — segment był za długi):
   Jeśli duration > 8s: ogranicz end do start + 8

4. Offset -0.05s na początku każdego napisu:
   result[i]["start"] = max(0, result[i]["start"] - 0.05)
   (widz zdąży przeczytać zanim usłyszy)

### Krok 6: Walidacja końcowa

Sprawdź że:
- Żaden napis nie wychodzi poza czas trwania audio
- Napisy są posortowane chronologicznie
- Brak duplikatów
- Każdy napis ma niepusty text

Wypisz statystyki:
  print(f"Dopasowano: {len(result)} napisów")
  print(f"Whisper segmentów: {N_segments}, Linii w pliku: {N_lines}")
  print(f"Pierwsza linia: '{result[0]['text']}' @ {result[0]['start']:.1f}s")
  print(f"Ostatnia linia: '{result[-1]['text']}' @ {result[-1]['start']:.1f}s")

## Implementacja

### Lokalizacja: musicvid/pipeline/lyrics_parser.py
Stwórz lub zastąp funkcję:
  merge_whisper_with_lyrics_file(whisper_segments, lyrics_lines, audio_duration) -> list[dict]

Implementuj dokładnie algorytm powyżej.

### Integracja w audio_analyzer.py lub musicvid.py
Gdy lyrics_path jest dostępny (z --lyrics lub auto-wykryty):
  whisper_result = model.transcribe(audio_path, word_timestamps=True)
  whisper_segments = [s for s in whisper_result["segments"] if s["text"].strip()]
  lyrics_lines = read_lyrics_file(lyrics_path)
  analysis["lyrics"] = merge_whisper_with_lyrics_file(
      whisper_segments, lyrics_lines, analysis["duration"]
  )

Gdy lyrics_path NIE jest dostępny:
  Użyj segments z Whisper bezpośrednio (tekst z Whisper, timing z Whisper)
  analysis["lyrics"] = [{"start": s["start"], "end": s["end"], "text": s["text"]}
                         for s in whisper_segments]

## Testy

test_case_1: N_segments==N_lines (8 i 8)
  Każda linia ma timing odpowiadającego segmentu
  result[3]["text"] == lines[3]
  result[3]["start"] == segments[3]["start"]

test_case_2: N_segments > N_lines (12 segmentów, 6 linii)
  6 wyników
  result[0]["start"] == segments[0]["start"]
  result[5]["end"] == segments[11]["end"]

test_case_3: N_segments < N_lines (4 segmenty, 12 linii)
  12 wyników
  Każda linia w oknie czasowym swojego segmentu

test_case_4: Korekta timingu
  Napisy nie nachodzą na siebie (gap >= 0.15s)
  Żaden napis < 0.8s

test_case_5: Pusty plik lyrics
  ValueError z komunikatem

test_case_6: Plik z pustymi liniami
  Puste linie ignorowane przed dopasowaniem

## Acceptance Criteria
- Napisy pojawiają się sekwencyjnie w tym samym czasie co słyszysz tekst
- Tekst pochodzi z pliku tekst.txt (poprawna polszczyzna)
- Timing pochodzi z Whisper (zsynchronizowany z muzyką)
- Działa dla wszystkich trzech przypadków N_seg vs N_lines
- python3 -m pytest tests/test_lyrics_parser.py -v przechodzi
