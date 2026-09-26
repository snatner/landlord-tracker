#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Landlord Tracker - one-step installer for Linux desktops (Ubuntu/Debian/Fedora).
#
#   ./install.sh
#
# Installs into your home directory only. No root needed unless python3-venv
# is missing, in which case it asks for your password once.
# ---------------------------------------------------------------------------
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$HOME/.local/share/landlord-tracker"
VENV_DIR="$APP_DIR/venv"
APP_SRC="$APP_DIR/app"
BIN_DIR="$HOME/.local/bin"
APPS_DIR="$HOME/.local/share/applications"

say()  { printf '%s\n' "$*"; }
fail() { printf '\n[!] %s\n' "$*" >&2; exit 1; }

say ""
say "  Landlord Tracker - installer"
say "  ----------------------------"
say ""

# --- 1. system prerequisites ------------------------------------------------
command -v python3 >/dev/null 2>&1 || fail "python3 is not installed. Install it with:  sudo apt install python3"

if ! python3 -c 'import venv, ensurepip' >/dev/null 2>&1; then
    say "[1/5] python3-venv is missing - installing it (your password is needed once)..."
    if command -v apt-get >/dev/null 2>&1; then
        sudo apt-get update -qq && sudo apt-get install -y python3-venv python3-pip
    elif command -v dnf >/dev/null 2>&1; then
        sudo dnf install -y python3-pip
    else
        fail "Could not install python3-venv automatically. Install it with your package manager and re-run."
    fi
else
    say "[1/5] python3 and venv found."
fi

PY_OK="$(python3 -c 'import sys; print("yes" if sys.version_info >= (3,10) else "no")')"
[ "$PY_OK" = "yes" ] || fail "Python 3.10 or newer is required (found $(python3 -V))."

# --- 2. copy the application into place -------------------------------------
say "[2/5] Installing application files into $APP_DIR"
mkdir -p "$APP_DIR"
rm -rf "$APP_SRC"
cp -r "$HERE/src" "$APP_SRC"
[ -f "$HERE/app_icon.png" ] && cp -f "$HERE/app_icon.png" "$APP_DIR/app_icon.png"
[ -f "$HERE/LICENSE" ]      && cp -f "$HERE/LICENSE" "$APP_DIR/LICENSE"

# --- 3. private virtual environment with the app's dependencies -------------
say "[3/5] Creating a private Python environment (this takes a minute the first time)"
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install --upgrade pip --quiet
say "      Downloading PySide6 and openpyxl..."
"$VENV_DIR/bin/python" -m pip install --quiet "PySide6>=6.6" "openpyxl>=3.1"

# --- 4. launcher command ----------------------------------------------------
say "[4/5] Creating the launcher command"
mkdir -p "$BIN_DIR"
cat > "$BIN_DIR/landlord-tracker" <<EOF
#!/usr/bin/env bash
export PYTHONPATH="$APP_SRC"
exec "$VENV_DIR/bin/python" -m landlord_tracker "\$@"
EOF
chmod +x "$BIN_DIR/landlord-tracker"

# --- 5. desktop menu entry + AppStream metadata -----------------------------
# The .desktop basename, StartupWMClass and the AppStream <id> ARE the app's
# identity: the desktop environment matches a running window to its menu entry
# by that id. All three must be io.github.snatner.LandlordTracker or GNOME shows
# "python3" and a generic gear in the dock. tests/test_desktop_integration.py
# reads this file and compares it against the app so they cannot drift.
say "[5/5] Adding the application to your menu"
mkdir -p "$APPS_DIR"
# Pre-0.2.0 installs wrote landlord-tracker.desktop. Remove it, or upgrading
# leaves two "Landlord Tracker" entries in the menu.
rm -f "$APPS_DIR/landlord-tracker.desktop"
cat > "$APPS_DIR/io.github.snatner.LandlordTracker.desktop" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=Landlord Tracker
Comment=Offline, private rental property tracker. No cloud, no accounts.
Exec=$BIN_DIR/landlord-tracker
Icon=$APP_DIR/app_icon.png
Terminal=false
Categories=Office;Finance;Calculator;
Keywords=rent;landlord;property;tenant;lease;mortgage;
StartupNotify=true
StartupWMClass=io.github.snatner.LandlordTracker
EOF
chmod +x "$APPS_DIR/io.github.snatner.LandlordTracker.desktop"

# AppStream metadata, so GNOME Software and KDE Discover can show the app and so
# this install describes itself exactly as the Flatpak/snap builds will.
METAINFO_DIR="$HOME/.local/share/metainfo"
METAINFO_NAME="io.github.snatner.LandlordTracker.metainfo.xml"
METAINFO_SRC="$APP_SRC/landlord_tracker/resources/$METAINFO_NAME"
if [ -f "$METAINFO_SRC" ]; then
    mkdir -p "$METAINFO_DIR"
    cp -f "$METAINFO_SRC" "$METAINFO_DIR/$METAINFO_NAME"
fi

command -v update-desktop-database >/dev/null 2>&1 && \
    update-desktop-database "$APPS_DIR" >/dev/null 2>&1 || true

# --- done -------------------------------------------------------------------
say ""
say "  Done. Landlord Tracker is installed."
say ""
say "  Launch it from your application menu, or run:"
say "      landlord-tracker"
say ""
case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *) say "  Note: $BIN_DIR is not on your PATH, so the 'landlord-tracker'"
       say "  command may not work from a terminal. The menu entry still works,"
       say "  or log out and back in to pick up the new PATH."; say "" ;;
esac
say "  Your data stays on this computer:"
say "      $APP_DIR/landlord.db"
say ""
say "  To uninstall:  ./uninstall.sh"
say ""
