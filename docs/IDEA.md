# Idea

# Spec 5: Hybrid visual sourcing — dobór źródła materiału per scena z tekstu

## Kontekst i historia problemu

Obecny pipeline używa TYLKO jednego źródła dla wszystkich scen:
- Tryb "stock": zawsze Pexels wideo (generyczne, niezwiązane z tekstem)
- Tryb "ai": zawsze BFL Flux (drogie, wolne, cukierkowe)

Problemy:
- Sceny nie pasują do tekstu bo źródło jest dobierane bez kontekstu tekstu
- Wszystkie sceny wyglądają tak samo (wszystkie AI lub wszystkie stock)
- Brak autentyczności — Pexels jest generyczny, AI zbyt artystyczne
- Koszt: BFL dla każdej sceny jest zbyt drogi

Rozwiązanie: Claude-reżyser decyduje PER SCENA skąd wziąć materiał
na podstawie tekstu tej konkretnej sceny.

## Cztery typy źródeł

### TYPE_VIDEO_STOCK — Pexels API (wideo, darmowe)
Kiedy używać:
  - Tekst opisuje konkretny element przyrody (góry, woda, las, niebo, pole)
  - Tekst opisuje ludzką aktywność (modlitwa, śpiew, wspólnota, marsz)
  - Tekst opisuje emocję która może być pokazana przez prawdziwych ludzi
  - Scena NIE jest kulminacyjna (nie wymaga unikalności)

Zalety: realistyczne, autentyczne, darmowe, szybkie (5s pobierania)
Wady: nie jest dopasowane do konkretnych słów, może być generyczne

Parametr: search_query (angielski, 3-5 słów)
Przykłady queries:
  "person praying outdoors golden hour"
  "worship hands raised congregation"
  "mountain valley peaceful morning"
  "calm water reflection sky"
  "open field walking alone sunset"

### TYPE_PHOTO_STOCK — Unsplash API (fotografia, darmowe)
Kiedy używać:
  - Tekst opisuje spokojny, kontemplacyjny moment bez ruchu
  - Konkretny przedmiot: otwarta Biblia, prosty krzyż, świeca
  - Krajobraz który ma być kadrowany statycznie (Ken Burns)
  - Scena gdzie fotografia wygląda lepiej niż wideo

Zalety: profesjonalna fotografia dokumentalna, bardziej artystyczna niż Pexels
Wady: statyczne zdjęcie (wymaga Ken Burns dla ruchu)

Parametr: search_query (angielski, 3-5 słów)
Przykłady:
  "open bible wooden table sunlight"
  "empty wooden cross hilltop sky"
  "person reading scripture morning"
  "sunlight through forest trees"

### TYPE_AI — BFL Flux Pro (generowanie AI, ~$0.04/obraz)
Kiedy używać:
  - Tekst opisuje abstrakcję duchową niemożliwą do sfotografowania
  - Metafora teologiczna wymagająca unikalnej wizualizacji
  - Kulminacyjna scena wymagająca idealnego dopasowania do tekstu
  - Stock nie oddałby właściwego znaczenia

Kiedy NIE używać (wybierz stock zamiast):
  - "góry", "niebo", "woda" — są w Pexels
  - "ludzie modlący się" — są w Pexels
  - Scena niekulminacyjna

Zalety: pełna kontrola, unikalne, dopasowane do tekstu
Wady: drogie ($0.04), wolne (30s), czasem cukierkowe

### TYPE_ANIMATED — BFL Flux Pro + Runway Gen-4 (AI foto → wideo, ~$0.54)
Kiedy używać:
  - TYPE_AI ale scena jest absolutnie kulminacyjna i wymaga ruchu
  - Maksymalnie co 4. scena i max 25% wszystkich scen
  - Minimum czas trwania sceny: 6 sekund
  - Sekcja: chorus (pierwszy lub ostatni) lub bridge

