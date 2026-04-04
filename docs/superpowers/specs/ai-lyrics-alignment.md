# Spec: AI dopasowanie tekstu z pliku do timingu Whisper

## Koncepcja
Whisper daje dobry timing ale błędny tekst (szczególnie po polsku).
Plik tekst.txt ma poprawny tekst ale bez timestampów.
Claude API dopasowuje linie z pliku do segmentów Whisper na podstawie
semantycznego podobieństwa — rozumie kontekst, kolejność i brzmienie.

## Przepływ gdy dostępny plik lyrics

1. Whisper transkrybuje audio → lista segmentów z polami start/end/text
   Pomiń puste segmenty (text.strip() == "")

2. Wczytaj plik lyrics → lista linii
   Pomiń puste linie i linie zawierające tylko whitespace

3. Wyślij do Claude API żądanie dopasowania:
   - Segmenty Whisper z timestampami i niedokładnym tekstem
   - Poprawne linie z pliku
   - Claude zwraca JSON: lista {start, end, text} gdzie text pochodzi
     z pliku a start/end z odpowiadającego segmentu Whisper

4. Użyj wyniku Claude jako finalnej listy lyrics dla assembler

## Prompt dla Claude w kroku 3

System:
Jesteś asystentem do synchronizacji tekstu piosenek.
Zwracaj WYŁĄCZNIE czysty JSON, bez markdown, bez komentarzy.

User:
Mam transkrypcję Whisper (niedokładną) i poprawny tekst piosenki.
Dopasuj każdą linię poprawnego tekstu do segmentu Whisper który
najbardziej jej odpowiada — na podstawie podobieństwa brzmienia,
kolejności w piosence i kontekstu.

Zasady:
- Zachowaj kolejność — linie z pliku pojawiają się w tej samej kolejności co w piosence
- Każda linia z pliku musi być przypisana do dokładnie jednego segmentu Whisper
- Jeśli jest więcej segmentów Whisper niż linii w pliku — scal sąsiednie segmenty
  (użyj start pierwszego i end ostatniego segmentu w grupie)
- Jeśli jest więcej linii w pliku niż segmentów Whisper — podziel dostępny
  czas równomiernie dla nadmiarowych linii po ostatnim segmencie
- Puste linie w pliku są już usunięte — ignoruj je

Segmenty Whisper (z niedokładnym tekstem):
{whisper_segments_json}

Poprawne linie z pliku:
{file_lines_json}

Zwróć JSON:
[{"start": float, "end": float, "text": "poprawna linia z pliku"}]

## Implementacja

### Nowa funkcja w musicvid/pipeline/lyrics_parser.py
align_with_claude(whisper_segments, file_lines) -> list[dict]
- Buduje prompt jak opisano wyżej
- Wywołuje Claude API (claude-sonnet-4) z max_tokens=2000
- Parsuje JSON z odpowiedzi
- Waliduje że każdy element ma start/end/text
- Retry (tenacity) max 2 próby na błąd parsowania JSON

### Integracja w audio_analyzer.py lub musicvid.py
Gdy plik lyrics dostępny:
  whisper_segments = whisper.transcribe(audio)["segments"]  # zawsze uruchamiaj
  file_lines = wczytaj_i_filtruj_puste(lyrics_path)
  lyrics = align_with_claude(whisper_segments, file_lines)
Gdy plik lyrics niedostępny:
  lyrics = whisper_segments  # zachowanie bez zmian

### Logowanie
Wyświetl: "[1/4] Tekst: Whisper timing + AI dopasowanie tekstu z pliku (N linii)"

## Koszt i wydajność
Jedno wywołanie Claude API per piosenka — tanie i szybkie.
Wynik cachuj w output/tmp/{hash}/lyrics_aligned.json razem z hashem
pliku lyrics — zmiana pliku lyrics invaliduje cache.

## Testy
- align_with_claude: mockuj Claude API, sprawdź że zwraca poprawny format
- Gdy N_segmentów == N_linii: każda linia przypisana do segmentu
- Gdy N_segmentów > N_linii: segmenty scalone poprawnie
- Gdy N_segmentów < N_linii: nadmiarowe linie po końcu
- Błąd parsowania JSON: retry, po 2 próbach rzuć ValueError
- Puste linie w pliku: ignorowane przed wysłaniem do Claude

## Acceptance Criteria
- Napisy w wideo mają tekst z pliku tekst.txt
- Timing napisów pochodzi z Whisper (zsynchronizowany z muzyką)
- Puste linie w pliku są pomijane
- Wynik cachowany — drugi run nie wywołuje Claude ponownie
- python3 -m pytest tests/ -v przechodzi
