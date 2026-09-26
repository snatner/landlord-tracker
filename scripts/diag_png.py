#!/usr/bin/env python3
"""Sample pixels out of a saved screenshot PNG."""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtGui import QImage  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication([])
path = Path(sys.argv[1])
img = QImage(str(path))
print(f"{path.name}: {img.width()}x{img.height()} format={img.format()} depth={img.depth()} alpha={img.hasAlphaChannel()} dpr={img.devicePixelRatio()}")
img = img.convertToFormat(QImage.Format_RGB32)

from collections import Counter  # noqa: E402

left = Counter()
for y in range(0, img.height(), 7):
    for x in range(0, 220, 7):
        left[img.pixelColor(x, y).name()] += 1
print("dominant colours in sidebar column (x<220):")
for colour, count in left.most_common(6):
    print(f"   {colour}  x{count}")

page = Counter()
for y in range(0, img.height(), 7):
    for x in range(260, img.width(), 7):
        page[img.pixelColor(x, y).name()] += 1
print("dominant colours in page area (x>260):")
for colour, count in page.most_common(6):
    print(f"   {colour}  x{count}")

points = {
    "sidebar-left": (8, 500),
    "nav-button-dashboard": (115, 64),
    "page-bg-gap": (300, 350),
    "kpi-area": (300, 130),
    "card-area": (600, 480),
    "statusbar": (700, 952),
}
for name, (x, y) in points.items():
    x = max(0, min(img.width() - 1, x))
    y = max(0, min(img.height() - 1, y))
    print(f"  {name:24s} ({x:4d},{y:3d}) = {img.pixelColor(x, y).name()}")
print("expected: sidebar #152c47 · nav checked #1e4c7a · page bg #f4f6fa · card #ffffff")
