#!/usr/bin/env bash
# Build the distributable release tarball into dist/releases/.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(grep -m1 '^APP_VERSION' "$ROOT/src/landlord_tracker/context.py" | cut -d'"' -f2)"
NAME="landlord-tracker-$VERSION"
STAGE="$(mktemp -d)"
OUT="$ROOT/dist/releases"

echo "Building $NAME"

mkdir -p "$STAGE/$NAME"
cp -r "$ROOT/src" "$STAGE/$NAME/src"
cp "$ROOT/dist/install.sh" "$ROOT/dist/uninstall.sh" "$STAGE/$NAME/"
cp "$ROOT/README.md" "$ROOT/LICENSE" "$STAGE/$NAME/"
[ -f "$ROOT/dist/landlord-tracker-import-template.xlsx" ] && \
    cp "$ROOT/dist/landlord-tracker-import-template.xlsx" "$STAGE/$NAME/"

# Screenshots so the README renders and the Flathub listing can reuse them.
if [ -d "$ROOT/artifacts/screenshots" ]; then
    mkdir -p "$STAGE/$NAME/artifacts/screenshots"
    cp "$ROOT"/artifacts/screenshots/*.png "$STAGE/$NAME/artifacts/screenshots/"
fi

# Rasterise the SVG icon so the desktop entry has a real PNG.
if [ -f "$ROOT/dist/app_icon.png" ]; then
    cp "$ROOT/dist/app_icon.png" "$STAGE/$NAME/"
else
    echo "  ! dist/app_icon.png missing (desktop icon will be absent)"
fi

# Strip caches so the tarball stays small.
find "$STAGE" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true

mkdir -p "$OUT"
tar -czf "$OUT/$NAME.tar.gz" -C "$STAGE" "$NAME"
rm -rf "$STAGE"

echo "  -> $OUT/$NAME.tar.gz  ($(du -h "$OUT/$NAME.tar.gz" | cut -f1))"
