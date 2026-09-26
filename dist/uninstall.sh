#!/usr/bin/env bash
# Remove Landlord Tracker from this computer.
# Your data file is kept unless you also pass --purge.
set -euo pipefail

APP_DIR="$HOME/.local/share/landlord-tracker"
BIN_DIR="$HOME/.local/bin"
APPS_DIR="$HOME/.local/share/applications"

PURGE=0
[ "${1:-}" = "--purge" ] && PURGE=1

rm -f  "$BIN_DIR/landlord-tracker"
rm -f  "$APPS_DIR/io.github.snatner.LandlordTracker.desktop"
# Pre-0.2.0 installs used this entry name; remove it too so an upgrade cannot
# leave two "Landlord Tracker" icons in the menu.
rm -f  "$APPS_DIR/landlord-tracker.desktop"
rm -f  "$HOME/.local/share/metainfo/io.github.snatner.LandlordTracker.metainfo.xml"
command -v update-desktop-database >/dev/null 2>&1 && \
    update-desktop-database "$APPS_DIR" >/dev/null 2>&1 || true

if [ "$PURGE" = "1" ]; then
    rm -rf "$APP_DIR"
    echo "Landlord Tracker removed, including your data file."
else
    # Keep the database, document vault and backups so nothing is lost by accident.
    find "$APP_DIR" -mindepth 1 -maxdepth 1 \
        ! -name 'landlord.db' ! -name 'documents' ! -name 'backups' \
        -exec rm -rf {} + 2>/dev/null || true
    echo "Landlord Tracker removed. Your data was kept at:"
    echo "    $APP_DIR/landlord.db"
    echo "Delete it yourself, or re-run with --purge, to remove everything."
fi
