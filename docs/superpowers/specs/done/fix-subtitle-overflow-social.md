# Spec: Naprawa napisów na rolkach — tekst przechodzi do niewidocznej drugiej linii

## Problem
Na rolkach 9:16 (1080x1920) napisy są za szerokie i zawijają się
na drugą linię która wychodzi poza dolny margines ekranu.

Przyczyna:
  TextClip ma size=(1600, None) — za szeroki dla formatu 9:16
  Font_size=64-66px (duży) + długa linia = zawijanie
  Pozycja bottom z marginesem 200px nie uwzględnia drugiej linii

## Poprawka w assembler.py

### 1. Szerokość TextClip zależy od platformy

Obecne: size=(1600, None) dla wszystkich platform
Zmień na:
  if platform in ['reels', 'shorts', 'tiktok']:
      subtitle_width = 900   # wąski ekran 9:16, zostawia marginesy
  else:
      subtitle_width = 1600  # szeroki ekran 16:9

### 2. Font size mniejszy dla rolek

Obecne: font_size=64-66px dla chorus na rolkach
Zmień na:
  if platform in ['reels', 'shorts', 'tiktok']:
      font_size = min(font_size, 52)  # cap na 52px dla rolek
  # Dla pełnego teledysku pozostaw bez zmian

### 3. Maksymalna długość linii tekstu dla rolek

Przed tworzeniem TextClip dla rolek:
Jeśli linia tekstu ma > 25 znaków — podziel na dwie linie:

  def wrap_for_portrait(text, max_chars=25):
      words = text.split()
      lines = []
      current = []
      current_len = 0
      for word in words:
          if current_len + len(word) + 1 > max_chars and current:
              lines.append(' '.join(current))
              current = [word]
              current_len = len(word)
          else:
              current.append(word)
              current_len += len(word) + 1
      if current:
          lines.append(' '.join(current))
      return '\n'.join(lines)

  if platform in ['reels', 'shorts', 'tiktok']:
      lyric_text = wrap_for_portrait(lyric_text, max_chars=25)

### 4. Pozycja napisów uwzględnia wieloliniowość

Gdy tekst ma dwie linie: podnieś napis wyżej żeby zmieścił się na ekranie.
  lines_count = lyric_text.count('\n') + 1
  line_height = font_size * 1.4
  total_height = lines_count * line_height

  margin_bottom = 200  # dla rolek
  y_position = frame_height - total_height - margin_bottom

  txt_clip = txt_clip.with_position(('center', y_position))

### 5. Bezpieczna strefa napisów dla rolek

Napisy MUSZĄ być w bezpiecznej strefie: między 10% a 85% wysokości ekranu.
  safe_top = frame_height * 0.10      # 192px od góry
  safe_bottom = frame_height * 0.85   # 1632px od góry

  Napis musi mieścić się między safe_top a safe_bottom.
  Jeśli wychodzi poza: zmniejsz font_size o 4px i sprawdź ponownie.

## Testy
- Linia > 25 znaków jest zawijana na dwie linie
- Dwie linie mieszczą się w bezpiecznej strefie (10%-85%)
- font_size dla rolek <= 52px
- subtitle_width dla rolek = 900px
- Brak ucinania drugiej linii

## Acceptance Criteria
- Napisy na rolkach zawsze w pełni widoczne
- Żaden tekst nie wychodzi poza dolny margines
- Długie linie zawijane do max 25 znaków
- Font size dostosowany do formatu 9:16
