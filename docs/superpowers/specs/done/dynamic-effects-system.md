# Spec: System dynamicznych efektów dopasowanych do utworu

## Filozofia
Efekty nie są stałe — reagują na energię muzyczną w danym momencie.
Utwór dyktuje co się dzieje wizualnie. Wynik: spójny, profesjonalny teledysk
który "oddycha" razem z muzyką.

## Analiza energii — podstawa wszystkiego

W audio_analyzer.py oblicz energy_curve: wartość energii per klatka:
  rms = librosa.feature.rms(y=y, sr=sr, hop_length=512)[0]
  energy_times = librosa.frames_to_time(np.arange(len(rms)), sr=sr)

Normalizuj 0.0-1.0:
  rms_norm = (rms - rms.min()) / (rms.max() - rms.min())

Zapisz w analysis:
  "energy_curve": [[float(t), float(e)] for t, e in zip(energy_times, rms_norm)]
  "energy_peaks": [...]  # już jest
  "energy_mean": float(np.mean(rms_norm))

Funkcja pomocnicza:
  def get_energy_at(t, energy_curve) -> float:
      Zwraca energię (0.0-1.0) w czasie t przez interpolację liniową.

## Efekty reaktywne na energię

### LUT — nasycenie kolorów zależy od energii

Zamiast stałego LUT dla całości:
Per klatka: saturation = 0.82 + energy * 0.28
  Energia 0.0 (spokój):    saturation = 0.82 (desaturacja, intymność)
  Energia 0.5 (średnia):   saturation = 0.96 (naturalne)
  Energia 1.0 (szczyt):    saturation = 1.10 (żywe, energetyczne)

Kontrast reaguje podobnie:
  contrast = 1.05 + energy * 0.15
  Energia 0.0: contrast = 1.05
  Energia 1.0: contrast = 1.20

Implementacja przez MoviePy image_transform() per klip:
  energy = get_energy_at(clip_start, energy_curve)
  sat = 0.82 + energy * 0.28
  cont = 1.05 + energy * 0.15
  clip = apply_grade(clip, saturation=sat, contrast=cont)

### Zoom punch — siła zależy od energii peak

Przy każdym energy peak (z analysis["energy_peaks"]):
  peak_energy = get_energy_at(peak_time, energy_curve)
  zoom_scale = 1.02 + peak_energy * 0.06  # zakres: 1.02-1.08
  zoom_duration_frames = max(2, int(peak_energy * 5))  # 2-5 klatek

Czyli przy cichym momencie: delikatny zoom 1.02
Przy kulminacji: mocniejszy zoom 1.08
Nigdy więcej niż 1.08 — zawsze subtelnie

### Vignette — intensywność odwrotna do energii

Przy cichych momentach (energia < 0.3): mocny vignette (intymność)
Przy energetycznych (energia > 0.7): słaby vignette (otwartość)
  vignette_strength = 0.7 - energy * 0.5  # zakres: 0.2-0.7

### Light flash — tylko przy energy spikes > 0.85

Flash WYŁĄCZNIE gdy energia skacze o > 0.4 w ciągu 0.5s (energy spike):
  spike = energy_at(t) - energy_at(t - 0.5)
  if spike > 0.4 and energy_at(t) > 0.85:
      apply_flash(opacity=spike * 0.3, fade=0.5)

