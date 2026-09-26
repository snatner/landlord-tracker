#!/usr/bin/env python3
"""Diagnostic: sample real pixels to verify stylesheet application."""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtWidgets import QApplication  # noqa: E402

from landlord_tracker.context import AppContext  # noqa: E402
from landlord_tracker.ui.main_window import MainWindow  # noqa: E402

app = QApplication([])
ctx = AppContext(data_dir=Path("/tmp/lt-diag"))
win = MainWindow(ctx)
win.resize(1500, 960)
win.show()
app.processEvents()
win.switch_to("dashboard")
for _ in range(3):
    app.processEvents()


def sample(widget, label, points):
    img = widget.grab().toImage()
    out = []
    for name, (x, y) in points:
        x = max(0, min(img.width() - 1, x))
        y = max(0, min(img.height() - 1, y))
        c = img.pixelColor(x, y)
        out.append(f"{name}={c.name()}")
    print(f"{label:16s} size={img.width()}x{img.height()}  " + "  ".join(out))


nav = win.sidebar.buttons[0][1]
print("nav objectName:", nav.objectName(), "geometry:", nav.geometry().getRect())
print("nav styleSheet inherited (window):", bool(win.styleSheet()), len(win.styleSheet()))
sample(nav, "NavButton", [
    ("center", (nav.width() // 2, nav.height() // 2)),
    ("edge", (2, nav.height() // 2)),
])

kpi = win.dashboard._kpi_cards["portfolio_value"]
print("kpi objectName:", kpi.objectName(), "geometry:", kpi.geometry().getRect())
sample(kpi, "KpiCard", [
    ("center", (kpi.width() // 2, kpi.height() - 6)),
    ("top-left-border", (0, 0)),
    ("inner", (4, 4)),
])

print("page bg expected: #F4F6FA · card white: #FFFFFF · border: #E1E8F2")
print("sidebar bg expected: #152C47 · nav checked bg: #1E4C7A")

sample(win, "FullWindow", [
    ("sidebar", (100, 500)),
    ("page-bg", (300, 350)),
])

ctx.close()