Kiedy NIE używać:
  - Outro
  - Sceny < 6s
  - Gdy dwie animowane sceny byłyby obok siebie (patrz Spec 2)

## Nowa struktura scene_plan.json

Każda scena dostaje nowe pola:
{
  "index": 0,
  "section": "verse",
  "start": 12.0,
  "end": 23.4,
  "lyrics_in_scene": [
    "Tylko w Bogu jest moja dusza",
    "w Nim moje zbawienie"
  ],
  "visual_source": "TYPE_VIDEO_STOCK",  // NOWE
  "search_query": "person alone cliff ocean peaceful trust",  // dla STOCK
  "visual_prompt": null,  // null dla STOCK, string dla AI
  "motion_prompt": null,  // null gdy animate=False, string gdy True
  "motion": "slow_zoom_in",
  "transition_to_next": "cross_dissolve",
  "animate": false
}

## Prompt dla Claude-reżysera — wybór źródła

Dodaj do director_system.txt:

"Dla każdej sceny wybierz visual_source według tych zasad:

=== TYPE_VIDEO_STOCK ===
Kiedy: tekst zawiera konkretne elementy możliwe do sfilmowania
Słowa kluczowe w tekście które sugerują STOCK:
  przyroda: góry, dolina, woda, rzeka, morze, las, pole, niebo, chmury,
            drzewa, kamienie, skały, zboże, kwiaty, pustynia, śnieg
  aktywności: modlitwa, śpiew, uwielbianie, chód, marsz, bieg, klęczenie,
              zbieranie, wspólnota, zgromadzenie
  czas: wschód, zachód, poranek, wieczór, noc (gdy jest naturalne wideo)
search_query: konkretne angielskie słowa do Pexels (3-5 słów)
visual_prompt: null (nie generuj AI)

=== TYPE_PHOTO_STOCK ===
Kiedy: tekst opisuje spokojny moment lub konkretny obiekt
Słowa kluczowe: cisza, spokój, czytanie, Biblia, krzyż (prosty),
               samotność, kontemplacja, sen, odpoczynek
search_query: konkretne angielskie słowa do Unsplash (3-5 słów)
visual_prompt: null

=== TYPE_AI ===
Kiedy: tekst opisuje niemożliwe do sfotografowania abstrakcje:
Słowa kluczowe: duch, chwała, wieczność, tron, rzeka życia, światłość
               (jako metafora duchowa), niebiosa (jako pojęcie, nie niebo)
visual_prompt: szczegółowy opis fotograficzny, 3 zdania minimum,
               styl dokumentalny, naturalne światło
search_query: null

=== TYPE_ANIMATED ===
Jak TYPE_AI ale TYLKO dla:
  - Pierwszego refrenu i ostatniego refrenu
  - Bridge
  - Maksymalnie 25% scen (co 4. scena)
visual_prompt: szczegółowy opis
motion_prompt: opis RUCHU KAMERY (3-8 słów)

PRZYKŁADY DOBORU ŹRÓDŁA:

Linijka 'I chociaż chodzę doliną cienia':
  visual_source: TYPE_VIDEO_STOCK
  search_query: 'person walking dark mountain path alone'

Linijka 'Chwała Bogu na wysokościach':
  visual_source: TYPE_AI (nie można sfotografować 'chwały Boga')
  visual_prompt: 'Vast cathedral of light above cloud layer,
  rays piercing through, documentary aerial photography style,
  natural atmosphere, no fantasy elements, real sky phenomenon'

Linijka 'Otwarta Biblia na stole':
  visual_source: TYPE_PHOTO_STOCK
  search_query: 'open bible morning light wooden table'

Linijka 'Refren: Tylko w Bogu!' (kulminacja):
  visual_source: TYPE_ANIMATED
  visual_prompt: '...'
  motion_prompt: 'slow camera rises revealing vast landscape'"

## Implementacja

### Nowy moduł: musicvid/pipeline/visual_router.py

