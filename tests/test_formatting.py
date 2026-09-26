"""Formatting + chart-colour regression tests.

The rent-status donut once rendered grey because translated labels were used
for colour lookup. These tests lock the canonical-key contract in place.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from landlord_tracker.i18n import set_language  # noqa: E402
from landlord_tracker.services.formatting import (  # noqa: E402
    format_money,
    format_money_short,
    format_months,
    format_path,
    format_percent,
    set_locale,
)


@pytest.fixture(autouse=True)
def restore_locale():
    yield
    set_locale("en")
    set_language("en")


def test_english_money_style():
    set_locale("en")
    assert format_money(1275, "EUR") == "€1,275.00"
    assert format_money(680.5, "EUR") == "€680.50"
    assert format_money(-412, "EUR") == "-€412.00"
    assert format_money(1234.56, "USD") == "$1,234.56"


def test_portuguese_money_style():
    set_locale("pt")
    assert format_money(1275, "EUR") == "1 275,00 €"
    assert format_money(680.5, "EUR") == "680,50 €"
    assert format_money(1234.56, "USD") == "$1 234,56"


def test_money_short_forms():
    set_locale("en")
    assert format_money_short(168000, "EUR") == "€168k"
    assert format_money_short(12500, "EUR") == "€12.5k"
    assert format_money_short(1500, "EUR") == "€1.5k"
    assert format_money_short(420, "EUR") == "€420"
    set_locale("pt")
    assert format_money_short(168000, "EUR") == "168k €"
    assert format_money_short(12500, "EUR") == "12,5k €"


def test_none_and_percent_and_months():
    set_locale("en")
    assert format_money(None) == "—"
    assert format_percent(None) == "—"
    assert format_percent(0.533) == "53.3%"
    set_locale("pt")
    assert format_percent(0.533) == "53,3%"
    assert format_months(56.0) == "56"
    assert format_months(0.4) == "<1"
    assert format_months(None) == "—"


def test_unknown_currency_falls_back_to_eur_symbol():
    set_locale("en")
    assert format_money(10, "XYZ") == "€10.00"


# --------------------------------------------------------------------------
# chart colour contract
# --------------------------------------------------------------------------
@pytest.fixture(scope="module")
def qapp():
    """A QApplication is mandatory: constructing any QWidget aborts without one."""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


def test_donut_uses_canonical_labels_for_colour_and_translated_text(qapp):
    from landlord_tracker.ui.theme import Theme
    from landlord_tracker.ui.widgets import DonutChart

    theme = Theme("light")
    chart = DonutChart(
        theme,
        labels=["paid", "late"],
        values=[680.0, 400.0],
        use_status_colors=True,
        display_labels=["Pago", "Em atraso"],
    )
    assert chart._color_for(0) == theme.status_color("paid")
    assert chart._color_for(1) == theme.status_color("late")
    assert chart._color_for(0) != chart._color_for(1)
    assert chart._display(0) == "Pago"
    assert chart._display(1) == "Em atraso"
    # and when only canonical labels are supplied, display falls back to them
    plain = DonutChart(theme, labels=["paid"], values=[1.0], use_status_colors=True)
    assert plain._display(0) == "paid"
    assert plain._color_for(0) == theme.status_color("paid")


def test_theme_card_selectors_are_id_only():
    """PySide6 subclasses need id-only selectors or cards render unstyled."""
    import re

    from landlord_tracker.ui.theme import Theme, build_stylesheet

    qss = build_stylesheet(Theme("light"))
    rules = re.sub(r"/\*.*?\*/", "", qss, flags=re.S)
    for selector in ("#Card", "#KpiCard"):
        assert selector in rules
    # a type-qualified selector would silently fail to match the Python subclass
    assert "QFrame#KpiCard" not in rules


# -- path display ---------------------------------------------------------
# The data folder is visible in the status bar and on the settings screen, and
# both are rendered into screenshots that ship in the README and the store
# listings. An absolute path there publishes the user's account name, and the
# screenshot harness used to leak its own /tmp scratch directory.


def test_format_path_collapses_the_home_directory(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert format_path(tmp_path / ".local" / "share" / "landlord-tracker") == (
        "~/.local/share/landlord-tracker"
    )
    assert format_path(tmp_path) == "~"


def test_format_path_leaves_foreign_paths_untouched(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    # Not cosmetic: shortening a path that is *not* under the user's home would
    # print a "~" that does not resolve for them.
    assert format_path("/tmp/landlord-tracker-shots-abc") == "/tmp/landlord-tracker-shots-abc"
    assert format_path(Path("/media/snatner/USB/backup")) == "/media/snatner/USB/backup"


def test_format_path_survives_a_root_home(monkeypatch):
    # HOME=/ would otherwise rewrite every absolute path into "~/..." garbage.
    monkeypatch.setenv("HOME", "/")
    assert format_path("/tmp/x") == "/tmp/x"
    assert format_path("/") == "/"


def test_format_path_does_not_match_a_sibling_directory(monkeypatch, tmp_path):
    """`/home/ana-marie` must not be shortened against a HOME of `/home/ana`."""
    monkeypatch.setenv("HOME", str(tmp_path / "ana"))
    assert format_path(tmp_path / "ana-marie" / "landlord-tracker") == str(
        tmp_path / "ana-marie" / "landlord-tracker"
    )
