# Spec: Hard cut na beat — cięcia synchronizowane z mocnymi uderzeniami

## Cel
Cięcia między scenami muszą trafić dokładnie w mocne uderzenie (downbeat)
a nie między beatami. To największa pojedyncza różnica między amatorskim
a profesjonalnym teledyskiem.

## Problem z obecną implementacją
Obecny assembler dzieli piosenkę na równe odcinki per sekcja (intro/verse/chorus).
Cięcia trafiają w losowe miejsca względem rytmu.
Efekt: wideo "nie gra" z muzyką nawet jeśli obrazy są piękne.

## Koncepcja

### Downbeat vs beat
Beat = każde uderzenie rytmiczne (4 na takt w 4/4)
Downbeat = pierwsze uderzenie taktu (mocne, "jeden")

Cięcia TYLKO na downbeat — nie na każdy beat.
Zbyt częste cięcia (każdy beat) wyglądają jak szybki montaż akcji —
nie pasują do muzyki uwielbienia. Właściwe tempo to co 2-4 takty.

### Minimalna długość sceny
Scena musi trwać minimum 4 beaty (jeden takt).
Dla BPM=84: jeden takt = 4 × (60/84) = 2.86s → min scena ~3s
Dla BPM=120: jeden takt = 4 × (60/120) = 2.0s → min scena ~2s

## Algorytm wyboru punktów cięcia

### Krok 1 — wykryj downbeaty z librosa
librosa.beat.beat_track() zwraca beaty.
Downbeaty to co N-ty beat gdzie N = liczba uderzeń w takcie.
Dla muzyki 4/4 (typowa dla worship): downbeat co 4 beaty.

Wykryj metrum (time signature):
librosa.beat.beat_track() + librosa.feature.tempogram()
Dla większości pieśni worship: 4/4 — możesz założyć jako domyślne.
Dodaj parametr --time-signature [4/4|3/4|6/8] (domyślnie: auto)

### Krok 2 — wyznacz kandydatów na cięcia
Lista downbeatów = beat_times[::4] dla 4/4
Odfiltruj downbeaty za blisko początku i końca sekcji (margines 1s)

### Krok 3 — wybierz najlepsze punkty cięcia per scena
Claude-reżyser dostaje listę dostępnych downbeatów i decyduje
przy których ciąć na podstawie:
- zmiany sekcji (verse→chorus zawsze na downbeat)
- intensywności tekstu (nowa myśl = nowa scena)
- długości sceny (min 2 takty, optymalnie 4-8 taktów)

Alternatywnie (szybciej, bez Claude): algorytm deterministyczny:
- Zawsze tnij na downbeat przy zmianie sekcji z librosa
- Między sekcjami: tnij co 4 takty (co 4. downbeat)
- Dostosuj żeby ostatnia scena sekcji kończyła się na downbeat przed
  początkiem następnej sekcji

### Krok 4 — snapowanie istniejących cięć do nearest downbeat
Gdy masz już plan scen (start/end per scena):
Dla każdego end/start: znajdź najbliższy downbeat w oknie ±0.5s
i "snapnij" cięcie do niego.
Jeśli żaden downbeat nie jest w oknie: zostaw oryginalne cięcie
(bezpieczny fallback).

## Zmiany w kodzie

### musicvid/pipeline/audio_analyzer.py
Dodaj do wyjścia analysis:
  "downbeats": [float, ...]  — lista czasów downbeatów w sekundach
  "time_signature": int      — liczba beatów w takcie (4 dla 4/4)
  "beats_per_bar": int       — alias dla time_signature

Implementacja:
  tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
  beat_times = librosa.frames_to_time(beat_frames, sr=sr)
  downbeats = beat_times[::4]  # co 4. beat dla 4/4

### musicvid/pipeline/assembler.py
Nowa funkcja: snap_to_downbeat(time, downbeats, window=0.5) -> float
  Znajdź downbeat najbliższy do time w oknie ±window sekund.
  Jeśli brak: zwróć oryginalny time.

Zastosuj snap_to_downbeat() dla każdego scene["start"] i scene["end"]
w planie scen przed montażem.
Wyświetl różnicę: "Scena 3: start przesunięty 0.12s → downbeat"

### musicvid/pipeline/director.py
Przekaż downbeats do Claude-reżysera jako dodatkowy kontekst.
Claude może uwzględnić je przy planowaniu długości scen.

## Nowa flaga CLI
--beat-sync [auto|strict|off]  (domyślnie: auto)

auto   — snapowanie do nearest downbeat w oknie ±0.5s (rekomendowane)
strict — snapowanie do nearest downbeat w oknie ±1.0s (agresywniejsze)
off    — wyłączone, cięcia jak dotychczas (fallback)

## Precyzja snapowania

Tolerancja snapowania zależy od BPM:
BPM < 80  → okno ±0.6s (wolna muzyka, downbeaty rzadsze)
BPM 80-120 → okno ±0.5s (standardowe)
BPM > 120  → okno ±0.4s (szybka muzyka, downbeaty gęstsze)

## Flash frame prevention
Po snapowaniu sprawdź że żadne dwie sceny nie mają odstępu < 1.5s.
Jeśli tak: przesuń słabszą scenę do następnego downbeatu.
Scena przy zmianie sekcji (verse→chorus) ma priorytet — nie przesuwa się.

## Wizualizacja (opcjonalna, dla debugowania)
Gdy --debug: zapisz do output/tmp/{hash}/beat_map.txt
Plik zawiera listę wszystkich downbeatów i przy których są cięcia:
  0:04.2  downbeat — CIĘCIE (verse start)
  0:07.1  downbeat
  0:09.9  downbeat — CIĘCIE
  0:12.8  downbeat — CIĘCIE (chorus start)

## Testy
- snap_to_downbeat(10.1, [9.8, 10.5], window=0.5) == 9.8 (bliższy)
- snap_to_downbeat(10.1, [9.0, 11.5], window=0.5) == 10.1 (żaden w oknie)
- snap_to_downbeat dla całego planu scen: każde cięcie na downbeat lub oryginał
- Flash frame: żadne dwie sceny < 1.5s po snapowaniu
- analysis["downbeats"]: lista nie pusta dla typowego pliku MP3
- --beat-sync off: plan scen niezmieniony

## Acceptance Criteria
- Cięcia między scenami trafiają w downbeat (mocne uderzenie taktu)
- analysis["downbeats"] zawiera listę downbeatów z librosa
- snap_to_downbeat przesuwa cięcia do nearest downbeat w oknie
- Żadna scena nie jest krótsza niż 1.5s po snapowaniu
- --beat-sync off wyłącza snapowanie (zachowanie jak dotychczas)
- Wideo "gra" z muzyką — cięcia czuć jako naturalne
- python3 -m pytest tests/ -v przechodzi
