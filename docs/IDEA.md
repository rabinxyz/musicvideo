# Idea

# Spec: Batch processing — folder z piosenkami

## Cel
Przetwarzanie całego folderu z piosenkami w jednym uruchomieniu.
Wrzucasz folder przed snem, rano masz gotowe teledyski do wszystkich pieśni.

## Nowa komenda CLI
python3 -m musicvid.musicvid --batch /sciezka/do/folderu

Przykłady:
python3 -m musicvid.musicvid --batch ~/Pulpit/piesni/
python3 -m musicvid.musicvid --batch ~/Pulpit/piesni/ --preset all
python3 -m musicvid.musicvid --batch ~/Pulpit/piesni/ --mode ai --provider flux-pro
python3 -m musicvid.musicvid --batch ~/Pulpit/piesni/ --preset all --effects minimal

Wszystkie pozostałe flagi działają tak samo jak dla pojedynczego pliku
i są stosowane do każdej piosenki w folderze.

## Struktura folderu wejściowego

Obsłuż dwa warianty automatycznie:

Wariant A — luźne pliki (auto-parowanie MP3 + TXT o tej samej nazwie):
  piesni/
    Tylko w Bogu.mp3
    Tylko w Bogu.txt
    Pan jest moca moja.mp3
    Pan jest moca moja.txt
    Badz uwielbiony.mp3     (brak .txt — Whisper jako fallback)

Wariant B — podfoldery per piosenka:
  piesni/
    Tylko w Bogu/
      Tylko w Bogu (Cover).mp3
      tekst.txt
      logo.svg              (opcjonalne logo specyficzne dla piosenki)
    Pan jest moca moja/
      Pan jest moca moja.mp3
      tekst.txt

Wykryj wariant automatycznie po strukturze folderu.
Parowanie lyrics: szukaj .txt o tej samej nazwie co .mp3 (wariant A)
lub dowolnego .txt w tym samym podfolderze (wariant B).

## Obsługiwane formaty audio
MP3, WAV, FLAC, M4A, OGG

## Struktura folderu wyjściowego

piesni/
  output/
    Tylko w Bogu/
      pelny/
        Tylko_w_Bogu_youtube.mp4
        Tylko_w_Bogu_youtube_metadata.txt
      social/
        Tylko_w_Bogu_rolka_A_15s.mp4
        Tylko_w_Bogu_rolka_B_15s.mp4
        Tylko_w_Bogu_rolka_C_15s.mp4
    Pan jest moca moja/
      pelny/
        ...
      social/
        ...
    batch_report.html

## Kolejność przetwarzania

Flaga --batch-order [alpha|random|size-asc|size-desc] (domyślnie: alpha)
alpha      — alfabetycznie
random     — losowo
size-asc   — od najkrótszej piosenki
size-desc  — od najdłuższej

## Obsługa błędów

Gdy piosenka X się nie powiedzie:
- Zaloguj błąd do batch_report.html
- Przejdź do następnej piosenki
- Po zakończeniu: "Gotowe 8/10 — sprawdź batch_report.html"

Wyjątek: błąd 402 (brak kredytów API) — zatrzymaj cały batch natychmiast.

## Równoległość

Flaga --batch-parallel INT (domyślnie: 1)
1 — sekwencyjnie (bezpieczne, domyślne)
2 — dwie piosenki naraz (szybciej, większe ryzyko rate limit)
Zalecane max 2-3.

## Pomijanie już przetworzonych

Jeśli piosenka ma już gotowy MP4 w output/ — pomiń ją.
Wyświetl: "Pomijam: Tylko w Bogu (juz przetworzona, uzyj --batch-force aby powtorzyc)"

Flaga --batch-force: pomiń sprawdzanie, przetwórz wszystkie od nowa.

## Logowanie postępu

Wyświetlaj prefix z numerem i nazwą piosenki:
  BATCH [1/10] Tylko w Bogu
  [1/4] Analiza audio...
  [2/4] Rezyseria (Claude)...
  [3/4] Generowanie obrazow...
  [4/4] Montaz...
  Gotowe — output/Tylko w Bogu/ (8m 32s)

  BATCH [2/10] Pan jest moca moja
  ...

Szacowany czas do końca po każdej piosence:
"Szacowany czas do konca: ~42 minuty (5 piosenek x ~8.5 min)"

## Szacowanie kosztu przed startem

