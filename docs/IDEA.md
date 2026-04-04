# Idea

Dodaj cache dla posrednich wynikow w musicvid aby przyspieszyc testowanie.

## ZASADA
Jesli plik audio juz byl przetwarzany, wczytaj zapisane wyniki zamiast liczyc od nowa.
Nowa opcja CLI: --new (wymus przeliczenie wszystkiego od poczatku)

## CACHE DIRECTORY
output/tmp/{audio_hash}/
  audio_analysis.json    - wynik audio_analyzer.py (Stage 1)
  scene_plan.json        - wynik director.py (Stage 2)
  video_manifest.json    - lista pobranych/wygenerowanych klipow (Stage 3)

audio_hash = MD5 pierwszych 64KB pliku audio (szybkie, nie czyta calego pliku)

## LOGIKA W musicvid.py

def get_audio_hash(audio_path):
    import hashlib
    with open(audio_path, 'rb') as f:
        return hashlib.md5(f.read(65536)).hexdigest()[:12]

Przed kazdym Stage sprawdz czy cache istnieje:
- Stage 1: jesli audio_analysis.json istnieje i nie --new -> wczytaj i skipuj
- Stage 2: jesli scene_plan.json istnieje i nie --new -> wczytaj i skipuj  
- Stage 3: jesli video_manifest.json istnieje i nie --new -> sprawdz czy pliki nadal istnieja na dysku, jesli tak skipuj pobieranie

Logowanie:
  [1/4] Audio analysis... CACHED (skipped)
  [2/4] Scene planning... CACHED (skipped)
  [3/4] Fetching videos... CACHED (skipped)
  [4/4] Assembling video...

## OPCJA --new
musicvid song.mp3 --new
Usun cache dla tego pliku i przelicz wszystko od poczatku.
