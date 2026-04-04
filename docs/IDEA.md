# Idea

# Spec: Transition variety — różne typy przejść między scenami

## Cel
Dodać różnorodne typy przejść między scenami dopasowane do momentu
w piosence. Obecny kod ma tylko fade i cut — brakuje przejść które
są standardem w profesjonalnych teledyskach worship.

## Nowa flaga CLI
--transitions [auto|fade|cut|dip-white|cross-dissolve|push|none]
(domyślnie: auto)

auto         — Claude wybiera typ przejścia per scena na podstawie kontekstu
fade         — wszystkie przejścia jako fade (obecne zachowanie)
cut          — wszystkie jako twarde cięcie na beat
dip-white    — wszystkie jako wybielenie
cross-dissolve — wszystkie jako cross dissolve
push         — wszystkie jako push
none         — brak przejść (sceny sklejone bez efektu)

## Typy przejść do zaimplementowania

### cut (twarde cięcie)
Brak efektu przejścia — jedna scena kończy się, natychmiast zaczyna następna.
Zawsze synchronizowane z downbeat (patrz: hard-cut-on-beat spec).
Najlepsze dla: energetycznych momentów, refrenu, zmiany sekcji przy wysokiej energii.
Implementacja: brak dodatkowego kodu — domyślne zachowanie concatenate_videoclips.

### fade (obecne)
Scena zanika do czarnego, następna pojawia się z czarnego.
Czas: 0.5s in + 0.5s out.
Najlepsze dla: spokojnych momentów, intro, outro, verse przy niskiej energii.
Implementacja: with_effects([vfx.CrossFadeIn(0.5)]) — już działa.

