# Spec: Finalna naprawa napisów — lyrics_path w analyze_audio

## Diagnoza
analyze_audio() nie ma parametru lyrics_path.
Merge Whisper+plik nigdy nie jest wywoływany.
Tekst z Whisper (błędny) trafia do lyrics zamiast tekstu z pliku.

## Poprawka 1 — dodaj lyrics_path do analyze_audio()

Zmień sygnaturę funkcji:
  def analyze_audio(audio_path, output_dir=None, whisper_model="small", lyrics_path=None):

Po zbudowaniu lyrics z Whispera (po pętli for segment in transcription...):

  if lyrics_path and Path(lyrics_path).exists():
      from musicvid.pipeline.lyrics_parser import merge_whisper_with_lyrics_file
      with open(lyrics_path, encoding="utf-8") as f:
          file_lines = [l.strip() for l in f.readlines() if l.strip()]
      lyrics = merge_whisper_with_lyrics_file(lyrics, file_lines)
      print(f"[Lyrics] Plik: {len(file_lines)} linii + Whisper: {len(lyrics)} segmentów → {len(lyrics)} napisów")
      print(f"[Lyrics] Pierwszy: '{lyrics[0]['text']}' @ {lyrics[0]['start']:.1f}s")
  else:
      print(f"[Lyrics] Whisper: {len(lyrics)} segmentów (brak pliku tekstu)")

## Poprawka 2 — auto-wykryj tekst.txt w musicvid.py i przekaż do analyze_audio

W musicvid.py przy wywołaniu analyze_audio():
Znajdź gdzie jest wywołanie analyze_audio(audio_path, ...) i dodaj lyrics_path:

  # Auto-wykryj plik lyrics obok audio
  lyrics_path = None
  audio_dir = Path(audio_path).parent
  txt_files = [f for f in audio_dir.glob("*.txt") if f.is_file()]
  if len(txt_files) == 1:
      lyrics_path = str(txt_files[0])
      click.echo(f"  Auto-wykryty plik tekstu: {txt_files[0].name}")
  elif len(txt_files) > 1:
      click.echo(f"  Znaleziono {len(txt_files)} plików .txt — użyj --lyrics aby wybrać")

  # Gdy --lyrics podane jawnie — nadpisz auto-wykryty
  if cli_lyrics_path:
      lyrics_path = cli_lyrics_path

  analysis = analyze_audio(
      str(audio_path),
      output_dir=str(cache_dir),
      lyrics_path=lyrics_path
  )

## Poprawka 3 — merge_whisper_with_lyrics_file musi być zaimplementowana

Sprawdź czy lyrics_parser.py ma funkcję merge_whisper_with_lyrics_file.
Jeśli nie ma — dodaj:

def merge_whisper_with_lyrics_file(whisper_lyrics, file_lines):
    N_seg = len(whisper_lyrics)
    N_lines = len(file_lines)

    if N_seg == 0 or N_lines == 0:
        return whisper_lyrics

    merged = []

    if N_seg >= N_lines:
        ratio = N_seg / N_lines
        for i, line in enumerate(file_lines):
            seg_start = round(i * ratio)
            seg_end = min(round((i + 1) * ratio), N_seg)
            group = whisper_lyrics[seg_start:seg_end]
            if not group:
                continue
            merged.append({
                "start": group[0]["start"],
                "end": group[-1]["end"],
                "text": line,
                "words": []
            })
    else:
        ratio = N_lines / N_seg
        for i, seg in enumerate(whisper_lyrics):
            line_start = round(i * ratio)
            line_end = min(round((i + 1) * ratio), N_lines)
            group_lines = file_lines[line_start:line_end]
            if not group_lines:
                continue
            seg_duration = seg["end"] - seg["start"]
            time_per = seg_duration / len(group_lines) if group_lines else seg_duration
            for j, line in enumerate(group_lines):
                merged.append({
                    "start": round(seg["start"] + j * time_per, 2),
                    "end": round(seg["start"] + (j + 1) * time_per - 0.15, 2),
                    "text": line,
                    "words": []
                })

    return merged

## Poprawka 4 — cache file name

analyze_audio zapisuje do "analysis.json" ale musicvid.py szuka "audio_analysis.json".
Ujednolicić — zmień w analyze_audio na "audio_analysis.json":
  with open(output_path / "audio_analysis.json", "w") as f:

## Acceptance Criteria
- analyze_audio() przyjmuje lyrics_path jako parametr
- Gdy lyrics_path podany: lyrics zawiera tekst z pliku, timing z Whispera
- Gdy auto-wykryty tekst.txt obok MP3: automatycznie użyty
- print pokazuje "Lyrics: N napisów" > 0
- Pierwszy napis to pierwsza linia z pliku tekst.txt
- Timing pierwszego napisu to czas z Whispera (~30s dla tej piosenki)
