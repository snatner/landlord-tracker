"""Display formatting helpers.

Currency symbol placement and decimal/thousand separators follow the active
language, because Portuguese landlords read ``1 234,50 €`` while English readers
expect ``€1,234.50``.
"""

from __future__ import annotations

from typing import Optional

# currency -> symbol
CURRENCIES = {
    "EUR": "€",
    "USD": "$",
    "GBP": "£",
    "BRL": "R$",
    "CHF": "CHF",
}

# (currency, language) -> (symbol position, decimal sep, thousand sep, space before symbol)
# Placement follows the currency's own convention; the separators follow the
# language, so a Portuguese landlord sees 1 275,00 € and an English reader sees
# €1,275.00 for the same amount.
STYLES = {
    ("EUR", "en"): ("before", ".", ",", False),
    ("EUR", "pt"): ("after", ",", " ", True),
    ("USD", "en"): ("before", ".", ",", False),
    ("USD", "pt"): ("before", ",", " ", True),
    ("GBP", "en"): ("before", ".", ",", False),
    ("GBP", "pt"): ("before", ",", " ", True),
    ("BRL", "en"): ("before", ".", ",", True),
    ("BRL", "pt"): ("before", ",", ".", True),
    ("CHF", "en"): ("before", ".", "'", True),
    ("CHF", "pt"): ("after", ",", " ", True),
}
FALLBACK_STYLE = ("before", ".", ",", False)

_locale = "en"


def set_locale(language: str) -> None:
    """Set the display locale used by every formatter (called on app start)."""
    global _locale
    language = (language or "en").lower()
    _locale = "pt" if language.startswith("pt") else "en"


def current_locale() -> str:
    return _locale


def _style(currency: str = "EUR") -> tuple[str, str, str, bool]:
    return STYLES.get((currency, _locale)) or STYLES.get(("EUR", _locale)) or FALLBACK_STYLE


def _group(number: str, currency: str = "EUR") -> str:
    """Apply the locale's decimal and thousand separators to an f-string number."""
    _, dec, thou, _ = _style(currency)
    return number.replace(",", "\u0000").replace(".", dec).replace("\u0000", thou)


def _wrap(number: str, currency: str, negative: bool) -> str:
    position, _, _, space = _style(currency)
    symbol = CURRENCIES.get(currency, CURRENCIES["EUR"])
    gap = " " if space else ""
    text = f"{symbol}{number}" if position == "before" else f"{number}{gap}{symbol}"
    return f"-{text}" if negative else text


def format_money(value: Optional[float], currency: str = "EUR", decimals: int = 2) -> str:
    if value is None:
        return "—"
    negative = float(value) < 0
    number = _group(f"{abs(float(value)):,.{decimals}f}", currency)
    return _wrap(number, currency, negative)


def format_money_short(value: Optional[float], currency: str = "EUR") -> str:
    """Compact form for tight dashboard cards (168k €, €1.5k)."""
    if value is None:
        return "—"
    amount = abs(float(value))
    if amount >= 1_000_000:
        number = f"{amount / 1_000_000:.1f}M".replace(".0M", "M")
    elif amount >= 1_000:
        number = f"{amount / 1000:.1f}k".replace(".0k", "k")
    else:
        return format_money(value, currency, decimals=0)
    return _wrap(_group(number, currency), currency, float(value) < 0)


def format_percent(value: Optional[float], decimals: int = 1) -> str:
    if value is None:
        return "—"
    return _group(f"{value * 100:.{decimals}f}") + "%"


def format_number(value: Optional[float], decimals: int = 1) -> str:
    if value is None:
        return "—"
    return _group(f"{value:,.{decimals}f}")


def format_months(value: Optional[float]) -> str:
    if value is None:
        return "—"
    if value < 1:
        return "<1"
    return f"{value:.0f}"


def format_count(value: Optional[float]) -> str:
    if value is None:
        return "—"
    return f"{int(value)}"


def format_kpi(value: Optional[float], kind: str, currency: str = "EUR") -> str:
    if kind == "money":
        return format_money_short(value, currency)
    if kind == "percent":
        return format_percent(value)
    if kind == "months":
        return format_months(value)
    return format_count(value)
