# Spec: Pro Music Video Generator — kompleksowy plan jakości

## Cel
Generator który myśli za użytkownika i produkuje profesjonalne teledyski.
Każde wideo ma być MEGA — nie "ok".

## PRIORYTET 1 — Naprawy krytyczne (bez nich nic nie działa)

### 1A — Podwójny merge lyrics (KRYTYCZNE)
Problem: musicvid.py linie 534-551 nadpisuje wynik align_lyrics()
Napraw: usuń blok merge_whisper_with_lyrics_file z musicvid.py
Zostaw tylko: jeśli cache istnieje → wczytaj, jeśli nie → align_lyrics
już wywołane w audio_analyzer.py przez lyrics_path parametr

### 1B — Filtrowanie segmentu "Muzyka" (KRYTYCZNE)
Problem: align_lyrics() nie filtruje segmentu "Muzyka" @ 0.0s
Przez to lyrics[0]['start'] = 0.0s zamiast ~30s
Napraw w lyrics_aligner.py funkcja _is_vocal():
  NON_VOCAL = {"muzyka", "music", "instrumental", "muzyk", "intro"}
  Sprawdzaj też: text_clean.startswith("muzy")
  Sprawdzaj: len(text_clean.split()) == 1 i len(text_clean) < 8
  → prawdopodobnie szum/noise, odfiltruj

### 1C — Runway pusty promptText (KRYTYCZNE)
Problem: 400 Bad Request bo motion_prompt jest "" lub None
Napraw w video_animator.py _submit_animation():
  if not motion_prompt or not motion_prompt.strip():
      motion_prompt = "Slow cinematic camera push forward, natural light"
  payload["promptText"] = motion_prompt.strip()[:400]

### 1D — Rolki imread crash (KRYTYCZNE)
Problem: assembler wywołuje imread() na .mp4 plikach
Napraw w assembler.py funkcja load_asset_clip():
  ext = Path(asset_path).suffix.lower()
  if ext == '.mp4':
      clip = VideoFileClip(asset_path)
      if clip.duration < scene_duration:
          clip = clip.loop(duration=scene_duration)
      clip = clip.subclipped(0, scene_duration).without_audio()
  elif ext in ('.jpg', '.jpeg', '.png'):
      clip = ImageClip(asset_path, duration=scene_duration)
      clip = apply_ken_burns(clip, motion)
  Użyj tej funkcji dla rolek zamiast bezpośredniego imread()

### 1E — Smart crop resizuje zamiast cropować
Problem: konwersja 16:9→9:16 rozciąga obraz
Napraw w assembler.py lub smart_crop.py:
  def convert_16_9_to_9_16(clip, target_w=1080, target_h=1920):
      scale = target_h / clip.h  # skaluj do pełnej wysokości
      clip = clip.resized(scale)
      x1 = (clip.w - target_w) // 2  # przytnij boki
      clip = clip.cropped(x1=x1, x2=x1+target_w)
      return clip  # NIE stretch

## PRIORYTET 2 — Inteligentny director (myśli za użytkownika)

### 2A — Limit scen oparty na BPM (nie stały)
W director.py oblicz max_scenes z BPM:
  bar = 4 * (60 / bpm)
  chorus_dur = bar * 2  # 2 takty na refren
  verse_dur = bar * 4   # 4 takty na zwrotkę
  suggested = int(audio_duration / (bar * 3))  # średnio 3 takty
  max_scenes = max(8, min(20, suggested))

Przekaż do promptu Claude:
  "Sugerowana liczba scen: {max_scenes}
   Refren: sceny po {chorus_dur:.1f}s
   Zwrotka: sceny po {verse_dur:.1f}s"

### 2B — Director system prompt — mega jakość wizualna
Zaktualizuj musicvid/prompts/director_system.txt:

SEKCJA 1 — STYL DOKUMENTALNY (zawsze):
"Wszystkie visual_prompt MUSZĄ:
1. Nawiązywać DO KONKRETNEJ LINIJKI tekstu sceny
2. Być opisem FOTOGRAFICZNYM (nie malarskim)
3. Zawierać: 'documentary photography, natural light, authentic'
4. Unikać: magical, mystical, dreamy, fantasy, glowing, ethereal,
   HDR, 8K, perfect lighting, studio lighting, bokeh everywhere

Wzorzec dobrego promptu:
'Person sitting on cliff edge at dawn, back to camera, arms open wide,
vast misty valley below, documentary style, Sony A7III 35mm,
natural golden light, film grain, authentic emotion of surrender'

Wzorzec złego promptu (NIE rób tak):
'Beautiful magical spiritual landscape with divine light rays'"

