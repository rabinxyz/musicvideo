# Spec: Czcionka napisów — polska obsługa + minimalistyczny styl

## Problem
Obecne napisy używają domyślnej czcionki MoviePy (ImageMagick), która:
- nie obsługuje polskich znaków (ą ę ó ł ź ż ć ń ś)
- wygląda generycznie

## Rozwiązanie

### Czcionka do pobrania
Użyj czcionki Montserrat — darmowa Google Fonts, obsługuje pełne
kodowanie UTF-8 z polskimi znakami, wygląda minimalistycznie i nowocześnie.

Automatycznie pobierz przy pierwszym uruchomieniu jeśli nie ma lokalnie:
URL: https://fonts.google.com/download?family=Montserrat
Zapisz do: musicvid/assets/fonts/Montserrat-Light.ttf

Hierarchia fallback jeśli pobieranie się nie uda:
1. Montserrat-Light.ttf (docelowa)
2. Lato-Regular.ttf
3. DejaVuSans.ttf (zawsze dostępna przez ImageMagick — obsługuje PL znaki)
4. Liberation-Sans

### Styl napisów

Domyślny wygląd:
- czcionka: Montserrat Light
- rozmiar: 58px
- kolor tekstu: biały #FFFFFF
- outline (obwódka): 2px, kolor #000000 opacity 60%
- pozycja: bottom center, margines od dołu 80px
- wyrównanie: center
- interlinia między wyrazami: normalna

Efekt wejścia/wyjścia:
- fade in: 0.3s
- fade out: 0.3s
- całość napisu pojawia się naraz (nie litera po literze)

### Obsługa polskich znaków

Przy tworzeniu TextClip jawnie ustaw encoding UTF-8.
Przed renderowaniem zamień znaki na ich odpowiedniki jeśli
wybrana czcionka nie obsługuje danego glifa — ale tylko jako
ostateczny fallback (nie rób tego przy Montserrat ani DejaVu).

Testuj napisy z tekstem zawierającym: ą ę ó ł ź ż ć ń ś Ą Ę Ó Ł

### Nowa flaga CLI
--font PATH  Ścieżka do własnego pliku .ttf (opcjonalna)
Gdy podana: użyj tej czcionki zamiast domyślnej Montserrat.
Gdy nie podana: użyj automatycznie pobranej Montserrat.

### Gdzie zmienić
Logika czcionki w assembler.py przy tworzeniu TextClip.
Dodaj moduł musicvid/assets/fonts/ jako folder na zasoby.
Dodaj helper font_loader.py w musicvid/pipeline/:
- get_font_path(custom_path=None) -> str
- Sprawdza custom_path → Montserrat lokalna → pobiera Montserrat →
  fallback DejaVuSans
- Pobieranie tylko raz — cache lokalny w musicvid/assets/fonts/

## Testy
- Test że TextClip renderuje poprawnie tekst z polskimi znakami
- Test font_loader: zwraca ścieżkę do istniejącego pliku
- Test fallback: gdy Montserrat niedostępna zwraca DejaVuSans
- Test flagi --font: użyta czcionka to ta z argumentu

## Acceptance Criteria
- Napisy wyświetlają poprawnie: ą ę ó ł ź ż ć ń ś
- Czcionka jest Montserrat Light lub wybrany fallback
- --font pozwala podać własny plik ttf
- Wideo generuje się bez błędów ImageMagick przy polskich znakach
- Wszystkie testy: python3 -m pytest tests/ -v