Maksimum 2 flashe przez cały teledysk (przy największych spike'ach).
Opacity max: 0.3 — ledwo widoczny ale "czujesz" że coś się wydarzyło.

## Przejścia dopasowane do energii

W director.py i assembler.py:
Typ przejścia zależy od energii NA GRANICY między scenami:

  transition_energy = get_energy_at(scene_end, energy_curve)

  if transition_energy > 0.75:
      transition = "cut"           # twarde cięcie na peak energii
  elif transition_energy > 0.45:
      transition = "cross_dissolve" # płynne przy średniej energii
      duration = 0.4
  elif transition_energy > 0.20:
      transition = "fade"          # spokojne fade przy niskiej
      duration = 0.6
  else:
      transition = "cross_dissolve" # bardzo spokojne
      duration = 0.8

Czas przejścia: im wyższa energia tym KRÓTSZE przejście:
  duration = max(0.15, 0.8 - transition_energy * 0.65)

## Tempo cięć dopasowane do BPM i sekcji

Długość sceny zależy od aktualnego tempa:

  bar = 4 * (60 / bpm)  # czas jednego taktu

  section_bars = {
      'intro':   6,    # długie — narastanie
      'verse':   4,    # średnie — budowanie
      'chorus':  2,    # krótkie — energia
      'bridge':  5,    # zmienne — kulminacja
      'outro':   8,    # długie — wyciszenie
  }

  Dla BPM=84: bar=2.86s
    chorus = 2 * 2.86 = 5.7s per scena (szybkie cięcia)
    verse  = 4 * 2.86 = 11.4s per scena (spokojne)

  Dodatkowy mnożnik energii:
    actual_duration = base_duration * (1.0 - energy_mean * 0.3)
    Energetyczny utwór (energy_mean=0.8): sceny 30% krótsze
    Spokojny utwór (energy_mean=0.2): sceny dłuższe

## Ken Burns reaktywny na energię

Prędkość zoom/pan zależy od energii:
  zoom_speed = 0.03 + energy * 0.07  # zakres: 0.03-0.10 per sekunda

  Spokojne (energia 0.2): zoom 1.00→1.03 przez 10s (ledwo widoczny)
  Energetyczne (energia 0.8): zoom 1.00→1.07 przez 10s (wyraźny)

Kierunek ruchu per sekcja:
  intro/outro:   slow_zoom_in (narastanie/wyciszenie)
  verse parzyste: pan_right
  verse nieparzyste: pan_left
  chorus: slow_zoom_in (skupienie)
  bridge: slow_zoom_out (odsłonięcie)

Nigdy dwa razy ten sam kierunek pod rząd.

## Napisy reaktywne

Rozmiar fontu zależy od energii w momencie napisu:
  base_size = 54
  font_size = int(base_size + energy * 12)  # 54-66px
  Chorus przy peak: 66px
  Intro przy ciszy: 54px

Animacja napisu zależy od energii:
  energia > 0.7: scale_pop (wskakuje)
  energia 0.4-0.7: slide_up (wjeżdża)
  energia < 0.4: fade (spokojne pojawienie)

## Rolki — osobny profil energetyczny

Rolki 30s mają skompresowany czas — efekty muszą być mocniejsze:

Przelicz energy_curve na 30s okno klipu.
Zastosuj boost: energy_reel = min(1.0, energy_clip * 1.3)

Specyficzne dla rolek:
  Zoom punch: zakres 1.03-1.09 (mocniejszy niż pełny film)
  Vignette: zawsze słabszy (otwartość dla małego ekranu)
  Blur-bg composite: zawsze włączony
  Gradient overlay dolny: opacity=0.6 (czytelność napisów)
  Przejścia: zawsze krótsze o 40% niż pełny film
  Hook 2s: freeze frame najlepszej klatki + fade in 0.3s

## Implementacja — nowy moduł energy_reactor.py

Klasa EnergyReactor:
  __init__(self, analysis)
    Przechowuje energy_curve, beats, bpm, sections

  get_energy(self, t) -> float
    Interpolowana energia w czasie t

  get_section(self, t) -> str
    Sekcja (intro/verse/chorus/bridge/outro) w czasie t

  get_zoom_scale(self, t) -> float
    Zoom punch scale dla danego momentu

  get_saturation(self, t) -> float
    Nasycenie kolorów dla danego momentu

  get_transition(self, t) -> dict
    {type, duration} dla przejścia w czasie t

  get_font_size(self, t, base=54) -> int
    Rozmiar fontu dla napisu w czasie t

  get_subtitle_animation(self, t) -> str
    Typ animacji napisu dla danego momentu

Użycie w assembler.py:
  reactor = EnergyReactor(analysis)

  for i, scene in enumerate(scenes):
      t = scene['start']
      clip = load_clip(asset_path)
      clip = apply_grade(clip,
          saturation=reactor.get_saturation(t),
          contrast=reactor.get_saturation(t) * 1.1)
      clip = apply_ken_burns(clip, speed=reactor.get_zoom_scale(t))

  for lyric in lyrics:
      font_size = reactor.get_font_size(lyric['start'])
      animation = reactor.get_subtitle_animation(lyric['start'])

## Color grade globalny (FFmpeg) — worship-warm z energią

Globalny LUT worship-warm zostaje ale z lekką adaptacją:
  Spokojne sekcje (intro/outro/verse): lut-intensity=0.80
  Energetyczne sekcje (chorus/bridge): lut-intensity=0.95

Implementacja: dwa osobne FFmpeg passes z xfade między nimi
lub jeden pass z curves interpolowanymi między wartościami.

Prostsze: jeden stały LUT worship-warm intensity=0.85 dla całości
+ per-klip grade przez MoviePy (sekcja korekty per scena).

## Acceptance Criteria
- EnergyReactor dostarcza wartości per czas t
- Saturacja kolorów wyższa przy chorus niż przy verse
- Zoom punch mocniejszy przy energy peaks > 0.8
- Przejścia krótsze przy wysokiej energii
- Napisy większe przy refrenie
- Ken Burns szybszy przy energetycznych sekcjach
- Rolki mają boost energetyczny +30%
- Brak migania (zoom max 1.08, flash max 2x, opacity max 0.3)
- python3 -m pytest tests/test_energy_reactor.py -v przechodzi