Przed uruchomieniem wyświetl szacunek i pytaj o potwierdzenie:

  Znaleziono 10 piosenek.
  Szacowany koszt (--mode ai --preset all):
    BFL flux-pro: ~10 x 8 scen x $0.05 = ~$4.00
    Claude API:   ~10 x 4 wywolania x $0.01 = ~$0.40
    Lacznie: ~$4.40
  Szacowany czas: ~10 x 9 minut = ~90 minut
  Kontynuowac? [T/n]:

Flaga --batch-yes: pomiń potwierdzenie (dla automatyzacji nocnej).

## Plik konfiguracyjny batcha (opcjonalnie)

Obsłuż plik batch.yaml w folderze wejściowym:

  default:
    mode: ai
    provider: flux-pro
    preset: all
    effects: minimal
    logo: ~/logo.svg

  overrides:
    "Pan jest moca moja":
      style: powerful
    "Tylko w Bogu":
      provider: flux-dev
      clip_duration: 30

Gdy batch.yaml istnieje: użyj ustawień z pliku zamiast flag CLI.
Overrides per piosenka nadpisują ustawienia domyślne.

## Raport HTML — batch_report.html

Generuj po zakończeniu całego batcha.
Zawiera:
- Tabelę: nazwa, status, czas generowania, szacowany koszt API
- Miniatury pierwszej klatki każdego teledysku
- Linki do wygenerowanych plików MP4
- Podsumowanie: łączny czas, łączny koszt, liczba plików
- Błędy z opisem dla nieudanych piosenek

## Nowy moduł musicvid/pipeline/batch_processor.py

Funkcje:
- discover_songs(folder_path) -> list[SongJob]
  Wykrywa piosenki i paruje z lyrics/logo.
  SongJob zawiera: audio_path, lyrics_path, logo_path, output_dir, config

- estimate_cost(songs, config) -> dict
  Szacuje koszt i czas dla całego batcha.
  Zwraca dict z polami: bfl, claude, runway, total, minutes

- run_batch(songs, config, parallel=1) -> BatchReport
  Przetwarza piosenki sekwencyjnie lub równolegle.
  Błąd jednej piosenki nie zatrzymuje pozostałych.
  Błąd 402 zatrzymuje cały batch natychmiast.

- generate_html_report(report, output_path)
  Generuje batch_report.html z miniaturami i podsumowaniem.

- load_batch_config(folder_path) -> dict
  Wczytuje batch.yaml jeśli istnieje, zwraca pusty dict jeśli nie ma.

## Integracja w musicvid.py

Dodaj obsługę flag:
  --batch PATH: wywołaj discover_songs() + run_batch() zamiast standardowego pipeline
  --batch-order: przekaż do discover_songs()
  --batch-parallel INT: przekaż do run_batch()
  --batch-force: pomiń sprawdzanie gotowych plików
  --batch-yes: pomiń potwierdzenie kosztu

## Testy
- discover_songs wariant A: paruje MP3 z TXT o tej samej nazwie
- discover_songs wariant B: wykrywa podfoldery i paruje pliki
- discover_songs brak TXT: lyrics_path=None (Whisper jako fallback)
- estimate_cost: zwraca dict z polami bfl, claude, total, minutes
- run_batch: błąd jednej piosenki nie zatrzymuje kolejnych
- run_batch: błąd 402 zatrzymuje batch natychmiast
- Pomijanie: piosenka z gotowym MP4 pomijana bez --batch-force
- --batch-force: wszystkie piosenki przetwarzane nawet z gotowym MP4
- generate_html_report: plik HTML zawiera tabelę i linki
- load_batch_config: wczytuje overrides per piosenka

## Acceptance Criteria
- --batch folder/ przetwarza wszystkie piosenki w folderze
- Parowanie MP3+TXT działa dla obu wariantów struktury folderu
- Brak TXT: Whisper jako fallback bez błędu
- Błąd jednej piosenki nie zatrzymuje pozostałych
- Błąd 402 zatrzymuje cały batch natychmiast z komunikatem
- Piosenki z gotowym MP4 pomijane (chyba że --batch-force)
- Szacunek kosztu wyświetlany przed startem z potwierdzeniem
- --batch-yes pomija potwierdzenie
- batch_report.html generowany po zakończeniu
- batch.yaml obsługiwany gdy istnieje w folderze
- python3 -m pytest tests/ -v przechodzi