### dip-white (wybielenie)
Scena zanika do białego, następna pojawia się z białego.
Czas: 0.4s in + 0.4s out.
Najlepsze dla: kulminacyjnych momentów, refrenu, "świetlistych" tekstów.
Bardzo charakterystyczny look dla worship music — używany przez Hillsong,
Elevation Worship, Bethel Music.
Implementacja: ColorClip biały (#FFFFFF) o długości 0.8s wstawiony między scenami
jako osobny klip. Fade in ostatniej klatki sceny A do bieli 0.4s,
fade out z bieli do pierwszej klatki sceny B 0.4s.
Alternatywnie przez FFmpeg filter: fade=t=out:st={t}:d=0.4:color=white

### cross-dissolve
Scena A i scena B nakładają się płynnie przez określony czas.
Czas nakładania: 0.6s
Najlepsze dla: płynnych przejść między podobnymi wizualnie scenami,
bridge, wolnych momentów.
Implementacja: CompositeVideoClip z nakładającymi się klipami i
animowaną opacity. Lub przez FFmpeg xfade filter:
xfade=transition=dissolve:duration=0.6:offset={offset}

### push (pchanie)
Scena B wjeżdża z prawej strony wypychając scenę A w lewo.
Czas: 0.5s
Najlepsze dla: zmiany sekcji, dynamicznych momentów, bridge→chorus.
Implementacja: przez FFmpeg xfade filter:
xfade=transition=slideleft:duration=0.5:offset={offset}
Warianty kierunku: slideleft, slideright, slideup, slidedown

## Logika auto-wyboru przejść przez Claude

W planie scen Claude dostaje dodatkowe pole transition per scena.
Prompt dla Claude:
"Dla każdej sceny wybierz typ przejścia do NASTĘPNEJ sceny.
Kieruj się zasadami:
- cut: zmiana sekcji przy wysokiej energii (verse→chorus z mocnym beatem)
- dip-white: kulminacyjny moment, tekst o świetle/chwale/uwielbieniu
- cross-dissolve: płynne przejście między podobnymi scenami, wolne tempo
- push: dramatyczna zmiana sekcji, bridge→chorus
- fade: spokojne momenty, intro, outro, niska energia
Uwzględnij BPM i energy_mood przy wyborze."

Struktura w scene_plan.json — dodaj pole do każdej sceny:
  "transition_to_next": "cut|fade|dip-white|cross-dissolve|push"
  "transition_duration": float  (w sekundach, domyślnie 0.5)

## Implementacja przez FFmpeg xfade (rekomendowane)

FFmpeg xfade filter obsługuje przejścia natywnie i jest znacznie
szybszy niż Python frame-by-frame przez MoviePy.

Przepływ:
1. Wygeneruj każdą scenę jako osobny plik MP4 bez przejść
2. Łącz sceny przez FFmpeg z xfade filterem
3. Każde przejście to osobna operacja xfade z odpowiednim offset

Mapowanie typów na FFmpeg xfade:
  fade         → fade (lub crossfade)
  dip-white    → fadewhite
  cross-dissolve → dissolve
  push         → slideleft
  cut          → brak xfade — bezpośrednie concat

Przykład komendy FFmpeg dla 3 scen:
ffmpeg -i scene_0.mp4 -i scene_1.mp4 -i scene_2.mp4 \
  -filter_complex \
  "[0][1]xfade=transition=fadewhite:duration=0.5:offset=11.5[v01]; \
   [v01][2]xfade=transition=dissolve:duration=0.6:offset=23.0[vout]" \
  -map "[vout]" output.mp4

Offset = czas końca poprzedniej sceny minus czas trwania przejścia.

## Nowy moduł musicvid/pipeline/transitions.py

Funkcje:
- get_transition_for_scene(scene, next_scene, analysis) -> dict
  Zwraca {type, duration} dla przejścia między sceną a następną.
  Używane gdy --transitions auto bez Claude (fallback deterministyczny):
    chorus po verse → dip-white
    zmiana sekcji przy mood_energy > 0.6 → cut
    bridge → push
    pozostałe → cross-dissolve

- build_ffmpeg_xfade_filter(scenes, transitions) -> str
  Buduje string filter_complex dla FFmpeg z wszystkimi przejściami.
  Zwraca gotowy string do przekazania do FFmpeg.

- apply_transitions(scene_files, transitions, output_path) -> str
  Wywołuje FFmpeg z xfade filterem.
  scene_files: lista ścieżek do plików MP4 per scena
  transitions: lista dictów {type, duration} per przejście
  Zwraca ścieżkę do złączonego pliku.

- get_transition_offset(scene_durations, transition_idx, transition_duration) -> float
  Oblicza offset dla xfade na podstawie długości poprzednich scen.

## Integracja w assembler.py

Obecny przepływ:
  concatenate_videoclips(clips) → jeden długi klip

Nowy przepływ gdy transitions != none:
  1. Wygeneruj każdą scenę jako osobny plik MP4 w tmp/
  2. Pobierz listę transitions z scene_plan (lub oblicz deterministycznie)
  3. Wywołaj apply_transitions() z FFmpeg xfade
  4. Wynik to złączony MP4 z przejściami
  5. Usuń pliki pośrednie per scena

Gdy transitions == none lub wszystkie cut:
  Użyj dotychczasowego concatenate_videoclips (szybciej).

## Długości przejść a synchronizacja z beatem

Długość przejścia powinna być wielokrotnością czasu jednego beatu:
  BPM=84: beat = 0.714s → przejście 0.5s (bliskie 0.71s)
  BPM=120: beat = 0.5s → przejście 0.5s (dokładnie jeden beat)

Oblicz optymalną długość przejścia:
  beat_duration = 60 / bpm
  transition_duration = round(beat_duration / 2, 2)  (pół beatu)
  Clamp do zakresu 0.3s - 0.8s

## Testy
- get_transition_offset: poprawny offset dla 3 scen
- build_ffmpeg_xfade_filter: zawiera xfade dla każdego przejścia
- Przejście cut: brak xfade w filtrze
- apply_transitions: mockuj FFmpeg, sprawdź komendę
- auto wybór: chorus po verse → dip-white
- auto wybór: mood_energy > 0.6 przy zmianie sekcji → cut
- Długość przejścia skalowana do BPM

## Acceptance Criteria
- --transitions dip-white: wszystkie przejścia jako wybielenie
- --transitions auto: różne typy per scena z planu Claude
- --transitions cut: twarde cięcia wszędzie
- --transitions none: sceny sklejone bez efektu
- Implementacja przez FFmpeg xfade (nie MoviePy frame-by-frame)
- Przejścia zsynchronizowane z BPM
- Czas generowania nie wzrasta o więcej niż 15%
- python3 -m pytest tests/ -v przechodzi
