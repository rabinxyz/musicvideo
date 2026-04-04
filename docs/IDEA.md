# Idea

# Spec: Tryb preset — pełna pieśń + 3 rolki z różnych fragmentów

## Cel
Jedno uruchomienie generuje komplet materiałów:
- pełny teledysk YouTube 16:9
- 3 rolki po 15s z różnych fragmentów piosenki w formacie 9:16

## Nowa flaga CLI
--preset [full|social|all]  (domyślnie: brak — zachowanie bez zmian)

### --preset full
Tylko pełny teledysk YouTube 16:9. Identyczne z dotychczasowym zachowaniem.

### --preset social
Tylko 3 rolki po 15s z różnych fragmentów, format 9:16. Bez pełnego teledysku.

### --preset all
Wszystko naraz:
- Pełny teledysk YouTube 16:9
- Rolka 1 z 15s (fragment A)
- Rolka 2 z 15s (fragment B)
- Rolka 3 z 15s (fragment C)

## Wybór 3 różnych fragmentów przez Claude

Wyślij do Claude jedną prośbę o wybranie 3 fragmentów po 15s.

Zasady dla Claude przy wyborze:
- Fragmenty nie mogą się nakładać ani stykać (minimum 5s przerwy między nimi)
- Każdy fragment pochodzi z innej sekcji piosenki (intro/verse/chorus/bridge/outro)
- Preferuj fragmenty z mocnym tekstem i wyraźną melodią
- Każdy fragment zaczyna się na początku frazy — nie w środku słowa
- Każdy fragment kończy się na końcu linii tekstu
- Opisz krótko dlaczego wybrałeś każdy fragment (pole "reason")

Claude zwraca JSON:
{
  "clips": [
    {
      "id": "A",
      "start": float,
      "end": float,
      "section": "chorus",
      "reason": "Refren — najbardziej rozpoznawalny fragment"
    },
    {
      "id": "B",
      "start": float,
      "end": float,
      "section": "verse",
      "reason": "Pierwsza zwrotka — dobry hook na początku"
    },
    {
      "id": "C",
      "start": float,
      "end": float,
      "section": "bridge",
      "reason": "Bridge — emocjonalny szczyt piosenki"
    }
  ]
}

Cachuj w output/tmp/{hash}/social_clips.json.

## Logika wykonania — optymalizacja

Stage 1 — analiza audio: tylko raz
Stage 2 — reżyseria Claude: tylko raz (pełny plan scen)
Stage 3 — generowanie obrazów: tylko raz (cache współdzielony)
Stage 4 — montaż: osobno dla każdego wariantu

Kolejność montażu:
1. Pełny teledysk (jeśli --preset full lub all)
2. Rolka A 15s
3. Rolka B 15s
4. Rolka C 15s

## Struktura folderów wyjściowych

output/
  pelny/
    Tylko_w_Bogu_youtube.mp4
  social/
    Tylko_w_Bogu_rolka_A_15s.mp4
    Tylko_w_Bogu_rolka_B_15s.mp4
    Tylko_w_Bogu_rolka_C_15s.mp4

## Format rolek 9:16

Rozdzielczość: 1080x1920
FPS: 30
Napisy: margines od dołu 200px (UI platform przykrywa dół ekranu)
Cinematic bars: wyłączone
Ken Burns: tylko zoom in/out i pan_up/pan_down (bez poziomego)
Fade in audio: 0.5s
Fade out audio: 1.5s
Fade in video: 0.5s
Fade out video: 1.0s

Konwersja obrazów 16:9 → 9:16:
Smart crop środkowej części + rozmyte tło (blur całego obrazu
skalowanego do 9:16 z ostrym centrum jako overlay).
Wygląda profesjonalnie i nie deformuje głównego motywu.

## Logowanie postępu

[1/4] Analiza audio...
[2/4] Reżyseria (Claude)...
[3/4] Generowanie obrazów...
[4/4] Montaż:
  → Pełny teledysk YouTube (1/4)... ✅
  → Rolka A — chorus (2/4)...       ✅
  → Rolka B — verse (3/4)...        ✅
  → Rolka C — bridge (4/4)...       ✅

Gotowe! Wygenerowano 4 pliki:
  output/pelny/Tylko_w_Bogu_youtube.mp4
  output/social/Tylko_w_Bogu_rolka_A_15s.mp4
  output/social/Tylko_w_Bogu_rolka_B_15s.mp4
  output/social/Tylko_w_Bogu_rolka_C_15s.mp4

## Opcja --reel-duration
--reel-duration [15|20|30]  (domyślnie: 15)
Zmienia długość wszystkich 3 rolek.

Użycie:
python3 -m musicvid.musicvid song.mp3 --preset social --reel-duration 30
→ generuje 3 rolki po 30s z różnych fragmentów

## Cache

Współdzielone między wariantami:
- audio_analysis.json
- scene_plan.json
- scene_NNN.jpg
- social_clips.json (wybrane fragmenty — invalidowany przez --reel-duration)

Nie cachuj gotowych MP4 — montaż jest szybki gdy obrazy już istnieją.

## Testy
- --preset all: generuje 4 pliki (1 youtube + 3 rolki)
- --preset social: generuje tylko 3 rolki, brak folderu pelny/
- --preset full: generuje tylko pełny teledysk, brak folderu social/
- 3 fragmenty nie nakładają się czasowo
- Każdy fragment pochodzi z innej sekcji
- Rolki mają format 1080x1920
- --reel-duration 30: rolki po 30s
- Stage 1-3 wykonywane tylko raz przy --preset all

## Acceptance Criteria
- python3 -m musicvid.musicvid song.mp3 --preset all
  generuje pełny teledysk + 3 rolki w jednym uruchomieniu
- 3 rolki pokazują 3 różne fragmenty piosenki
- Rolki mają format 9:16 gotowy na FB/Instagram Reels
- Obrazy generowane tylko raz, montaż 4x
- --reel-duration zmienia długość rolek
- python3 -m pytest tests/ -v przechodzi
