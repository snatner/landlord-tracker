"""Lightweight translation layer.

The app ships English + Portuguese (pt-PT) from day one. Translation files are
plain JSON under ``resources/locale/`` so translators can add languages without
touching Python code.

Design notes:
- No network access, ever. Language packs are shipped locally.
- ``tr()`` falls back to English, then to the key itself, so a missing string
  never crashes the UI.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULT_LANGUAGE = "en"
SUPPORTED_LANGUAGES = {"en": "English", "pt": "Português (pt-PT)"}

_LOCALE_DIR = Path(__file__).resolve().parent / "resources" / "locale"

_translations: dict[str, dict[str, str]] = {}
_current_language = DEFAULT_LANGUAGE
_listeners: list = []


def _load_catalogs() -> dict[str, dict[str, str]]:
    catalogs: dict[str, dict[str, str]] = {}
    if _LOCALE_DIR.is_dir():
        for path in sorted(_LOCALE_DIR.glob("*.json")):
            try:
                catalogs[path.stem] = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
    return catalogs


def available_languages() -> dict[str, str]:
    """Return {code: display_name} for languages that actually have a catalog."""
    langs = {"en": SUPPORTED_LANGUAGES["en"]}
    for code in sorted(_translations):
        if code in SUPPORTED_LANGUAGES:
            langs[code] = SUPPORTED_LANGUAGES[code]
        else:  # pragma: no cover - future language packs
            langs[code] = code
    return langs


def detect_system_language() -> str:
    """Best-effort system language detection, no subprocesses."""
    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(var, "")
        if not value or value in {"C", "POSIX"}:
            continue
        code = value.split(".")[0].split("_")[0].split("-")[0].lower()
        if code in _translations:
            return code
    return DEFAULT_LANGUAGE


def set_language(code: str) -> None:
    global _current_language
    code = (code or DEFAULT_LANGUAGE).lower()
    _current_language = code if code in _translations else DEFAULT_LANGUAGE
    for callback in list(_listeners):
        try:
            callback(_current_language)
        except Exception:  # pragma: no cover - listeners must never break the app
            pass


def current_language() -> str:
    return _current_language


def on_language_changed(callback) -> None:
    """Register a callback invoked after :func:`set_language`."""
    if callback not in _listeners:
        _listeners.append(callback)


def tr(key: str, **kwargs) -> str:
    """Translate ``key`` into the active language."""
    text = _translations.get(_current_language, {}).get(key)
    if text is None:
        text = _translations.get(DEFAULT_LANGUAGE, {}).get(key)
    if text is None:
        return kwargs.get("default", key)
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError):
            return text
    return text


def tr_plural(count: int, singular_key: str, plural_key: str, **kwargs) -> str:
    key = singular_key if abs(count) == 1 else plural_key
    return tr(key, count=count, **kwargs)


_translations = _load_catalogs()
