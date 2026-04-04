# Spec: Animacje napisów — karaoke style i slide up (format ASS)

## Cel
Dodać nowe style animacji napisów jako opcję obok istniejącego fade.
Obecna implementacja MoviePy TextClip zostaje jako domyślna i fallback.
Nowe style używają formatu ASS + FFmpeg dla lepszej jakości i wydajności.

## Nowa flaga CLI
--subtitle-style [fade|karaoke|slide-up|word-pop]  (domyślnie: fade)

### fade (domyślny — obecna implementacja, BEZ ZMIAN)
Zachowaj dokładnie obecny kod MoviePy TextClip jako domyślne zachowanie.
Nie ruszaj istniejącej implementacji.

### karaoke (nowy — format ASS)
Słowa podświetlane jedno po drugim zsynchronizowane z muzyką.
Tekst przed aktywnym słowem: biały opacity 60%
Aktywne słowo: biały pełny, lekko powiększony
Tekst po aktywnym słowie: biały opacity 30%
Wymaga word-level timestamps z Whisper.
Gdy word timestamps niedostępne: podziel czas segmentu równomiernie
przez liczbę słów (karaoke działa, ale mniej precyzyjnie).

### slide-up (nowy — format ASS)
Cała linijka wylatuje płynnie z dołu do pozycji docelowej.
Czas animacji wejścia: 0.3s ease-out
Czas animacji wyjścia: 0.2s ease-in (znika w górę)

### word-pop (nowy — format ASS)
Każde słowo pojawia się osobno z efektem pop (scale 0→110%→100%).
Słowa budują linijkę jedno po drugim w tempie mowy.

## Dlaczego ASS dla nowych stylów

Format ASS (Advanced SubStation Alpha) to standard branżowy:
- FFmpeg renderuje go natywnie — szybciej niż Python frame-by-frame
- Natywna obsługa karaoke (tag {\k} per słowo)
- Natywna obsługa animacji pozycji (tag {\move})
- Pełna obsługa UTF-8 z polskimi znakami — zero problemów z ą ę ó
- Ten sam format co YouTube, Netflix, profesjonalne narzędzia

## Implementacja

### Nowy moduł musicvid/pipeline/subtitle_ass.py
Tylko dla trybów karaoke, slide-up, word-pop.
Nie dotyka istniejącego kodu TextClip.

Funkcje:
- generate_ass_file(lyrics, style, config, output_path) -> str
  Główna funkcja — generuje plik .ass i zwraca ścieżkę.
  style: "karaoke" | "slide-up" | "word-pop"

- _generate_header(width, height, font_name, font_size) -> str
  Sekcje [Script Info] i [V4+ Styles].

- _generate_karaoke_events(lyrics_with_words) -> str
  Linie [Events] z tagami {\k} per słowo (czas w centisekundach).
  Format linii: {\k50}Pan {\k40}jest {\k60}moim {\k45}pasterzem

- _generate_slide_up_events(lyrics) -> str
  Linie [Events] z tagami {\move(x,y_start,x,y_end,0,300)}.

- _generate_word_pop_events(lyrics_with_words) -> str
  Osobne linie per słowo z tagiem {\t(\fscx110\fscy110\fscx100\fscy100)}.

- burn_ass_subtitles(video_path, ass_path, output_path) -> str
  FFmpeg: ffmpeg -i video.mp4 -vf "ass=subtitles.ass" output.mp4
  Wywołuje po wygenerowaniu wideo przez MoviePy.

### Integracja w assembler.py

Gdy --subtitle-style fade (domyślny):
  Używaj obecnej implementacji MoviePy TextClip — BEZ ZMIAN.

Gdy --subtitle-style karaoke/slide-up/word-pop:
  1. Wygeneruj wideo BEZ napisów przez MoviePy
  2. Wygeneruj plik .ass przez subtitle_ass.py
  3. Wywołaj burn_ass_subtitles() — FFmpeg wpal napisy
  4. Usuń plik pośredni bez napisów

## Styl wizualny ASS (spójny z obecnymi napisami)

Font: Montserrat Light (ten sam co obecne napisy)
Rozmiar: 58px dla 1080p
Kolor tekstu: biały &H00FFFFFF
Outline: 2px czarny &H00000000
Shadow: 1px z opacity 60%
Pozycja: bottom center, margines 80px od dołu (200px dla 9:16)
Wyrównanie: center

## Testy
- --subtitle-style fade: używa obecnej implementacji TextClip (bez zmian)
- generate_ass_file karaoke: plik .ass zawiera tagi {\k}
- generate_ass_file slide-up: plik .ass zawiera tagi {\move}
- Polski tekst "ąęółźżćńś": plik .ass zakodowany UTF-8
- burn_ass_subtitles: mockuj FFmpeg, sprawdź komendę z "ass="
- Brak word timestamps: karaoke działa z równomiernym podziałem czasu

## Acceptance Criteria
- --subtitle-style fade: zachowanie identyczne jak przed zmianą
- --subtitle-style karaoke: słowa podświetlane jedno po drugim
- --subtitle-style slide-up: linijki wylatują z dołu
- --subtitle-style word-pop: słowa pojawiają się z efektem pop
- Polskie znaki poprawne we wszystkich stylach
- Styl domyślny (fade) nie wymaga FFmpeg — MoviePy jak dotychczas
- python3 -m pytest tests/ -v przechodzi
