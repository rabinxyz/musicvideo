# Idea

# Spec 3: Jakość zdjęć — dokumentalny realizm zamiast cukierkowego AI

## Kontekst i historia problemu

Obecne zdjęcia generowane przez BFL Flux Pro są:
- Zbyt nasycone kolorystycznie (oversaturated)
- Zbyt "magiczne" i bajkowe
- Widać że to AI — brak autentyczności
- Bokeh na wszystkim — niepotrzebne
- Zbyt perfekcyjne oświetlenie — nierealistyczne

Dla pieśni chrześcijańskich protestanckich potrzebujemy:
- Styl dokumentalnej fotografii
- Autentyczne emocje i miejsca
- Naturalne oświetlenie
- Subtelne, nie przesadzone efekty

## Zmiany w director_system.txt (system prompt Claude-reżysera)

### Usuń kompletnie te słowa/frazy z generowanych promptów:
(Claude nie może ich używać w visual_prompt)

Zakazane słowa:
magical, mystical, ethereal, dreamy, fantasy, otherworldly,
glowing, radiant glow, divine light rays, heavenly glow,
surreal, cinematic fantasy, epic, majestic (używaj rzadko),
bokeh everywhere, heavy bokeh, extreme bokeh,
oversaturated, vivid colors, vibrant, ultra sharp,
perfect lighting, studio lighting, professional lighting,
HDR, ultra-realistic (paradoksalnie wygląda nierealnie),
8K, ultra HD, hyper-detailed

### Dodaj obowiązkowy styl fotograficzny do każdego promptu:

Suffix dodawany automatycznie do KAŻDEGO visual_prompt (w image_generator.py):
"Shot on Sony A7III, 35mm f/2.8 lens, natural available light only,
documentary photography style, authentic and unposed,
slight film grain, natural color grading, no heavy filters,
real location feel, photojournalism aesthetic"

### Nowe wzorce dla różnych typów scen:

Dla przyrody:
"[opis sceny], actual landscape photography, no HDR enhancement,
natural colors slightly desaturated, authentic weather conditions,
real sky with natural clouds, shot on location feel"

Dla ludzi (sylwetki, ręce, ogólne):
"[opis], documentary portrait style, authentic human emotion,
natural skin tones, available light, candid feel, no posing,
real worship moment not staged"

Dla abstrakcji duchowej (gdy tekst wymaga):
"[opis], fine art photography, long exposure, minimal post-processing,
subtle and restrained, atmospheric not overwhelming"

### Zmień Visual Bible w visual_bible.py

Nowy master_style (zastąp obecny):
"Documentary worship photography aesthetic. Natural available light,
film grain present, colors slightly desaturated and warm,
authentic unposed moments, Sony A7III 35mm feel,
no artificial enhancements, real and human."

### Nowe przykłady promptów w director_system.txt

Zastąp obecne przykłady tymi (każdy jest wzorcem do naśladowania):

Dla "Tylko w Bogu jest moja dusza":
"Person sitting alone on wooden dock overlooking misty lake at dawn,
back to camera, legs hanging over water, complete stillness,
documentary style, natural morning light, slight mist on water,
Sony A7III 35mm, film grain, authentic solitude and trust"

Dla "Pan jest moim pasterzem":
"Vast open meadow at golden hour, single figure walking in distance,
long grass moving in wind, wide establishing shot, natural colors,
documentary landscape photography, real weather, no filters"

Dla "Nawet przez ciemną dolinę":
"Rocky mountain path at dusk, dramatic but real clouds,
dark foreground with lighter sky, lone figure on path seen from behind,
photojournalism style, available light only, natural shadows"

Dla refrenu/kulminacji:
"Outdoor worship gathering at sunset, people with hands raised,
wide shot showing community, authentic emotion on faces,
documentary photography, warm natural backlight, no staging"

## Zmiany w image_generator.py

### Dodaj negatywny kontekst do każdego promptu (jako część głównego promptu, nie osobny parametr)

W funkcji generate_images() przed wysłaniem do BFL:
Dodaj na końcu full_prompt:
", documentary style, no Catholic imagery, no religious figures,
no rosary, no crucifix, no saints, authentic not staged,
natural light not artificial, film grain not oversaturated"

### Zmień wymiary dla lepszej kompozycji 16:9

Obecne: width=1024, height=768 (4:3 — złe proporcje!)
Zmień na: width=1360, height=768 (bliższe 16:9)

BFL akceptuje te wymiary i dają lepszą kompozycję panoramiczną
która po przycięciu do 1920x1080 wygląda lepiej.

## Zmiany w assembler.py — post-processing

### Dodaj subtelne filmowe przetwarzanie do każdego obrazu

W apply_effects() dla poziomu "minimal" i "full":
Po warm_grade dodaj subtle_film_look():

def subtle_film_look(frame):
  # Lekka desaturacja (bardziej filmowy look)
  # Konwertuj do HSV, zmniejsz S o 8%
  hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV).astype(float)
  hsv[:,:,1] *= 0.92  # -8% saturacji
  hsv = np.clip(hsv, 0, 255).astype(np.uint8)
  result = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)

  # Bardzo subtelny film grain (sigma=4, opacity=0.08)
  noise = np.random.normal(0, 4, frame.shape).astype(np.float32)
  result = np.clip(result.astype(float) + noise * 0.08, 0, 255).astype(np.uint8)

  return result

Używaj tylko gdy --effects minimal lub full.
NIE używaj dla --effects none.

## Testy

test_no_banned_words:
  Sprawdź że visual_prompt nie zawiera żadnego z zakazanych słów
  ["magical", "mystical", "dreamy", "fantasy", "glowing", "ethereal", "HDR", "8K"]

test_documentary_suffix:
  Każdy prompt wysyłany do BFL zawiera "documentary photography style"

test_dimensions:
  BFL request ma width=1360, height=768

test_film_look:
  subtle_film_look() zwraca frame o nieco niższej saturacji

## Acceptance Criteria
- Żaden prompt nie zawiera zakazanych słów
- Każdy prompt kończy się dokumentalnym suffixem
- Wymiary 1360x768 zamiast 1024x768
- Wygenerowane zdjęcia wyglądają jak fotografia dokumentalna
- Subtelny film grain i desaturacja gdy --effects minimal
- python3 -m pytest tests/test_image_generator.py -v przechodzi
