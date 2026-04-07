# Spec: Synchronizacja napisów — fuzzy match z cursor (sliding window)

## Koncepcja
Profesjonalne podejście do synchronizacji karaoke:
- Plik tekstu = ciągły strumień słów (bez podziału na linie)
- Whisper = timing + niedokładny tekst (literówki, złączone słowa)
- Cursor = pozycja w strumieniu słów gdzie skończyliśmy ostatnie dopasowanie
- Dla każdego segmentu Whispera: szukaj pasującego fragmentu OD cursor wzwyż

## Przygotowanie tekstu z pliku

### Krok 1 — jeden ciągły strumień słów
  import re

  with open(lyrics_path, encoding='utf-8') as f:
      raw = f.read()

  # Usuń didaskalia w nawiasach: [Refren:], [x2], [Bridge], itp.
  raw = re.sub(r'\[.*?\]', '', raw, flags=re.DOTALL)

  # Podziel na słowa — ignoruj podział na linie
  all_words = re.findall(r'\b\w+\b', raw, re.UNICODE)
  # all_words = ['Tylko', 'w', 'Bogu', 'moje', 'jest', 'zbawienie', ...]

  # Ciągły string do fuzzy matchowania (małe litery, bez interpunkcji)
  word_string = ' '.join(w.lower() for w in all_words)

## Algorytm sliding cursor fuzzy match

