from __future__ import annotations


def normalize_symbol(symbol: str) -> str:
    """Normalize a trading symbol into uppercase dash-separated form."""
    return symbol.replace("/", "-").replace("_", "-").upper()
