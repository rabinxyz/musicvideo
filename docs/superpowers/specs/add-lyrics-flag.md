# Spec: Flaga --lyrics z automatycznym wykrywaniem pliku tekstowego

## Kontekst
Logika lyrics już istnieje w projekcie:
- audio_analyzer.py buduje listę lyrics z polami start/end/text
- assembler.py przyjmuje lyrics i tworzy napisy (_create_subtitle_clips)

Brakuje flagi --lyrics w CLI oraz automatycznego wykrywania pliku txt.

## Nowa opcja CLI
--lyrics PATH  Ścieżka do pliku .txt z tekstem piosenki (opcjonalna)

## Zachowanie gdy --lyrics NIE jest podane (auto-wykrywanie)
Przed uruchomieniem Whisper sprawdź czy w katalogu pliku audio
istnieje dokładnie jeden plik .txt:
- Jeśli tak: użyj go automatycznie jako lyrics, pomiń Whisper
- Wyświetl: "[1/4] Tekst: znaleziono automatycznie → nazwa_pliku.txt (N linijek)"
- Jeśli jest więcej niż jeden .txt: zignoruj auto-wykrywanie, użyj Whisper,
  wyświetl ostrzeżenie: "Znaleziono wiele plików .txt — użyj --lyrics aby wybrać"
- Jeśli nie ma żadnego .txt: użyj Whisper jak dotychczas

## Zachowanie gdy --lyrics JEST podane
- Użyj wskazanego pliku, pomiń Whisper
- Wyświetl: "[1/4] Tekst: wczytano z pliku (N linijek)"
- Plik nie istnieje: czytelny błąd ze ścieżką

## Format pliku lyrics — obsłuż oba warianty

Wariant A — linie bez timestampów:
Podziel audio_duration równomiernie przez liczbę linijek.
start = i * segment, end = (i+1) * segment - 0.3

Wariant B — linie z timestampem MM:SS lub HH:MM:SS na początku linii:
start = timestamp, end = następny timestamp - 0.3
Ostatnia linijka: end = audio_duration - 1.0

Wykryj wariant automatycznie po pierwszej niepustej linii pliku.
Pusty plik: ValueError z czytelnym komunikatem.

## Nowy moduł musicvid/pipeline/lyrics_parser.py
Funkcja: parse(lyrics_path, audio_duration) -> list[dict]
Zwraca format zgodny z istniejącym: [{"start": float, "end": float, "text": str}]
Obsługuje wariant A i B jak opisano wyżej.

## Cache
Hash pliku lyrics (MD5) wchodzi do klucza cache.
Zmiana pliku lyrics invaliduje cache.

## Testy
- Auto-wykrywanie: jeden .txt w katalogu → użyty automatycznie
- Auto-wykrywanie: wiele .txt → Whisper + ostrzeżenie
- Auto-wykrywanie: brak .txt → Whisper
- Wariant A: 4 linijki audio 60s → każda 15s
- Wariant B: parsowanie MM:SS i HH:MM:SS
- Ostatnia linijka: end = audio_duration - 1.0
- Pusty plik: ValueError
- Brakujący plik przy --lyrics: FileNotFoundError

## Acceptance Criteria
- python3 -m musicvid.musicvid piosenka.mp3 automatycznie używa tekst.txt
  jeśli jest w tym samym katalogu co piosenka
- --lyrics ścieżka/do/tekst.txt działa jawnie
- Pominięcie Whisper gdy tekst dostępny (szybszy start)
- Napisy w wideo odpowiadają treści pliku
- python3 -m pytest tests/ -v przechodzi