### Krok 2 — przetwórz segmenty Whispera

  from rapidfuzz import fuzz

  cursor = 0          # pozycja ZNAKOWA w word_string gdzie zaczyna szukanie
  result_lyrics = []  # wynikowa lista napisów

  for seg in vocal_segments:  # segmenty bez szumu
      whisper_raw = seg['text'].strip()
      # Oczyść tekst Whispera — małe litery, tylko litery i spacje
      whisper_clean = ' '.join(re.findall(r'\b\w+\b', whisper_raw.lower()))

      if not whisper_clean or len(whisper_clean) < 3:
          continue

      # Okno szukania: od cursor do cursor + max_window
      # Zakładamy że Whisper może "rozjechać się" o max 2x długość segmentu
      max_window = max(300, len(whisper_clean) * 6)
      search_text = word_string[cursor:cursor + max_window]

      if not search_text.strip():
          break  # koniec tekstu

      # Sliding window — szukaj najlepiej pasującego podciągu
      target_len = len(whisper_clean)
      best_ratio = 0
      best_pos = 0  # pozycja w search_text (nie w word_string)

      # Krok przesunięcia okna — mały żeby nie przeoczyć
      step = max(1, target_len // 8)

      for i in range(0, max(1, len(search_text) - target_len + 1), step):
          # Weź fragment o długości ~1.5x długości segmentu Whispera
          window = search_text[i:i + int(target_len * 1.5)]
          ratio = fuzz.partial_ratio(whisper_clean, window)
          if ratio > best_ratio:
              best_ratio = ratio
              best_pos = i

      # Próg akceptacji — minimum 45% podobieństwo
      MIN_RATIO = 45

      if best_ratio >= MIN_RATIO:
          # Znajdź odpowiednie słowa ORYGINALNEGO tekstu (z interpunkcją)
          # best_pos to pozycja znakowa w search_text (= word_string od cursor)
          abs_pos = cursor + best_pos
          matched_len = int(target_len * 1.3)

          # Przelicz pozycję znakową na indeks słowa
          words_before_cursor = word_string[:abs_pos].split()
          word_idx = len(words_before_cursor)

          # Liczba słów w dopasowaniu (szacuj z długości)
          n_words = max(1, len(whisper_clean.split()))
          original_words = all_words[word_idx:word_idx + n_words]
          matched_text = ' '.join(original_words)

          result_lyrics.append({
              'start': seg['start'],
              'end': seg['end'],
              'text': matched_text,
              'match_ratio': best_ratio,
              'words': []
          })

          # Przesuń cursor NA KONIEC dopasowania
          # Następne szukanie zaczyna się STĄD
          new_cursor = abs_pos + matched_len
          cursor = min(new_cursor, len(word_string))

          print(f"  {seg['start']:.1f}s: '{matched_text}' (ratio={best_ratio})")
      else:
          # Słabe dopasowanie — użyj tekstu z Whispera jako fallback
          print(f"  WARN {seg['start']:.1f}s: słaby match ({best_ratio}) — Whisper: '{whisper_raw}'")
          result_lyrics.append({
              'start': seg['start'],
              'end': seg['end'],
              'text': whisper_raw,
              'match_ratio': best_ratio,
              'words': []
          })
          # Przesuń cursor o trochę żeby nie utknąć
          cursor += max(50, len(whisper_clean))

  return result_lyrics

## Podział długich segmentów na krótsze napisy

Whisper łączy kilka linii w jeden segment (np. 15s z 2 zdaniami).
Podziel na mniejsze napisy po MAX_WORDS słów:

  MAX_WORDS_PER_SUBTITLE = 7

  def split_segment(seg):
      words = seg['text'].split()
      if len(words) <= MAX_WORDS_PER_SUBTITLE:
          return [seg]

      groups = []
      for i in range(0, len(words), MAX_WORDS_PER_SUBTITLE):
          groups.append(' '.join(words[i:i + MAX_WORDS_PER_SUBTITLE]))

      duration = seg['end'] - seg['start']
      time_per = duration / len(groups)

      result = []
      for i, group in enumerate(groups):
          result.append({
              'start': round(seg['start'] + i * time_per, 2),
              'end': round(seg['start'] + (i + 1) * time_per - 0.1, 2),
              'text': group,
              'words': [],
              'match_ratio': seg.get('match_ratio', 0)
          })
      return result

  # Zastosuj po matchowaniu
  final_lyrics = []
  for seg in result_lyrics:
      final_lyrics.extend(split_segment(seg))

## Filtrowanie szumu przed matchingiem

  NON_VOCAL = {'muzyka', 'music', 'instrumental'}

  def is_vocal(seg):
      text = seg['text'].strip().lower()
      text_clean = re.sub(r'[\[\]()♪♫ ]', '', text)
      if text_clean in NON_VOCAL:
          return False
      if len(text_clean) < 3:
          return False
      return True

  vocal_segments = [s for s in whisper_segments if is_vocal(s)]

## Nowy moduł musicvid/pipeline/lyrics_aligner.py

Eksportuj funkcję:
  align_lyrics(whisper_segments, lyrics_path) -> list[dict]

Która implementuje cały algorytm powyżej.

## Integracja w audio_analyzer.py

Gdy lyrics_path dostępny:
  from musicvid.pipeline.lyrics_aligner import align_lyrics

  vocal_segs = [s for s in lyrics if is_vocal_segment(s)]
  aligned = align_lyrics(vocal_segs, lyrics_path)

  # Podziel długie segmenty
  final = []
  for seg in aligned:
      final.extend(split_segment(seg))

  lyrics = final
  print(f"[Lyrics] Aligned: {len(lyrics)} napisów z {len(vocal_segs)} segmentów")

## requirements.txt
rapidfuzz>=3.0.0

## Testy

test_cursor_advances:
  Po dopasowaniu segmentu 1 cursor > 0
  Segment 2 szuka od cursor, nie od 0

test_fuzzy_typos:
  whisper "tolko w bogu mojest" → match "Tylko w Bogu moje jest zbawienie"
  ratio >= 45

test_brackets_ignored:
  Plik ma "[Refren:]" → nie pojawia się w wynikach

test_sequential:
  Wyniki posortowane chronologicznie
  lyrics[i]['start'] < lyrics[i+1]['start'] zawsze

test_split_long:
  Segment z 14 słowami → 2 napisy po 7 słów
  Timing rozłożony równomiernie

test_noise_filtered:
  Segment "Muzyka" @ 0.0s → odfiltrowany, nie w wynikach

test_first_subtitle_timing:
  lyrics[0]['start'] >= 28.0  (nie 0.0s)

## Acceptance Criteria
- lyrics[0]['start'] >= 28.0s
- Tekst pochodzi z pliku (poprawna polszczyzna, bez literówek)
- Cursor przesuwa się tylko do przodu
- Słabe dopasowania używają tekstu Whispera jako fallback
- [Refren:] i podobne są ignorowane
- Długie segmenty podzielone na krótsze napisy
- python3 -m pytest tests/test_lyrics_aligner.py -v przechodzi
