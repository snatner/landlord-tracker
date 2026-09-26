"""Entry point: ``python -m landlord_tracker`` or the ``landlord-tracker`` script."""

from __future__ import annotations

import os
import sys


def main() -> int:
    # Qt must know we are a Wayland/X11 desktop app; offscreen is honoured for
    # headless screenshot generation and CI.
    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")

    from .app import run

    return run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
