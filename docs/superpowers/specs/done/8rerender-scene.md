# Spec: Re-render pojedynczej sceny

## Cel
Możliwość podmiany jednej sceny bez generowania całego teledysku od nowa.
Oszczędza czas i koszt API gdy jedna scena nie pasuje wizualnie.

## Nowe komendy CLI

### Podgląd planu scen
python3 -m musicvid.musicvid song.mp3 --list-scenes

Wyświetla tabelę wszystkich scen z cache:
  Nr  Sekcja    Start    Koniec   Prompt (pierwsze 60 znaków)
  ─────────────────────────────────────────────────────────────
  0   intro     0:00     0:12     Golden sunrise over mountain peaks...
  1   verse     0:12     0:44     Ancient forest with light filtering...
  2   chorus    0:44     1:16     Silhouette of person with hands raised...
  3   verse     1:16     1:48     Calm lake reflecting blue sky and clouds...

Wymaga istnienia cache (output/tmp/{hash}/).
Jeśli brak cache: "Najpierw wygeneruj teledysk bez --list-scenes"

### Re-render sceny z nowym promptem
python3 -m musicvid.musicvid song.mp3 --rerender-scene 2

Generuje nowy obraz dla sceny nr 2 z tym samym promptem co poprzednio.
Użyteczne gdy obraz nie pasuje jakościowo ale prompt był dobry.

### Re-render z własnym promptem
python3 -m musicvid.musicvid song.mp3 --rerender-scene 2 \
  --scene-prompt "Vast wheat fields at golden hour, wind rippling through grain"

Generuje nowy obraz dla sceny nr 2 z podanym promptem.
Style suffix z Visual Bible jest doklejany automatycznie.

### Re-render z nowym promptem przez Claude
python3 -m musicvid.musicvid song.mp3 --rerender-scene 2 --reprompt

Claude generuje nowy prompt dla tej sceny na podstawie:
- tekstu linijek które pojawiają się w tej scenie
- Visual Bible (styl, paleta)
- informacji że poprzedni prompt był niesatysfakcjonujący
Użyteczne gdy chcesz żeby AI zaproponowała coś innego.

### Rebuild wideo po re-renderze
python3 -m musicvid.musicvid song.mp3 --rebuild

Ponownie montuje wideo z istniejących assetów w cache.
Używa gdy zmieniłeś dowolny plik w cache (obraz, plan scen).
Pomija Stage 1-3 (analiza, reżyseria, generowanie) — tylko montaż.

## Typowy workflow

1. Wygeneruj teledysk normalnie
   python3 -m musicvid.musicvid song.mp3 --mode ai --preset all

2. Obejrzyj wynik — scena 2 nie pasuje

3. Sprawdź listę scen
   python3 -m musicvid.musicvid song.mp3 --list-scenes

4a. Wygeneruj nowy obraz z tym samym promptem (losowość BFL)
    python3 -m musicvid.musicvid song.mp3 --rerender-scene 2

4b. Lub z własnym promptem
    python3 -m musicvid.musicvid song.mp3 --rerender-scene 2 \
      --scene-prompt "Open Bible on wooden table with warm window light"

4c. Lub poproś Claude o nowy pomysł
    python3 -m musicvid.musicvid song.mp3 --rerender-scene 2 --reprompt

5. Zmontuj ponownie
   python3 -m musicvid.musicvid song.mp3 --rebuild

## Jak działa re-render

Wczytaj scene_plan.json z cache.
Znajdź scenę o podanym indeksie.
Wygeneruj nowy obraz przez BFL API (jeden obraz, nie wszystkie).
Zapisz jako scene_NNN.jpg w cache — nadpisz poprzedni.
Jeśli --animate i scena była animowana: uruchom Runway ponownie.
Wyświetl: "Scena 2 wygenerowana → output/tmp/{hash}/scene_002.jpg"
Przypomnij: "Uruchom --rebuild żeby złożyć nowe wideo"

## Zachowanie scene_plan.json przy --scene-prompt

Gdy podano własny prompt:
Zaktualizuj pole visual_prompt dla tej sceny w scene_plan.json.
Zapisz zaktualizowany plan — następne --rebuild użyje nowego promptu.
Wyświetl: "Plan scen zaktualizowany: scena 2 ma nowy prompt"

## Nowy moduł musicvid/pipeline/scene_rerender.py

Funkcje:
- list_scenes(cache_dir) -> list[dict]
  Wczytuje scene_plan.json, zwraca listę scen z indeksem i skrótem promptu.

