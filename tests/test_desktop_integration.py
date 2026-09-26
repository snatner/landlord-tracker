"""Desktop integration: the window must be associated with its menu entry.

A running Qt window and the installed ``.desktop`` file are two separate files
that the desktop environment has to match up. If they disagree, GNOME cannot
identify the app: the dock shows the interpreter name ("python3") and a generic
icon instead of the app's name and logo. These tests pin both halves so they
cannot drift apart again.
"""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from landlord_tracker.app import build_app  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
APP_ID = "landlord-tracker"


@pytest.fixture(autouse=True)
def isolated_data_dir(monkeypatch):
    """build_app() constructs a real AppContext: keep it off any real install."""
    monkeypatch.setenv("LANDLORD_TRACKER_DATA",
                       tempfile.mkdtemp(prefix="landlord-tracker-desktop-test-"))


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_app_declares_its_desktop_file_id(qapp):
    """Qt must know the desktop file it belongs to."""
    app, window, ctx = build_app([])
    assert app.desktopFileName() == APP_ID
    assert app.applicationName() == "Landlord Tracker"
    assert window.windowIcon().isNull() is False, "the window needs the app logo"
    ctx.close()


def test_window_title_is_the_app_name_not_the_interpreter(qapp):
    app, window, ctx = build_app([])
    title = window.windowTitle()
    assert title.startswith("Landlord Tracker")
    assert "python" not in title.lower()
    ctx.close()


def test_installer_entry_declares_the_same_wm_class():
    """The generated .desktop must name the same id the app announces."""
    installer = (ROOT / "dist" / "install.sh").read_text(encoding="utf-8")
    match = re.search(r"^StartupWMClass=(.+)$", installer, re.MULTILINE)
    assert match, "dist/install.sh must write a StartupWMClass into the .desktop entry"

    app, window, ctx = build_app([])
    assert match.group(1).strip() == app.desktopFileName()
    ctx.close()


def test_installer_entry_points_at_a_real_name_and_icon():
    installer = (ROOT / "dist" / "install.sh").read_text(encoding="utf-8")
    assert re.search(r"^Name=Landlord Tracker$", installer, re.MULTILINE)
    # No .desktop may fall back to naming the interpreter.
    assert "Name=python" not in installer
    assert re.search(r"^Icon=\$APP_DIR/app_icon\.png$", installer, re.MULTILINE)


def test_desktop_file_name_matches_the_entry_basename():
    """``setDesktopFileName`` must equal the basename of the installed .desktop."""
    installer = (ROOT / "dist" / "install.sh").read_text(encoding="utf-8")
    assert f'"$APPS_DIR/{APP_ID}.desktop"' in installer
