# Spec: Naprawa wyświetlania wideo — pasy, skalowanie, napisy

## Problem 1 — czarne pasy góra i dół
Cinematic bars (12% góra + 12% dół) są włączone domyślnie.
Dla trybu youtube 16:9 powinny być domyślnie WYŁĄCZONE.
Włączone tylko gdy użytkownik jawnie poda --effects full.

Zmień w platform_config.py lub assembler.py:
cinematic_bars domyślnie: False dla wszystkich platform
Włącz tylko gdy: --effects full I użytkownik jawnie prosi

## Problem 2 — obrazy źle skalowane (nie wypełniają ekranu)
Obrazy z BFL (1024x768) muszą być przeskalowane do pełnej rozdzielczości
docelowej (1920x1080) przed zastosowaniem Ken Burns.

W assembler.py przy tworzeniu ImageClip:
- Użyj resize() do wypełnienia całego kadru PRZED Ken Burns
- Użyj metody "fill" (cover) — zachowaj proporcje, przytnij nadmiar
- NIE używaj "fit" (contain) — zostawia czarne pasy
- NIE rozciągaj (stretch) — deformuje obraz

Poprawna kolejność:
1. Wczytaj obraz ImageClip
2. Oblicz scale = max(target_w / img_w, target_h / img_h)
3. Przeskaluj: clip = clip.resized(scale)
4. Wyśrodkuj i przytnij do target_w x target_h
5. Zastosuj Ken Burns na już przeskalowanym klipie

## Problem 3 — brak napisów
Napisy nie pojawiają się w wideo.
Sprawdź i napraw w assembler.py:

Możliwe przyczyny:
a) TextClip rzuca błąd cicho — dodaj try/except z logowaniem
b) Lyrics lista jest pusta — sprawdź czy analysis["lyrics"] ma elementy
c) Font nie istnieje — dodaj fallback do DejaVuSans
d) Pozycja napisów poza kadrem — sprawdź czy y < frame_height
e) Napisy generowane ale nie dodane do CompositeVideoClip — sprawdź kolejność

Dodaj log dla każdej linijki napisów:
print(f"Napis: '{lyric['text']}' start={lyric['start']:.1f}s end={lyric['end']:.1f}s")

Jeśli lista lyrics pusta: wyświetl ostrzeżenie i kontynuuj bez napisów.
Jeśli font nie znaleziony: użyj DejaVuSans jako fallback bez rzucania błędu.

## Acceptance Criteria
- Wideo wypełnia cały ekran bez czarnych pasów góra/dół
- Obrazy skalowane cover (nie contain, nie stretch)
- Napisy widoczne w wideo
- --effects minimal i --effects full nie dodają cinematic bars domyślnie
- python3 -m pytest tests/ -v przechodzi
