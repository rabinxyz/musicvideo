# Spec: Naprawa pobierania czcionki Montserrat

## Problem
font_loader.py próbuje pobrać Montserrat z Google Fonts jako ZIP
ale API zwraca HTML lub inny format — "File is not a zip file"

## Poprawka w font_loader.py

Zmień URL pobierania z Google Fonts ZIP na bezpośredni plik TTF z GitHub:

MONTSERRAT_URL = "https://github.com/google/fonts/raw/main/ofl/montserrat/Montserrat-Light.ttf"

Pobierz bezpośrednio jako plik TTF bez rozpakowywania:
  response = requests.get(MONTSERRAT_URL, timeout=30)
  response.raise_for_status()
  font_path.write_bytes(response.content)

Usuń cały kod który rozpakowuje ZIP — nie jest potrzebny.

## Fallback
Jeśli pobieranie się nie uda: użyj DejaVuSans przez ImageMagick.
Nie rzucaj wyjątku — kontynuuj z fallback fontem.

## Acceptance Criteria
- Montserrat-Light.ttf pobierany bezpośrednio jako TTF z GitHub
- Brak błędu "File is not a zip file"
- Fallback do DejaVuSans gdy pobieranie się nie uda