SEKCJA 2 — VISUAL SOURCE PER SEKCJA:
"Zasady doboru visual_source per sekcja:
intro/outro → TYPE_VIDEO_STOCK (przyroda, spokój)
verse → 50% TYPE_VIDEO_STOCK + 30% TYPE_VIDEO_RUNWAY + 20% TYPE_PHOTO_STOCK
chorus → 60% TYPE_VIDEO_RUNWAY + 40% TYPE_VIDEO_STOCK
bridge → 70% TYPE_VIDEO_RUNWAY (kulminacja, unikalny moment)

TYPE_VIDEO_STOCK search_query: TYLKO przyroda bez ludzi:
  mountain, valley, lake, forest, sky, clouds, sunrise, sunset,
  river, ocean, field, fog, mist, stars, waterfall
  ZAKAZ: people, hands, prayer, worship, church, drinking, alcohol

TYPE_VIDEO_RUNWAY motion_prompt: pełny opis sceny (2-3 zdania):
  Co się dzieje + ruch kamery + nastrój + styl dokumentalny"

SEKCJA 3 — RÓŻNORODNOŚĆ OBOWIĄZKOWA:
"ZAKAZ powtarzania:
- Tego samego visual_source dla 3 kolejnych scen
- Tego samego motion dla 2 kolejnych scen
- queries zawierające: muslim, islamic, mosque, alcohol, beer,
  drinking, casino, cigarette, smoking, buddha, hindu, shrine"

SEKCJA 4 — ANIMATE z głową:
"animate=True tylko gdy:
- Sekcja to chorus lub bridge
- Czas trwania >= 4s
- Poprzednia scena NIE ma animate=True
- Maksymalnie 20% wszystkich scen

motion_prompt dla TYPE_VIDEO_RUNWAY i animate=True:
MUSI być niepustym stringiem minimum 8 słów opisującym
ruch kamery i nastrój sceny"

### 2C — Auto color_grade per mood_energy
W musicvid.py po analyze_audio():
  auto_lut = {
      "contemplative": "worship-warm",
      "worship": "worship-warm",
      "joyful": "natural",
      "powerful": "teal-orange",
  }
  if not user_provided_color_grade:
      color_grade = auto_lut.get(analysis["mood_energy"], "worship-warm")
      click.echo(f"  Auto LUT: {color_grade} (styl: {analysis['mood_energy']})")

## PRIORYTET 3 — Domyślne PRO zachowanie

### 3A — Nowe domyślne wartości CLI
Zmień defaulty w musicvid.py:
  --effects: "minimal" → "full"  (pełne efekty domyślnie)
  --reel-duration: "15" → "30"   (30s rolki)
  --subtitle-style: "fade" → "karaoke"
  --lut-style: "warm" → "warm"   (bez zmian)
  --lut-intensity: 0.85 → 0.90   (lekko mocniej)
  --wow: True domyślnie (już jest)
  --preset: None → "all"         (pełny film + 3 rolki domyślnie)
  --mode: "stock" → "runway"     (Runway mix domyślnie)

### 3B — Skrócona komenda uruchomienia
Po wszystkich zmianach domyślnych minimalna komenda:
  python3 -m musicvid.musicvid piosenka.mp3 --yes
Daje: pełny film YouTube + 3 rolki 30s z worship-warm LUT,
      full effects, karaoke subtitles, Runway mix

### 3C — Content filtering w stock_fetcher i visual_router
Dodaj walidację query przed Pexels:
  BLOCKED = {"muslim", "islamic", "mosque", "hindu", "buddha", "alcohol",
             "beer", "wine", "drinking", "bar", "pub", "cigarette",
             "smoking", "gambling", "casino", "church interior",
             "cathedral", "shrine", "altar", "prayer rug", "hijab"}

  def is_safe_query(query):
      q = query.lower()
      return not any(b in q for b in BLOCKED)

  if not is_safe_query(search_query):
      print(f"WARN: blocked query '{search_query}' — fallback TYPE_VIDEO_RUNWAY")
      return route_runway(scene, idx)

Dodaj do BFL prompt suffix:
  ", no alcohol, no smoking, no gambling, no Catholic imagery,
  no Islamic imagery, no Buddhist imagery, Protestant Christian context,
  no inappropriate content, family friendly, documentary style"

## PRIORYTET 4 — Dynamika i efekty PRO

### 4A — Section grade domyślnie włączony (nie opcjonalny)
W assembler.py dla każdego klipu ZAWSZE:
  section = get_section_for_time(scene_start, analysis["sections"])
  clip = apply_section_grade(clip, section, reactor=reactor)

Nie pytaj o flagę — to powinno być zawsze włączone.

