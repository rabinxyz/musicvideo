# Spec: Równoległy montaż głównego filmu i rolek social media

## Cel
Gdy --preset all: montaż głównego teledysku i wszystkich 3 rolek
wykonywany równolegle zamiast sekwencyjnie.
Oszczędność czasu ~50-60% na Stage 4.

## Obecny przepływ (sekwencyjny)
Stage 1 → Stage 2 → Stage 3 → Montaż youtube → Montaż rolka A → Montaż rolka B → Montaż rolka C
Czas: ~20 minut (Stage 4 dominuje)

## Nowy przepływ (równoległy montaż)
Stage 1 → Stage 2 → Stage 3 →
  ┌─ Montaż youtube    ─┐
  ├─ Montaż rolka A    ─┤ → wszystkie równolegle → gotowe
  ├─ Montaż rolka B    ─┤
  └─ Montaż rolka C    ─┘
Czas: ~13 minut (Stage 4 = czas najdłuższego montażu)

## Implementacja

### Użyj ThreadPoolExecutor dla montaży FFmpeg
FFmpeg jest procesem zewnętrznym (subprocess) — idealny do
ThreadPoolExecutor bo nie blokuje GIL Pythona.

from concurrent.futures import ThreadPoolExecutor, as_completed

def assemble_all_parallel(jobs: list[AssemblyJob]) -> list[str]:
    results = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(assemble_single, job): job
            for job in jobs
        }
        for future in as_completed(futures):
            job = futures[future]
            try:
                output_path = future.result()
                results.append(output_path)
                print(f"✅ Gotowe: {job.name}")
            except Exception as e:
                print(f"❌ Błąd: {job.name} — {e}")
    return results

AssemblyJob zawiera:
  name: str            (np. "youtube", "rolka_A_15s")
  audio_path: str
  scene_assets: list   (obrazy/wideo z cache)
  clip_start: float    (0.0 dla głównego, offset dla rolek)
  clip_end: float      (duration dla głównego, clip_end dla rolek)
  platform: str        (youtube/reels/square)
  output_path: str

### Logowanie postępu przy równoległym montażu

Wyświetlaj status wszystkich montaży jednocześnie:
  Montaż równoległy (4 wątki):
  [youtube   ] ████████░░░░ 65% — 00:45 pozostało
  [rolka A   ] ██████░░░░░░ 48% — 01:02 pozostało
  [rolka B   ] ████░░░░░░░░ 32% — 01:18 pozostało
  [rolka C   ] ██░░░░░░░░░░ 18% — 01:35 pozostało

Jeśli rich/progress bar niedostępny: zwykłe logi z prefixem nazwy.

### Ograniczenia sprzętowe na Macu

Mac M2 ma 8 rdzeni wydajnościowych.
4 równoległe FFmpeg to bezpieczne maximum.
Dodaj ostrzeżenie jeśli RAM < 16GB:
"Uwaga: równoległy montaż wymaga ~8GB RAM. Jeśli Mac zwalnia
użyj --sequential-assembly"

Flaga --sequential-assembly: wyłącza równoległość Stage 4
(powrót do sekwencyjnego dla słabszych Maców).

### Współdzielone zasoby między montażami

Wszystkie montaże czytają z cache (tylko odczyt) — bezpieczne:
  output/tmp/{hash}/scene_NNN.jpg — odczyt wielu procesów naraz
  output/tmp/{hash}/animated_NNN.mp4 — odczyt wielu procesów naraz
  output/tmp/{hash}/audio_analysis.json — odczyt

Każdy montaż pisze do osobnego pliku wyjściowego — brak konfliktu:
  output/pelny/nazwa_youtube.mp4
  output/social/nazwa_rolka_A_15s.mp4
  output/social/nazwa_rolka_B_15s.mp4
  output/social/nazwa_rolka_C_15s.mp4

Pliki tymczasowe FFmpeg (jeśli potrzebne) w osobnych podfolderach:
  output/tmp/{hash}/assembly_youtube/
  output/tmp/{hash}/assembly_rolka_A/

### Kolejność priorytetów

Jeśli system jest przeciążony i jeden montaż musi poczekać:
  Priorytet 1: youtube (najdłuższy, najważniejszy)
  Priorytet 2: rolka A (zwykle refren — najpopularniejsza)
  Priorytet 3: rolka B
  Priorytet 4: rolka C

## Integracja w assembler.py i musicvid.py

W musicvid.py gdy --preset all lub --preset social:
  Zamiast: for variant in variants: assemble_single(variant)
  Użyj: assemble_all_parallel(variants)

Gdy --preset full lub brak --preset:
  Jeden montaż — bez zmian, bez ThreadPoolExecutor.

Gdy --sequential-assembly podane:
  Zawsze sekwencyjnie niezależnie od --preset.

## Testy
- assemble_all_parallel: mockuj assemble_single, sprawdź że
  wszystkie 4 wywołania są uruchamiane równolegle (nie sekwencyjnie)
- Błąd jednego montażu nie zatrzymuje pozostałych
- Wyniki zawierają ścieżki do wszystkich udanych plików
- --sequential-assembly: assemble_single wywoływany sekwencyjnie
- Pliki wyjściowe trafiają do właściwych podfolderów

## Acceptance Criteria
- --preset all: 4 montaże uruchamiane równolegle przez ThreadPoolExecutor
- Czas Stage 4 = czas najdłuższego montażu (nie suma wszystkich)
- Błąd jednej rolki nie zatrzymuje głównego teledysku
- --sequential-assembly przywraca sekwencyjne zachowanie
- Wszystkie pliki wyjściowe w prawidłowych folderach
- python3 -m pytest tests/ -v przechodzi
