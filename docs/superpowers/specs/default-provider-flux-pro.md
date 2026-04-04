# Spec: Zmiana domyślnego providera na flux-pro

## Zmiana
W musicvid/musicvid.py zmień domyślną wartość opcji --provider z "flux-dev" na "flux-pro".

## Acceptance Criteria
- python3 -m musicvid.musicvid --help pokazuje domyślnie flux-pro
- Uruchomienie bez --provider używa flux-pro
