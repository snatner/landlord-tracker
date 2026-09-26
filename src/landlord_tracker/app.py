"""Application bootstrap."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from .context import APP_ID, APP_VERSION, AppContext
from .i18n import tr
from .ui.main_window import MainWindow


def build_app(argv: Optional[list[str]] = None) -> tuple[QApplication, MainWindow, AppContext]:
    """Create the QApplication, context and main window (used by tests too)."""
    app = QApplication.instance() or QApplication(argv or sys.argv)
    app.setApplicationName("Landlord Tracker")
    app.setApplicationDisplayName(tr("app_name"))
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("Landlord Tracker")
    # The desktop environment identifies a running window by this id and matches
    # it to ``<APP_ID>.desktop``. Without it GNOME cannot associate the window
    # with the installed entry, so the dock falls back to the interpreter name
    # ("python3") and a generic icon instead of the app's name and logo.
    # Must stay in sync with StartupWMClass and the .desktop basename in
    # dist/install.sh, and with the AppStream <id>.
    # tests/test_desktop_integration.py pins all of them together.
    app.setDesktopFileName(APP_ID)

    icon_path = Path(__file__).resolve().parent / "resources" / "app_icon.svg"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    ctx = AppContext()
    app.setStyleSheet(ctx.stylesheet())
    window = MainWindow(ctx)
    window.setStyleSheet(ctx.stylesheet())
    app.setProperty("hermes_ctx", ctx)
    return app, window, ctx


def run(argv: Optional[list[str]] = None) -> int:
    app, window, ctx = build_app(argv)
    window.show()
    try:
        return app.exec()
    finally:
        ctx.close()