- print_scenes_table(scenes)
  Wyświetla tabelę w terminalu (tabulate lub ręczne formatowanie).

- rerender_scene(cache_dir, scene_idx, new_prompt=None, provider="flux-pro") -> str
  Generuje nowy obraz dla sceny scene_idx.
  Gdy new_prompt: aktualizuje scene_plan.json.
  Gdy brak new_prompt: używa istniejącego promptu + style_suffix.
  Zwraca ścieżkę do nowego pliku obrazu.

- reprompt_scene(cache_dir, scene_idx, analysis, visual_bible) -> str
  Wywołuje Claude API żeby wygenerować nowy prompt dla sceny.
  Kontekst dla Claude: tekst sceny + visual_bible + info że poprzedni nie pasował.
  Zapisuje nowy prompt w scene_plan.json.
  Zwraca nowy prompt.

- rebuild_video(audio_path, cache_dir, output_dir, platform_config, effects_config)
  Wczytuje wszystkie assety z cache i montuje wideo od nowa.
  Odpowiednik Stage 4 bez Stage 1-3.
  Identyczny wynik co pełny pipeline dla tych samych assetów.

## Integracja w musicvid.py

Dodaj obsługę flag w CLI:
  --list-scenes: wywołaj list_scenes() + print_scenes_table() i exit
  --rerender-scene INT: wywołaj rerender_scene() i exit
  --scene-prompt TEXT: używane razem z --rerender-scene
  --reprompt: używane razem z --rerender-scene
  --rebuild: wywołaj rebuild_video() bez Stage 1-3

Walidacja:
  --rerender-scene bez istniejącego cache: czytelny błąd
  --rerender-scene N gdy N >= liczba scen: błąd z listą dostępnych
  --scene-prompt bez --rerender-scene: błąd "--scene-prompt wymaga --rerender-scene"
  --reprompt bez --rerender-scene: błąd analogiczny
  --rebuild bez cache: błąd "Najpierw wygeneruj teledysk"

## Cache — co jest zachowane między re-renderami

Zachowuje się:
  audio_analysis.json
  scene_plan.json (aktualizowany przez --scene-prompt)
  visual_bible.json
  scene_NNN.jpg (nadpisywany przez --rerender-scene)
  animated_scene_NNN.mp4 (nadpisywany jeśli --animate)

Nie nadpisuje się automatycznie:
  Poprzedni scene_NNN.jpg — rozważ backup do scene_NNN_backup.jpg
  przed nadpisaniem żeby umożliwić powrót do poprzedniej wersji

## Backup poprzedniej sceny

Przed nadpisaniem scene_NNN.jpg stwórz kopię:
  scene_002.jpg → scene_002_v1.jpg (jeśli v1 nie istnieje)
  scene_002.jpg → scene_002_v2.jpg (przy kolejnym re-renderze)
  itd. do maksymalnie 5 wersji

Dodaj komendę --restore-scene N [--version V]:
  python3 -m musicvid.musicvid song.mp3 --restore-scene 2
  Przywraca ostatnią wersję backup (scene_002_v1.jpg → scene_002.jpg)
  python3 -m musicvid.musicvid song.mp3 --restore-scene 2 --version 1
  Przywraca konkretną wersję

## Testy
- list_scenes: zwraca listę z poprawnymi indeksami i sekcjami
- rerender_scene: generuje plik scene_NNN.jpg w cache (mockuj BFL)
- rerender_scene z new_prompt: aktualizuje scene_plan.json
- reprompt_scene: mockuj Claude API, zwraca niepusty string
- rebuild_video: montuje wideo (mockuj MoviePy), nie wywołuje Whisper ani BFL
- Backup: scene_002_v1.jpg istnieje po pierwszym re-renderze
- restore-scene: scene_002.jpg zastąpiony przez scene_002_v1.jpg
- --rerender-scene bez cache: FileNotFoundError z komunikatem
- --rerender-scene poza zakresem: ValueError z listą dostępnych

## Acceptance Criteria
- --list-scenes wyświetla tabelę scen z cache
- --rerender-scene 2 generuje nowy obraz tylko dla sceny 2
- --rerender-scene 2 --scene-prompt "..." używa podanego promptu
- --rerender-scene 2 --reprompt pyta Claude o nowy prompt
- --rebuild montuje wideo bez Stage 1-3
- Backup poprzedniej wersji sceny przed nadpisaniem
- --restore-scene przywraca poprzednią wersję
- python3 -m pytest tests/ -v przechodzi