class VisualRouter:

  def __init__(self, cache_dir, provider="flux-pro"):
      self.cache_dir = cache_dir
      self.provider = provider
      self.pexels_key = os.getenv("PEXELS_API_KEY")
      self.unsplash_key = os.getenv("UNSPLASH_ACCESS_KEY")

  def route(self, scene: dict) -> str:
      source = scene.get("visual_source", "TYPE_AI")
      idx = scene["index"]
      duration = scene["end"] - scene["start"]

      if source == "TYPE_VIDEO_STOCK":
          return self._fetch_pexels(scene["search_query"], idx, duration)

      elif source == "TYPE_PHOTO_STOCK":
          return self._fetch_unsplash(scene["search_query"], idx)

      elif source == "TYPE_ANIMATED":
          image_path = self._generate_bfl(scene["visual_prompt"], idx)
          return self._animate_runway(
              image_path,
              scene.get("motion_prompt", "slow camera push forward"),
              duration=min(5, int(duration)),
              output_idx=idx
          )

      else:  # TYPE_AI (default)
          return self._generate_bfl(scene["visual_prompt"], idx)

  def _fetch_pexels(self, query, idx, min_duration):
      # Używaj istniejącego stock_fetcher.fetch_video() ale z query
      from musicvid.pipeline.stock_fetcher import fetch_video_by_query
      output_path = str(Path(self.cache_dir) / f"scene_{idx:03d}.mp4")
      if Path(output_path).exists():
          return output_path
      return fetch_video_by_query(query, min_duration, output_path)

  def _fetch_unsplash(self, query, idx):
      output_path = str(Path(self.cache_dir) / f"scene_{idx:03d}.jpg")
      if Path(output_path).exists():
          return output_path

      if not self.unsplash_key:
          print(f"WARN: Brak UNSPLASH_ACCESS_KEY — fallback do TYPE_AI")
          return None  # caller obsługuje fallback

      resp = requests.get(
          "https://api.unsplash.com/photos/random",
          headers={"Authorization": f"Client-ID {self.unsplash_key}"},
          params={"query": query, "orientation": "landscape", "content_filter": "high"},
          timeout=10
      )
      resp.raise_for_status()
      image_url = resp.json()["urls"]["regular"]
      download_file(image_url, output_path)
      return output_path

  def _generate_bfl(self, prompt, idx):
      from musicvid.pipeline.image_generator import generate_single_image
      output_path = str(Path(self.cache_dir) / f"scene_{idx:03d}.jpg")
      if Path(output_path).exists():
          return output_path
      return generate_single_image(prompt, output_path, self.provider)

  def _animate_runway(self, image_path, motion_prompt, duration, output_idx):
      from musicvid.pipeline.video_animator import animate_image
      output_path = str(Path(self.cache_dir) / f"animated_scene_{output_idx:03d}.mp4")
      if Path(output_path).exists():
          return output_path
      return animate_image(image_path, motion_prompt, duration, output_path)

### Fallback hierarchy

Gdy source=TYPE_VIDEO_STOCK ale Pexels nie zwraca wyników:
  → Próbuj z uproszczonym query (pierwsze 2 słowa)
  → Jeśli nadal brak: fallback do TYPE_PHOTO_STOCK z tym samym query
  → Jeśli Unsplash też nie: fallback do TYPE_AI

Gdy source=TYPE_PHOTO_STOCK ale brak UNSPLASH_ACCESS_KEY:
  → Fallback do TYPE_VIDEO_STOCK z tym samym query
  → Jeśli Pexels też nie: fallback do TYPE_AI

Gdy source=TYPE_ANIMATED ale brak RUNWAY_API_KEY:
  → Fallback do TYPE_AI (obraz bez animacji + Ken Burns)

Loguj każdy fallback:
  print(f"  Fallback: scena {idx} {source} → {fallback_source}")

### Zmiany w stock_fetcher.py

