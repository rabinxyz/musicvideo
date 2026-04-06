# Spec: Naprawa konfiguracji Whisper — język polski i lepszy model

## Problem
Linia 95 w audio_analyzer.py:
  model.transcribe(audio_path, word_timestamps=True)

Brak parametru language — Whisper auto-wykrywa i myli się na polskim śpiewie.
Efekt: bełkot zamiast polskiego tekstu, lyrics=[] po filtracji.

## Poprawka w audio_analyzer.py

Zmień linię 95:
  model.transcribe(audio_path, word_timestamps=True)

Na:
  model.transcribe(
      audio_path,
      word_timestamps=True,
      language="pl",
      initial_prompt="Polska pieśń chrześcijańska. Słowa: tylko, Bogu, zbawienie, Pan, dusza, serce, chwała.",
      temperature=0.0,
      condition_on_previous_text=True,
  )

Parametry:
- language="pl": wymusza polski — kluczowe
- initial_prompt: podpowiada Whisperowi kontekst (polska pieśń)
  pomaga z rozpoznawaniem słów religijnych i polskich
- temperature=0.0: deterministyczny wynik, mniej halucynacji
- condition_on_previous_text=True: spójność między segmentami

## Zmień model z "base" na "small"

Obecny model "base" jest za słaby dla polskiego śpiewu z muzyką.
Model "small" jest ~4x większy ale znacznie lepiej radzi sobie z polskim.

Zmień:
  model = whisper.load_model("base")
Na:
  model = whisper.load_model("small")

Czas transkrypcji: ~2 minuty zamiast ~30s dla 4-minutowej piosenki.
Jakość: znacznie lepsza dla języków nieangiełskich.

## Filtracja segmentów po transkrypcji

Obecna filtracja usuwa wszystkie segmenty gdy tekst jest bełkotem.
Popraw filtrację żeby była mniej agresywna:

Stara filtracja (zbyt agresywna):
  segments = [s for s in result["segments"] if s["text"].strip()]

Nowa filtracja (zachowaj segment jeśli ma jakiś tekst):
  segments = []
  for s in result["segments"]:
      text = s["text"].strip()
      if not text:
          continue
      if len(text) < 2:
          continue
      # Nie filtruj po zawartości — Whisper z language=pl da poprawny tekst
      segments.append(s)

## Gdy lyrics_path dostępny

Gdy użytkownik podał plik tekstu (--lyrics lub auto-wykryty):
  Nadal uruchamiaj Whisper z powyższą konfiguracją dla timingów
  Ale NIE używaj tekstu z Whisper — użyj tekstu z pliku
  Timing (start/end) bierz z Whisper, tekst z pliku

## Acceptance Criteria
- model.transcribe() zawiera language="pl"
- Model to "small" nie "base"
- initial_prompt zawiera polskie słowa religijne
- lyrics lista nie jest pusta po transkrypcji polskiej pieśni
- Tekst segmentów to polskie słowa (nie bełkot)
- Timing segmentów pokrywa się z rzeczywistym śpiewem w audio