### 4B — Napisy overflow na rolkach (fix)
W assembler.py dla platform in ['reels', 'shorts', 'tiktok']:
  subtitle_width = 880  # wąski dla 9:16
  font_size = min(font_size, 50)  # cap dla rolki
  margin_bottom = 220  # bezpieczna strefa

  Dla długich linii (> 22 znaki) podziel na dwie:
  def wrap_portrait(text, max_chars=22):
      words = text.split()
      lines, cur, cur_len = [], [], 0
      for w in words:
          if cur_len + len(w) + 1 > max_chars and cur:
              lines.append(' '.join(cur))
              cur, cur_len = [w], len(w)
          else:
              cur.append(w)
              cur_len += len(w) + 1
      if cur: lines.append(' '.join(cur))
      return '\n'.join(lines)

### 4C — Przejścia per energia (zamiast stałych)
W assembler.py przy łączeniu klipów:
  energy = reactor.get_energy(scene_end) if reactor else 0.5
  if energy > 0.75:
      transition = "cut"
      transition_duration = 0.0
  elif energy > 0.45:
      transition = "cross_dissolve"
      transition_duration = 0.3
  else:
      transition = "cross_dissolve"
      transition_duration = 0.6

### 4D — Różnorodność Ken Burns
W assembler.py przypisz motion per scena z rotacją:
  MOTIONS = ["slow_zoom_in", "slow_zoom_out", "pan_left",
             "pan_right", "diagonal_drift"]
  Nigdy ten sam motion 2x pod rząd.
  Dla rolki: ["slow_zoom_in", "slow_zoom_out", "pan_up", "pan_down"]

## PRIORYTET 5 — Jakość eksportu

### 5A — Global LUT zawsze przez FFmpeg (nie opcjonalny)
W assembler.py apply_global_lut() zawsze na końcu:
  Gdy lut_style podany: użyj
  Gdy nie: domyślnie "worship-warm"
  Fallback gdy FFmpeg fail: użyj oryginału (nie crashuj)

### 5B — Napisy zawsze widoczne
Gradient overlay dolny dla rolek (zawsze):
  ColorClip size=(1080, 400), color=(0,0,0)
  opacity=0.55, position=('center', 'bottom')
  Dodaj pod napisy ale nad wideo

### 5C — Progress w terminalu
Każdy stage wypisuje % ukończenia:
  [3/4] Generating assets: 12/20 (60%) — scene_007 TYPE_VIDEO_RUNWAY...
Użyj \r do nadpisywania linii (nie spam nowych)

## Komenda testowa po implementacji
cd /Users/s.rzytki/Documents/aiprojects/musicvideo && \
source venv/bin/activate && \
export $(grep -v '^#' .env | xargs) && \
find output/tmp output/pelny output/social -type f -delete 2>/dev/null; \
mkdir -p output/tmp output/pelny output/social && \
python3 -m musicvid.musicvid \
  "/Users/s.rzytki/Documents/piesni-do-teledysku/Tylko w Bogu/Tylko w Bogu (Cover).mp3" \
  --new --yes

## Kolejność implementacji przez loop
1. PRIORYTET 1A — fix podwójny merge (30 min)
2. PRIORYTET 1B — fix filtrowanie "Muzyka" (15 min)
3. PRIORYTET 1C — fix Runway empty prompt (10 min)
4. PRIORYTET 1D — fix imread crash (20 min)
5. PRIORYTET 1E — fix smart crop (20 min)
6. PRIORYTET 2A — BPM-based scene count (30 min)
7. PRIORYTET 2B — director system prompt (45 min)
8. PRIORYTET 2C — auto color_grade (15 min)
9. PRIORYTET 3A — nowe defaulty CLI (10 min)
10. PRIORYTET 3C — content filtering (20 min)
11. PRIORYTET 4A — section grade domyślnie (15 min)
12. PRIORYTET 4B — napisy overflow fix (20 min)
13. PRIORYTET 4C — przejścia per energia (30 min)
14. PRIORYTET 4D — Ken Burns rotacja (20 min)
15. PRIORYTET 5A — global LUT zawsze (15 min)
16. PRIORYTET 5B — gradient overlay (15 min)

## Acceptance Criteria
- python3 -m musicvid.musicvid piosenka.mp3 --yes generuje bez błędów
- lyrics[0]['start'] >= 28.0s dla tej piosenki
- Brak "NoneType imread" przy rolkach
- Runway dostaje niepusty promptText
- Rolki mają prawidłowy crop (nie stretch)
- Wideo ma worship-warm LUT domyślnie
- Brak duplikatów scen Pexels
- Brak treści alkoholowych i nieprotestanckich
- Napisy widoczne na rolkach (nie ucięte)
- Przejścia zsynchronizowane z energią muzyki
- Każde 5 kolejnych scen ma różne motion typy
- python3 -m pytest tests/ -v przechodzi
