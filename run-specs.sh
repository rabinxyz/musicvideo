#!/bin/bash
set -e

PROJECT_DIR="/Users/s.rzytki/Documents/aiprojects/musicvideo"
SPECS_DIR="$PROJECT_DIR/docs/superpowers/specs"
DONE_DIR="$SPECS_DIR/done"

cd "$PROJECT_DIR"
source venv/bin/activate
mkdir -p "$DONE_DIR"

SPECS=($(ls "$SPECS_DIR"/*.md 2>/dev/null | sort))

if [ ${#SPECS[@]} -eq 0 ]; then
  echo "Brak specyfikacji w $SPECS_DIR"
  exit 0
fi

TOTAL=${#SPECS[@]}
CURRENT=0
FAILED=0

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Kolejka: $TOTAL specyfikacji"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

for SPEC_PATH in "${SPECS[@]}"; do
  CURRENT=$((CURRENT + 1))
  SPEC_NAME=$(basename "$SPEC_PATH")

  echo ""
  echo "▶  [$CURRENT/$TOTAL] $SPEC_NAME"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

  if loop run -i "@$SPEC_PATH"; then
    mv "$SPEC_PATH" "$DONE_DIR/$SPEC_NAME"
    echo "✅ [$CURRENT/$TOTAL] Gotowe → przeniesiony do done/"
  else
    echo "❌ [$CURRENT/$TOTAL] Błąd: $SPEC_NAME — zostaje w specs/"
    FAILED=$((FAILED + 1))
  fi
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅ Wykonane: $((TOTAL - FAILED))"
echo "  ❌ Błędy:    $FAILED"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
