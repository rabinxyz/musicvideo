# Idea

# Spec: Naprawa pipeline — lyrics nie trafiają do montażu

## Problem
Whisper działa poprawnie (20 segmentów, dobry timing, polski tekst).
Ale analysis["lyrics"] = [] w cache — pipeline używa starego audio_analysis.json
który powstał przed poprawką Whispera.

Dwa osobne problemy do naprawy:

## Problem 1 — --new nie usuwa audio_analysis.json

W musicvid.py gdy --new=True:
Obecny kod usuwa scene_plan.json ale NIE usuwa audio_analysis.json.
Efekt: Whisper nie jest wywoływany ponownie — stary pusty lyrics zostaje.

Napraw: gdy --new=True usuń Z CACHE wszystkie pliki przed startem:
  if new and cache_dir.exists():
      for f in cache_dir.glob("*.json"):
          f.unlink()
      for f in cache_dir.glob("scene_*.jpg"):
          f.unlink()
      for f in cache_dir.glob("scene_*.mp4"):
          f.unlink()
      for f in cache_dir.glob("animated_*.mp4"):
          f.unlink()
      print(f"Cache wyczyszczony: {cache_dir}")

## Problem 2 — plik tekst.txt nie jest podawany do merge

Gdy plik tekst.txt jest auto-wykryty obok MP3:
Pipeline wywołuje analyze_audio() BEZ przekazania lyrics_path.
Efekt: Whisper daje tekst (błędny) zamiast użyć pliku.

Napraw w musicvid.py:
  # Auto-wykryj plik lyrics obok audio
  lyrics_path = None
  audio_dir = Path(audio_path).parent
  txt_files = list(audio_dir.glob("*.txt"))
  if len(txt_files) == 1:
      lyrics_path = str(txt_files[0])
      print(f"Auto-wykryty plik tekstu: {txt_files[0].name}")

  # Przekaż do analyze_audio
  analysis = analyze_audio(audio_path, lyrics_path=lyrics_path)

## Problem 3 — merge_whisper_with_lyrics_file nie jest wywoływane

W audio_analyzer.py brakuje logiki łączenia Whisper + plik.
Dodaj parametr lyrics_path do analyze_audio():

def analyze_audio(audio_path, output_dir=None, whisper_model="small", lyrics_path=None):

Po transkrypcji Whispera:
  if lyrics_path:
      # Wczytaj linie z pliku
      with open(lyrics_path, encoding='utf-8') as f:
          file_lines = [l.strip() for l in f.readlines() if l.strip()]

      # Połącz timing z Whispera z tekstem z pliku SEKWENCYJNIE
      whisper_segments = lyrics  # lista [{start, end, text}] z Whispera
      N_seg = len(whisper_segments)
      N_lines = len(file_lines)

      merged = []

      if N_seg == 0:
          # Fallback: równomierne rozłożenie bez Whispera
          vocal_start = 30.0  # domyślne intro
          text_duration = duration - vocal_start
          time_per_line = text_duration / max(N_lines, 1)
          for i, line in enumerate(file_lines):
              merged.append({
                  "start": round(vocal_start + i * time_per_line, 2),
                  "end": round(vocal_start + (i+1) * time_per_line - 0.2, 2),
                  "text": line
              })

      elif N_seg >= N_lines:
          # Więcej segmentów niż linii — grupuj segmenty
          ratio = N_seg / N_lines
          for i, line in enumerate(file_lines):
              seg_start = round(i * ratio)
              seg_end = min(round((i+1) * ratio), N_seg)
              group = whisper_segments[seg_start:seg_end]
              if not group:
                  continue
              merged.append({
                  "start": group[0]["start"],
                  "end": group[-1]["end"],
                  "text": line
              })

      else:
          # Więcej linii niż segmentów — podziel segmenty
          ratio = N_lines / N_seg
          for i, seg in enumerate(whisper_segments):
              line_start = round(i * ratio)
              line_end = min(round((i+1) * ratio), N_lines)
              group_lines = file_lines[line_start:line_end]
              if not group_lines:
                  continue
              seg_duration = seg["end"] - seg["start"]
              time_per = seg_duration / len(group_lines)
              for j, line in enumerate(group_lines):
                  merged.append({
                      "start": round(seg["start"] + j * time_per, 2),
                      "end": round(seg["start"] + (j+1) * time_per - 0.2, 2),
                      "text": line
                  })

      lyrics = merged
      print(f"Tekst z pliku: {N_lines} linii dopasowane do {N_seg} segmentów Whisper")

  print(f"Lyrics: {len(lyrics)} napisów")
  if lyrics:
      print(f"  Pierwszy: '{lyrics[0]['text']}' @ {lyrics[0]['start']:.1f}s")
      print(f"  Ostatni:  '{lyrics[-1]['text']}' @ {lyrics[-1]['start']:.1f}s")

## Acceptance Criteria
- --new czyści CAŁY cache (wszystkie .json, scene_*.jpg, scene_*.mp4)
- auto-wykryty tekst.txt jest przekazywany do analyze_audio()
- analyze_audio() łączy timing Whisper z tekstem z pliku sekwencyjnie
- analysis["lyrics"] ma > 0 elementów po transkrypcji
- Tekst napisów pochodzi z tekst.txt (poprawna polszczyzna)
- Timing pochodzi z Whisper (zsynchronizowany z muzyką)
- python3 -m pytest tests/ -v przechodzi
