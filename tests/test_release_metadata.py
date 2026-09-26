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

# Invented street addresses — same whitelist reasoning as DEMO_LOCATIONS.
DEMO_ADDRESSES = {
    "Rua das Flores 12",
    "Av. D. Afonso Henriques 45",
    "Travessa do Forno 8",
}


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


# Every vendor/contractor name the demo fixture may use. Frozen on purpose: the
# city test above only catches `city="..."`, and a company name embeds a place
# just as easily — "<trade> <town> Lda" reads like a plausible local business
# while quietly naming somewhere real. Adding a name here is the review
# checkpoint, because it ships in a public screenshot.
DEMO_VENDORS = {
    "Autoridade Tributária",
    "Casa Banho & Cia",
    "Condomínio Afonso",
    "Condomínio Flores",
    "Cozinhas Lisboa",
    "Fidelidade",
    "Hidráulica Rápida",
    "Obras Lisboa Lda",
    "Pintores Lisboa",
}

# Those names hide their location after a preposition, so a bare-city check
# never saw it: only the whole company string did.
PLACE_PREPOSITION = re.compile(r"\b(?:d[aeo]s?|de)\s+([A-ZÀ-Þ][\wÀ-ÿ]+)")


def _demo_names(tmp_path):
    from landlord_tracker.db import Database
    from landlord_tracker.services.demo import load_demo

    db = Database(data_dir=tmp_path)
    load_demo(db)
    names = set()
    for table, column in (
        ("expenses", "vendor"),
        ("renovations", "contractor"),
        ("recurring_expenses", "vendor"),
    ):
        rows = db.query(
            f"SELECT DISTINCT {column} AS name FROM {table} "
            f"WHERE {column} IS NOT NULL AND {column} != ''"
        )
        names |= {row["name"] for row in rows}
    db.close()
    return names


def test_demo_vendors_are_the_reviewed_set(tmp_path):
    """A new vendor name must be approved deliberately, not slipped in.

    Four real-data workbooks were blocked at the leak gate before the first
    push; this is the same gate for the strings that reach the render output.
    """
    found = _demo_names(tmp_path)
    assert found == DEMO_VENDORS, (
        "demo vendors changed — check every new name for a real place, then "
        f"update DEMO_VENDORS. Unexpected: {sorted(found - DEMO_VENDORS)}, "
        f"missing: {sorted(DEMO_VENDORS - found)}"
    )


def test_demo_vendors_hide_no_place_after_a_preposition(tmp_path):
    offenders = set()
    for name in _demo_names(tmp_path):
        for word in PLACE_PREPOSITION.findall(name):
            if word not in DEMO_LOCATIONS:
                offenders.add(f"{name} -> {word}")
    assert not offenders, (
        f"demo vendor names embed locations outside {sorted(DEMO_LOCATIONS)}: "
        f"{sorted(offenders)}"
    )


def test_snapcraft_yaml_tracks_the_app_version():
    """The snap manifest is a THIRD copy of the version string.

    ``pyproject.toml`` drifted for ten releases because nothing ever read it, so
    the same mistake here would publish a store listing that advertises a
    version the app does not report.
    """
    text = (ROOT / "snapcraft.yaml").read_text(encoding="utf-8")
    match = re.search(r'^version:\s*"?([^"\n]+?)"?\s*$', text, re.MULTILINE)
    assert match, "snapcraft.yaml must declare a version"
    assert match.group(1).strip() == APP_VERSION, (
        f"snapcraft.yaml says {match.group(1).strip()} but APP_VERSION is "
        f"{APP_VERSION} — the Snap Store would advertise the wrong version"
    )


def test_snap_bundles_every_runtime_dependency():
    """A dependency added to pyproject but not to the snap fails at runtime.

    The snap does not install from PyPI at run time; it ships the wheels it was
    built with. Forget one and the confined app crashes with an ImportError that
    the tarball install never reproduces.
    """
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    block = re.search(r"^dependencies\s*=\s*\[(.*?)\]", pyproject, re.MULTILINE | re.DOTALL)
    assert block, "could not read the runtime dependency list"
    declared = re.findall(r'"([A-Za-z0-9_.-]+)', block.group(1))
    assert declared, "no runtime dependencies parsed"

    snapcraft = (ROOT / "snapcraft.yaml").read_text(encoding="utf-8")
    # PySide6 is bundled as the Essentials wheel; everything else keeps its name.
    aliases = {"PySide6": "PySide6-Essentials"}
    missing = [d for d in declared if aliases.get(d, d) not in snapcraft]
    assert not missing, (
        f"pyproject requires {missing} but snapcraft.yaml does not bundle them"
    )


def test_demo_addresses_are_the_reviewed_set():
    """Same whitelist reasoning as the city test, one field deeper.

    An address is the most likely way the real portfolio creeps back into the
    fixture, because demo.py is *modelled* on it.
    """
    demo = (ROOT / "src" / "landlord_tracker" / "services" / "demo.py").read_text(
        encoding="utf-8"
    )
    addresses = set(re.findall(r'address="([^"]+)"', demo))
    assert addresses, "the demo fixture must still create properties"
    assert addresses == DEMO_ADDRESSES, (
        "demo addresses changed — confirm the new ones are invented, then update "
        f"DEMO_ADDRESSES. Unexpected: {sorted(addresses - DEMO_ADDRESSES)}, "
        f"missing: {sorted(DEMO_ADDRESSES - addresses)}"
    )


def test_status_bar_does_not_publish_the_home_directory(qapp, tmp_path, monkeypatch):
    """The status bar string ends up in public screenshots.

    Rendered absolute, it disclosed the account name of whoever took the
    screenshot — and the harness's own temp directory, which read as debug
    output on the store listing.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    from landlord_tracker.context import AppContext
    from landlord_tracker.ui.main_window import MainWindow

    data_dir = tmp_path / ".local" / "share" / "landlord-tracker"
    win = MainWindow(AppContext(data_dir=data_dir))
    try:
        win.switch_to("dashboard")
        message = win.status.currentMessage()
        assert "~/.local/share/landlord-tracker" in message, message
        assert str(tmp_path) not in message, message
    finally:
        win.close()


def test_settings_screen_does_not_publish_the_home_directory(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    from landlord_tracker.context import AppContext
    from landlord_tracker.ui.main_window import MainWindow

    data_dir = tmp_path / ".local" / "share" / "landlord-tracker"
    win = MainWindow(AppContext(data_dir=data_dir))
    try:
        text = win.settings.path_label.text()
        assert text == "~/.local/share/landlord-tracker", text
    finally:
        win.close()
