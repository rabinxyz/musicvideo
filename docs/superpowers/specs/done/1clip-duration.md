# Spec: Skrócone wideo na social media (15/20/25/30 sekund)

## Cel
Dodać opcję generowania krótkiego klipu z piosenki zamiast pełnego teledysku.
Przydatne do promowania na FB Reels, Instagram, YouTube Shorts, TikTok.

## Nowa flaga CLI
--clip [15|20|25|30]  (domyślnie: brak — pełny utwór)

Użycie:
python3 -m musicvid.musicvid song.mp3 --clip 15
python3 -m musicvid.musicvid song.mp3 --clip 30 --platform reels
python3 -m musicvid.musicvid song.mp3 --clip 20 --platform shorts --effects full

## Logika wyboru fragmentu

Gdy --clip podane, Claude API wybiera najlepszy fragment piosenki.

Wyślij do Claude:
- Pełną listę segmentów Whisper z timestampami i tekstem
- Żądaną długość klipu w sekundach
- Informację o sekcjach (intro/verse/chorus/outro z librosa)

Claude zwraca JSON:
{
  "start": float,  — czas początku klipu w sekundach
  "end": float,    — czas końca klipu w sekundach
  "reason": string — krótkie uzasadnienie wyboru
}

Zasady dla Claude przy wyborze fragmentu:
- Preferuj refren (chorus) — najbardziej rozpoznawalny fragment
- Unikaj początku intro (pierwsze 5 sekund) chyba że to jedyna opcja
- Unikaj urwania w połowie słowa lub linii tekstu
- Jeśli możliwe zacznij na początku frazy muzycznej (po biciu)
- Kończ na końcu linii tekstu, nie w środku słowa
- Długość end-start musi być dokładnie równa żądanej długości +/- 2s

## Przetwarzanie pipeline dla trybu clip

Stage 1 — analiza audio: pełna (Whisper + librosa na całości)
Stage 2 — Claude reżyser: generuje plan scen tylko dla wybranego fragmentu
  (start do end, nie dla całej piosenki)
Stage 3 — generowanie obrazów: tylko dla scen w oknie start-end
Stage 4 — montaż: tylko fragment start-end z audio

Przytnij audio do fragmentu: audio.subclipped(start, end)
Przytnij lyrics do fragmentu: tylko segmenty gdzie start >= clip_start
  i end <= clip_end, dostosuj start/end względem clip_start (odejmij offset)

## Efekty specjalne dla klipu

Fade in audio: 0.5s na początku klipu
Fade out audio: 1.0s na końcu klipu
Fade in video: 0.5s
Fade out video: 1.0s

Opcjonalnie dodaj planszę na początku lub końcu (--title-card):
Plansza 2s z tytułem piosenki i nazwą wykonawcy (czarny lub biały tekst
na rozmytym ostatnim kadrze). Domyślnie wyłączona.

## Nazewnictwo pliku wyjściowego

piosenka_15s.mp4
piosenka_30s_reels.mp4
piosenka_20s_shorts.mp4

## Cache

Wynik wyboru fragmentu przez Claude cachuj w:
output/tmp/{hash}/clip_{duration}s.json
Zmiana --clip invaliduje tylko ten plik, nie całą analizę audio.

## Testy
- Wybrany fragment ma długość zbliżoną do żądanej (+/- 2s)
- audio.subclipped używa poprawnych czasów start/end
- Lyrics przycinane i offsetowane względem clip_start
- Fade in/out zastosowane na początku i końcu
- Nazwa pliku zawiera sufiks z czasem trwania
- Kombinacja --clip 30 --platform reels: plik 30s w formacie 9:16

## Acceptance Criteria
- --clip 15 generuje wideo ~15 sekund z najlepszego fragmentu piosenki
- --clip 30 --platform reels generuje 30s wideo w formacie 9:16
- Klip zaczyna i kończy się na granicy frazy — nie urywa słów
- Fade in/out audio i video zastosowane
- Pełny utwór generowany gdy --clip nie podane (bez zmian)
- python3 -m pytest tests/ -v przechodzi
