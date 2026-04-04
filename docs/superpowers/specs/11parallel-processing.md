# Spec: Równoległe generowanie wielu piosenek

## Cel
Generowanie 2-3 piosenek jednocześnie na lokalnym Macu.
Stage 3 (generowanie obrazów BFL) jest naturalnie async i idealnie
nadaje się do zrównoleglenia. Stage 4 (FFmpeg montaż) jest CPU-intensive
i powinien być sekwencyjny.

## Nowa flaga CLI
--parallel INT  (domyślnie: 1, max: 4)
Liczba piosenek przetwarzanych równolegle.

Użycie:
python3 -m musicvid.musicvid --batch ~/piesni/ --parallel 2
python3 -m musicvid.musicvid --batch ~/piesni/ --parallel 3

## Architektura równoległości

Nie zrównoleglaj wszystkiego naraz — różne stage mają różne bottlenecki.

### Stage 1 (Whisper + librosa) — sekwencyjny
Whisper jest CPU-intensive i zajmuje dużo RAM.
Uruchamiaj sekwencyjnie — jedna piosenka na raz.
Wszyskie analizy najpierw, potem dalej.

### Stage 2 (Claude reżyseria) — równoległy, async
Claude API jest async i szybki.
Wszystkie piosenki mogą pytać Claude jednocześnie.
Użyj asyncio.gather() dla wszystkich wywołań Claude.

### Stage 3 (BFL generowanie obrazów) — równoległy, async
BFL obsługuje max 24 równoległe zadania.
Wszystkie obrazy dla wszystkich piosenek wysyłaj jednocześnie.
Jeden globalny semaphore: max 20 równoległych requestów do BFL
(zostawia bufor na rate limity).
Użyj asyncio z semaphore dla kontroli przepływu.

### Stage 4 (FFmpeg montaż) — sekwencyjny
FFmpeg jest CPU-intensive — jeden montaż na raz.
Kolejkuj montaże i wykonuj jeden po drugim.
Mac M2 ma dobre single-core performance — nie ma sensu parallelizować.

## Implementacja

### Nowy moduł musicvid/pipeline/parallel_runner.py

Klasa ParallelRunner:

  __init__(self, max_parallel=2, max_bfl_requests=20)

  run_parallel(self, song_jobs: list[SongJob]) -> list[Result]
    Główna metoda — orkiestruje cały pipeline dla wielu piosenek.

    Algorytm:
    1. SEQUENTIAL: dla każdej piosenki wykonaj Stage 1 (Whisper + librosa)
       Wyświetl: "[Song 1/3] Analiza audio: Tylko w Bogu..."
    
    2. PARALLEL async: dla wszystkich piosenek równolegle Stage 2 (Claude)
       asyncio.gather(*[self._run_director(song) for song in songs])
       Wyświetl: "Reżyseria Claude: 3 piosenki równolegle..."
    
    3. PARALLEL async z semaphore: Stage 3 (BFL obrazy) dla wszystkich
       Globalny semaphore(max_bfl_requests) — dzielony między piosenki
       asyncio.gather(*[self._generate_images(song) for song in songs])
       Wyświetl: "Generowanie obrazów: [Song A: 3/8] [Song B: 5/8] [Song C: 1/8]"
    
    4. SEQUENTIAL: dla każdej piosenki Stage 4 (FFmpeg montaż)
       Kolejkuj montaże, wykonuj jeden po drugim
       Wyświetl: "[1/3] Montaż: Tylko w Bogu..."

  _run_director(self, song) -> dict
    Async wywołanie Claude API dla jednej piosenki.

  _generate_images(self, song) -> list[str]
    Async generowanie obrazów z globalnym semaphore.
    async with self.bfl_semaphore:
      task_id, polling_url = await _submit_task_async(...)
    Polluj async przez asyncio.sleep(1.5) zamiast time.sleep().

  _run_ffmpeg(self, song) -> str
    Synchroniczny montaż FFmpeg. Wywoływany sekwencyjnie.

### Async wersje wywołań API

Stwórz async wersje istniejących funkcji:
- _submit_task_async() — aiohttp zamiast requests
- _poll_result_async() — aiohttp z asyncio.sleep()
- _call_claude_async() — anthropic AsyncAnthropic client

Istniejące synchroniczne wersje zostają dla trybu --parallel 1.

### Integracja w musicvid.py i batch_processor.py

Gdy --parallel > 1 i --batch podane:
  runner = ParallelRunner(max_parallel=parallel)
  results = asyncio.run(runner.run_parallel(song_jobs))

Gdy --parallel 1 (domyślnie):
  Zachowanie bez zmian — sekwencyjny pipeline jak dotychczas.

## Wyświetlanie postępu przy parallel

Używaj rich library lub prostego inline update:
  [Tylko w Bogu    ] [1/4] Analiza audio...    ████░░░░ 25%
  [Pan jest mocą   ] [3/4] Generowanie 5/8...  ██████░░ 62%
  [Bądź uwielbiony ] [2/4] Reżyseria...        ██░░░░░░ 20%

Jeśli rich niedostępny: zwykłe logi z prefixem nazwy piosenki.

## Obsługa błędów przy parallel

Gdy jedna piosenka się nie powiedzie:
- Nie zatrzymuj pozostałych
- Zaloguj błąd per piosenka
- Kontynuuj z kolejnymi stage dla pozostałych piosenek
- Na końcu pokaż podsumowanie: "2/3 gotowe, 1 błąd"

Gdy błąd 429 (rate limit BFL):
- Exponential backoff dla tej konkretnej sceny
- Pozostałe sceny innych piosenek kontynuują bez przerwy

Gdy błąd 402 (brak kredytów):
- Zatrzymaj wszystkie równoległe zadania natychmiast
- Wyczyść zasoby (anuluj pending requests)

## Ograniczenia i rekomendacje

Wyświetl ostrzeżenie gdy --parallel > 2 na lokalnym Macu:
"Uwaga: --parallel 3+ może być wolniejszy niż 2 ze względu na
RAM i CPU. Rekomendowane max 2 dla Mac M2."

Szacunek przyspieszenia:
- 3 piosenki sequential: ~27 minut
- 3 piosenki --parallel 2: ~16 minut (Stage 3 dominuje)
- 3 piosenki --parallel 3: ~14 minut (mniejszy zysk ze Stage 4)

## requirements.txt — dodaj
aiohttp>=3.9.0      (async HTTP dla BFL i innych API)
rich>=13.0.0        (opcjonalne, ładniejszy progress display)

## Testy
- ParallelRunner z 2 piosenkami: Stage 1 sekwencyjny, Stage 3 równoległy
- Semaphore: max max_bfl_requests równoległych requestów BFL
- Błąd jednej piosenki w Stage 3: pozostałe kontynuują
- Błąd 402: wszystkie zadania zatrzymane
- --parallel 1: używa synchronicznego pipeline (bez asyncio)
- asyncio.gather dla Stage 2: wszystkie wywołania Claude równoległe

## Acceptance Criteria
- --batch folder/ --parallel 2: dwie piosenki przetwarzane równolegle
- Stage 1 i Stage 4 zawsze sekwencyjne
- Stage 2 i Stage 3 zawsze równoległe (gdy --parallel > 1)
- Max 20 równoległych requestów do BFL (globalny semaphore)
- Błąd jednej piosenki nie zatrzymuje innych
- --parallel 1 (domyślnie): zachowanie identyczne jak przed zmianą
- python3 -m pytest tests/ -v przechodzi
