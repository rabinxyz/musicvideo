# Idea

# Spec: Naprawa ucinania dolnych wydłużeń liter w napisach (j, g, y, p, q)

## Problem
MoviePy TextClip ucina dolne wydłużenia liter (descenders) takich jak
j, g, y, p, q. Litera "j" ma ucięty ogon bo ImageMagick oblicza
wysokość boxa na podstawie cap-height bez uwzględnienia descenderów.

## Przyczyna techniczna
ImageMagick convert oblicza boundingbox tekstu bez descender space.
TextClip w MoviePy używa tego boundingboxa bezpośrednio — bez marginesu.

## Poprawka w assembler.py

### Metoda 1 — padding przez interline (najprostsza)
Przy tworzeniu TextClip dodaj parametr interline z ujemną wartością
lub użyj większego font_size z późniejszym skalowaniem.

Zamiast:
  TextClip(text=lyric_text, font_size=58, ...)

Użyj:
  TextClip(text=lyric_text, font_size=58, interline=-5, ...)

Interline=-5 dodaje przestrzeń pod ostatnią linijką tekstu.

### Metoda 2 — padding przez size (rekomendowana)
Jawnie ustaw wysokość TextClip większą niż domyślna:

  font_size = 58
  padding_bottom = int(font_size * 0.35)  # 35% rozmiaru fontu na descenders
  
  txt_clip = TextClip(
      text=lyric_text,
      font_size=font_size,
      size=(1600, font_size + padding_bottom),  # jawna wysokość z paddingiem
      color='white',
      stroke_color='black',
      stroke_width=2,
      font=font_path,
      method='caption',
      text_align='center',
  )

Wysokość = font_size + 35% = 58 + 20 = 78px
To daje wystarczający margines na j, g, y, p, q, ą, ę.

### Metoda 3 — przez ImageMagick label zamiast caption
Zmień method z 'caption' na 'label':
  method='label'
Label używa innego algorytmu obliczania boundingboxa który
lepiej obsługuje descenders.

Przetestuj wszystkie 3 metody i użyj tej która działa.

## Testowy string
Testuj zawsze z: "Tylko w Bogu jest moja dusza"
Zawiera: j, g, y — wszystkie descenders.
Oraz polskie: ą, ę, ó, ł — upewnij się że też nie są ucinane.

## Pozycja po poprawce
Po zwiększeniu wysokości TextClip upewnij się że pozycja
bottom center jest liczona od zewnętrznej krawędzi paddingowanego
clipu — nie od baseline tekstu.
Margines od dołu ekranu: 80px (lub 200px dla reels).

## Testy
- TextClip z "gjypq": dolne wydłużenia widoczne w wideo
- TextClip z "Tylko w Bogu": litera j nie ucięta
- Polskie znaki ą ę ó: nie ucięte
- Pozycja napisów: bottom center z marginesem 80px

## Acceptance Criteria
- Litera "j" w "Tylko w Bogu" ma widoczny ogon w wideo
- Litery g, y, p, q nie są ucinane
- Polskie znaki ą ę nie są ucinane
- Napisy nadal wycentrowane i w odpowiedniej pozycji
- python3 -m pytest tests/ -v przechodzi
