"""Shared application context passed to every view.

Holds the database handle, the user's local settings and the active theme.
Views never reach for globals, which keeps them testable and keeps the
"data stays local" story obvious: one context, one local database file.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .db import Database, default_data_dir
from .i18n import detect_system_language, set_language, tr
from .services.formatting import set_locale as set_formatting_locale
from .ui.theme import Theme, build_stylesheet

APP_VERSION = "0.1.13"

# Reverse-DNS application id. This is a ONE-WAY DOOR once published: Flathub and
# the Snap Store treat it as the permanent identity of the app. It has to be
# identical in four places — the installed .desktop basename, StartupWMClass,
# setDesktopFileName() and the AppStream <id>. tests/test_desktop_integration.py
# pins them together so they cannot drift.
APP_ID = "io.github.snatner.LandlordTracker"

# Support / feedback destinations live in one place so they are trivial to
# change at release time.
#
# FEATURE_EMAIL is REAL (set 2026-09-26): a dedicated Posteo alias created for
# this app. It is published in the app UI, the README and the store listings, so
# it will be scraped — never point it at a personal mailbox. Posteo aliases are
# deletable and a deleted address stays blocked for 6 years, but post to a
# deleted alias BOUNCES and shipped copies cannot be recalled, so keep this
# address rather than rotating it.
#
# Ko-fi and Buy Me a Coffee slugs are now IDENTICAL in the README and the UI;
# tests/test_release_metadata.py pins them together so they cannot drift apart
# again. They once disagreed: the README's bullet used the /landlordtracker slug
# while the app button opened /snatner1337 — two different pages, and the README
# labelled its link with the other service's name.
# The Ko-fi slug itself is still UNCONFIRMED LIVE: ko-fi.com answers Cloudflare
# 403 to every fetch tried (datacenter and residential), so it could not be
# verified over HTTP. Open the page in a browser once, then delete this note.
# Buy Me a Coffee resolves 200 and is live.
#
# Crypto addresses are real public receive addresses; private keys are stored
# only on llm-box, not in the app repository/package. Do not include placeholder
# chains here: the Crypto button copies this exact text to the user's clipboard.
KOFI_URL = "https://ko-fi.com/snatner1337"
BUYMEACOFFEE_URL = "https://buymeacoffee.com/snatner"
CRYPTO_DONATION_TEXT = """Landlord Tracker crypto donations

USDC on Base: 0x5e22326c91Ad8bf751c4c4CAdE26d3eb5F947898
Litecoin: ltc1qmpwgk4uqxgteypf644r43c6estk7wx4n5hvacx
Bitcoin: bc1qwz8k0tss6649fpgjhhgc29tjsaxzzq0sqfkw0y
"""
DONATION_URL = KOFI_URL
FEATURE_EMAIL = "landlordtracker@posteo.us"
GITHUB_ISSUES_URL = "https://github.com/snatner/landlord-tracker/issues/new"
GITHUB_REPO_URL = "https://github.com/snatner/landlord-tracker"

DEFAULT_SETTINGS = {
    "language": "",            # "" -> follow system on first run
    "currency": "EUR",
    "theme": "light",
    "dashboard_months": "12",
    "privacy_ack": "0",
    "demo_data": "0",
    "last_backup": "",
}


class AppContext:
    def __init__(self, data_dir: Optional[Path] = None, db: Optional[Database] = None):
        self.db = db or Database(data_dir=data_dir or default_data_dir())
        self._load_settings()
        language = self.db.get_setting("language") or detect_system_language()
        set_language(language)
        set_formatting_locale(language)
        self.theme = Theme(self.db.get_setting("theme") or "light")

    # -- settings -------------------------------------------------------
    def _load_settings(self) -> None:
        for key, value in DEFAULT_SETTINGS.items():
            if self.db.get_setting(key) is None:
                self.db.set_setting(key, value)

    def setting(self, key: str, default: str = "") -> str:
        return self.db.get_setting(key, default) or default

    def set_setting(self, key: str, value: str) -> None:
        self.db.set_setting(key, value)

    @property
    def currency(self) -> str:
        return self.setting("currency", "EUR")

    @property
    def language(self) -> str:
        return self.setting("language") or detect_system_language()

    def set_language(self, code: str) -> None:
        self.db.set_setting("language", code)
        set_language(code)
        set_formatting_locale(code)

    def set_theme(self, name: str) -> None:
        name = name if name in ("light", "dark") else "light"
        self.db.set_setting("theme", name)
        self.theme = Theme(name)

    def stylesheet(self) -> str:
        return build_stylesheet(self.theme)

    def t(self, key: str, **kwargs) -> str:
        return tr(key, **kwargs)

    # -- lifecycle ------------------------------------------------------
    def close(self) -> None:
        try:
            self.db.backup_to()
            self.db.prune_backups(20)
        except Exception:  # pragma: no cover - never block shutdown
            pass
        self.db.close()