Dodaj nową funkcję fetch_video_by_query(query, min_duration, output_path):
  Używa bezpośrednio podanego query zamiast mapowania styl→keywords.
  Reszta logiki bez zmian.

### Zmiany w musicvid.py

Zastąp obecną pętlę generowania assetów:

  router = VisualRouter(cache_dir=str(cache_dir), provider=provider)
  fetch_manifest = []

  for i, scene in enumerate(scene_plan["scenes"]):
      scene["index"] = i
      click.echo(f"  [{i+1}/{len(scenes)}] {scene['section']}: "
                 f"{scene.get('visual_source', 'TYPE_AI')} — "
                 f"'{scene.get('search_query') or scene.get('visual_prompt','')[:40]}'")

      asset_path = router.route(scene)

      if asset_path is None:
          # Ostateczny fallback — Ken Burns z czarnym tłem
          asset_path = create_placeholder(i, scene["end"]-scene["start"], str(cache_dir))

      fetch_manifest.append({
          "scene_index": i,
          "video_path": asset_path,
          "start": scene["start"],
          "end": scene["end"],
          "source": scene.get("visual_source", "TYPE_AI")
      })

### Nowy plik .env.example

Dodaj:
UNSPLASH_ACCESS_KEY=...  # darmowy klucz z unsplash.com/developers (50 req/h)

## Podsumowanie kosztów dla typowego teledysku (20 scen)

Bez hybrid (tylko AI):
  20 × TYPE_AI × $0.04 = $0.80

Z hybrid (typowy mix 40% stock, 40% photo, 15% AI, 5% animated):
  8 × TYPE_VIDEO_STOCK × $0.00 = $0.00
  8 × TYPE_PHOTO_STOCK × $0.00 = $0.00
  3 × TYPE_AI × $0.04 = $0.12
  1 × TYPE_ANIMATED × $0.54 = $0.54
  Łącznie: $0.66 (tańsze i bardziej zróżnicowane)

## Testy

test_route_video_stock:
  scene["visual_source"] = "TYPE_VIDEO_STOCK"
  Sprawdź że router wywołuje _fetch_pexels z scene["search_query"]

test_route_photo_stock:
  scene["visual_source"] = "TYPE_PHOTO_STOCK"
  Sprawdź że router wywołuje _fetch_unsplash

test_route_ai:
  scene["visual_source"] = "TYPE_AI"
  Sprawdź że router wywołuje _generate_bfl

test_route_animated:
  scene["visual_source"] = "TYPE_ANIMATED"
  Sprawdź że router wywołuje _generate_bfl + _animate_runway

test_fallback_no_pexels_key:
  Brak PEXELS_API_KEY, source=TYPE_VIDEO_STOCK
  Router fallback do TYPE_PHOTO_STOCK lub TYPE_AI, brak błędu

test_fallback_no_unsplash_key:
  Brak UNSPLASH_ACCESS_KEY, source=TYPE_PHOTO_STOCK
  Router fallback do TYPE_VIDEO_STOCK lub TYPE_AI, brak błędu

test_fallback_no_runway_key:
  Brak RUNWAY_API_KEY, source=TYPE_ANIMATED
  Router fallback do TYPE_AI + Ken Burns, brak błędu

test_cache_respected:
  Jeśli plik scene_003.jpg już istnieje w cache:
  Router NIE wywołuje API — zwraca cached ścieżkę

## Acceptance Criteria
- scene_plan.json zawiera visual_source dla każdej sceny
- Sceny z search_query używają Pexels lub Unsplash
- Sceny z visual_prompt używają BFL Flux
- Mix źródeł widoczny w logach: "[1/20] verse: TYPE_VIDEO_STOCK — 'mountain valley'"
- Fallback działa cicho bez crashowania gdy brak klucza API
- Cache działa — drugi run nie pobiera ponownie
- python3 -m pytest tests/test_visual_router.py -v przechodzi
