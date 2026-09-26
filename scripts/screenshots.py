#!/usr/bin/env python3
"""Render real screenshots of the app using Qt's offscreen platform.

Used for review on machines without a display (and for the Flathub listing).
Every image is produced by the actual application code — nothing is mocked.

Usage:
    QT_QPA_PLATFORM=offscreen python scripts/screenshots.py [outdir]
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtWidgets import QApplication  # noqa: E402

from landlord_tracker.context import AppContext  # noqa: E402
from landlord_tracker.db import Database  # noqa: E402
from landlord_tracker.i18n import set_language  # noqa: E402
from landlord_tracker.services.demo import load_demo  # noqa: E402
from landlord_tracker.ui.main_window import MainWindow  # noqa: E402

SHOTS = [
    ("dashboard", "dashboard"),
    ("properties", "properties"),
    ("tenants", "tenants"),
    ("leases", "leases"),
    ("rent", "rent"),
    ("expenses", "expenses"),
    ("recurring", "recurring"),
    ("renovations", "renovations"),
    ("documents", "documents"),
    ("feedback", "feature-request"),
    ("settings", "settings"),
]


def render(outdir: Path, data_dir: Path, width: int = 1500, height: int = 960) -> list[Path]:
    data_dir.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])

    ctx = AppContext(data_dir=data_dir)
    if ctx.db.is_empty():
        load_demo(ctx.db)
    set_language(ctx.language)

    window = MainWindow(ctx)
    # Apply the theme exactly like app.build_app() does. Without this the
    # offscreen render shows default-Qt grey and any pixel review is meaningless.
    app.setStyleSheet(ctx.stylesheet())
    window.setStyleSheet(ctx.stylesheet())
    window.resize(width, height)
    window.show()
    app.processEvents()

    outdir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for key, name in SHOTS:
        window.switch_to(key)
        for _ in range(3):
            app.processEvents()
        target = outdir / f"{name}.png"
        window.grab().save(str(target), "PNG")
        written.append(target)
        print(f"  {target}  ({target.stat().st_size // 1024} KB)")

    window.close()
    ctx.close()
    return written


def main() -> int:
    outdir = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "artifacts" / "screenshots"
    # Fresh directory per run. A reused one keeps the old database, `is_empty()`
    # is then false, load_demo() never runs again, and every screenshot silently
    # shows stale data after the seed set changes.
    #
    # We also point HOME at the scratch directory. The status bar and the
    # settings screen render the data folder through format_path(), which
    # collapses the home prefix to "~" — so the shipped screenshots read
    # "~/.local/share/landlord-tracker", which is what a real user sees, instead
    # of advertising this script's temp path on a store listing.
    home = Path(tempfile.mkdtemp(prefix="landlord-tracker-shots-"))
    os.environ["HOME"] = str(home)
    data_dir = Path(os.environ.get("SHOT_DATA_DIR") or home / ".local" / "share" / "landlord-tracker")
    print(f"Rendering screenshots into {outdir}")
    written = render(outdir, data_dir)
    print(f"Done: {len(written)} screenshots")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
