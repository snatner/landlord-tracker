"""Release metadata guards.

Every support/contact destination in this app is *published*: it ships in the UI,
the README, the packaging metadata and — after launch — the store listings. A
placeholder value therefore becomes a user-facing dead link, and the version
string is what users quote when they report a bug.

Why this file exists: before it, ``FEATURE_EMAIL`` was
``features@landlordtracker.app`` (a domain the owner does not control), both
GitHub URLs pointed at a non-existent ``landlord-tracker/landlord-tracker`` org
that 404s, and ``pyproject.toml`` declared version 0.1.0 while the app reported
0.1.10. Nothing failed — the drift was found by hand while wiring the real
address in.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QDesktopServices  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402

from landlord_tracker.context import (  # noqa: E402
    APP_VERSION,
    FEATURE_EMAIL,
    GITHUB_ISSUES_URL,
    GITHUB_REPO_URL,
)

ROOT = Path(__file__).resolve().parents[1]
REPO = "github.com/snatner/landlord-tracker"

# Values that were placeholders. Shipped text must never mention them again.
DEAD_MARKERS = ("landlordtracker.app", "github.com/landlord-tracker/")


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture()
def window(qapp, tmp_path: Path):
    from landlord_tracker.context import AppContext
    from landlord_tracker.ui.main_window import MainWindow

    win = MainWindow(AppContext(data_dir=tmp_path))
    win.show()
    qapp.processEvents()
    yield win
    win.close()


# --- the values themselves ------------------------------------------------


def test_feature_email_is_a_deliverable_address():
    assert re.fullmatch(r"[^@\s]+@[^@\s]+\.[A-Za-z]{2,}", FEATURE_EMAIL), FEATURE_EMAIL
    for dead in DEAD_MARKERS:
        assert dead not in FEATURE_EMAIL, f"placeholder domain resurfaced: {dead}"


def test_github_urls_point_at_the_real_repository():
    assert GITHUB_REPO_URL == f"https://{REPO}"
    assert GITHUB_ISSUES_URL == f"https://{REPO}/issues/new"


def test_pyproject_version_matches_the_app_version():
    """Two version strings exist; the user only ever sees the app's one."""
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version = "([^"]+)"', text, re.MULTILINE)
    assert match, "pyproject.toml must declare a version"
    assert match.group(1) == APP_VERSION, (
        f"pyproject says {match.group(1)} but the app reports {APP_VERSION}"
    )


def test_shipped_source_never_mentions_a_dead_placeholder():
    offenders = []
    for path in sorted((ROOT / "src").rglob("*")):
        if not path.is_file() or path.suffix not in {".py", ".json", ".xml", ".desktop"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for dead in DEAD_MARKERS:
            if dead in text:
                offenders.append(f"{path.relative_to(ROOT)}: {dead}")
    assert not offenders, offenders


# --- and they actually reach the user ------------------------------------


def test_feedback_email_button_targets_the_real_address(window, monkeypatch):
    captured: list[str] = []
    monkeypatch.setattr(
        QDesktopServices, "openUrl",
        lambda url: bool(captured.append(url.toString())) or True,
    )

    view = window.feedback
    view.message.setPlainText("Body")  # a blank body raises a modal dialog
    view.send_email()

    assert captured, "send_email() must hand a mailto: URL to the desktop"
    assert captured[0].startswith(f"mailto:{FEATURE_EMAIL}"), captured[0]


def test_feedback_github_button_targets_the_real_repository(window, monkeypatch):
    captured: list[str] = []
    monkeypatch.setattr(
        QDesktopServices, "openUrl",
        lambda url: bool(captured.append(url.toString())) or True,
    )

    view = window.feedback
    view.message.setPlainText("Body")
    view.open_github()

    assert captured, "open_github() must hand an issues URL to the desktop"
    assert captured[0].startswith(GITHUB_ISSUES_URL), captured[0]


def test_settings_page_shows_the_feature_email(window):
    texts = [label.text() for label in window.settings.findChildren(QLabel)]
    assert FEATURE_EMAIL in texts, (
        "the settings page must show the address users should write to"
    )


# Locations the demo fixture is permitted to use. Deliberately a whitelist rather
# than a blacklist: naming the author's real city here would itself publish it,
# and this test file is shipped to a public repository.
DEMO_LOCATIONS = {"Lisboa"}


def test_demo_data_is_geographically_fictional():
    """Demo records get rendered into PUBLIC screenshots.

    The demo portfolio used to be set in the author's real city, so every
    screenshot in the README and the store listings quietly disclosed where he
    lives. This keeps the fixture on demo venues only.
    """
    demo = (ROOT / "src" / "landlord_tracker" / "services" / "demo.py").read_text(
        encoding="utf-8"
    )
    cities = set(re.findall(r'city="([^"]+)"', demo))
    assert cities, "the demo fixture must still create properties"
    assert cities <= DEMO_LOCATIONS, (
        f"demo.py uses locations outside the fictional allow-list: "
        f"{sorted(cities - DEMO_LOCATIONS)}"
    )
