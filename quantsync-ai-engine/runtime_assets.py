"""
runtime_assets.py — Extended Trading Pairs
Tambahan: Forex Majors, Metals, Energy, Indices
"""

from typing import TypedDict


class ForexAsset(TypedDict):
    name: str       # nama display dan key di database
    inst: str       # instrument name untuk Dukascopy / yfinance lookup
    category: str   # 'forex' | 'commodity' | 'index'


# ─── CRYPTO ───────────────────────────────────────────────────────────────────
REQUIRED_CRYPTO_SYMBOLS: list[str] = [
    "BTC/USDT",
    "BTC/USDC",
    "ETH/USDT",
    "ETH/USDC",
    "SOL/USDT",
    "SOL/USDC",
    "BNB/USDT",
    "BNB/USDC",
]

# ─── FOREX MAJORS ─────────────────────────────────────────────────────────────
REQUIRED_FOREX_ASSETS: list[ForexAsset] = [
    {"name": "EUR/USD", "inst": "EUR/USD", "category": "forex"},
    {"name": "GBP/USD", "inst": "GBP/USD", "category": "forex"},
    {"name": "USD/JPY", "inst": "USD/JPY", "category": "forex"},
    {"name": "AUD/USD", "inst": "AUD/USD", "category": "forex"},
    {"name": "USD/CAD", "inst": "USD/CAD", "category": "forex"},
    {"name": "USD/CHF", "inst": "USD/CHF", "category": "forex"},
    {"name": "NZD/USD", "inst": "NZD/USD", "category": "forex"},
    {"name": "EUR/GBP", "inst": "EUR/GBP", "category": "forex"},
    {"name": "EUR/JPY", "inst": "EUR/JPY", "category": "forex"},
    {"name": "GBP/JPY", "inst": "GBP/JPY", "category": "forex"},
]

# ─── METALS ───────────────────────────────────────────────────────────────────
REQUIRED_METALS_ASSETS: list[ForexAsset] = [
    {"name": "XAU/USD", "inst": "XAU/USD", "category": "commodity"},  # Gold
    {"name": "XAG/USD", "inst": "XAG/USD", "category": "commodity"},  # Silver
    {"name": "XPT/USD", "inst": "XPT/USD", "category": "commodity"},  # Platinum
    {"name": "XPD/USD", "inst": "XPD/USD", "category": "commodity"},  # Palladium
]

# ─── ENERGY ───────────────────────────────────────────────────────────────────
REQUIRED_ENERGY_ASSETS: list[ForexAsset] = [
    {"name": "WTI/USD", "inst": "WTI/USD", "category": "commodity"},  # Crude Oil WTI
    {"name": "BRT/USD", "inst": "BRT/USD", "category": "commodity"},  # Brent Crude
    {"name": "NG/USD",  "inst": "NG/USD",  "category": "commodity"},  # Natural Gas
]

# ─── INDICES ──────────────────────────────────────────────────────────────────
REQUIRED_INDEX_ASSETS: list[ForexAsset] = [
    {"name": "US30",   "inst": "US30",   "category": "index"},  # Dow Jones
    {"name": "US500",  "inst": "US500",  "category": "index"},  # S&P 500
    {"name": "NAS100", "inst": "NAS100", "category": "index"},  # Nasdaq 100
    {"name": "GER40",  "inst": "GER40",  "category": "index"},  # DAX 40
    {"name": "JP225",  "inst": "JP225",  "category": "index"},  # Nikkei 225
]

# ─── COMBINED ─────────────────────────────────────────────────────────────────

ALL_NON_CRYPTO_ASSETS: list[ForexAsset] = (
    REQUIRED_FOREX_ASSETS
    + REQUIRED_METALS_ASSETS
    + REQUIRED_ENERGY_ASSETS
    + REQUIRED_INDEX_ASSETS
)

REQUIRED_FOREX_SYMBOLS:  list[str] = [a["name"] for a in REQUIRED_FOREX_ASSETS]
REQUIRED_METALS_SYMBOLS: list[str] = [a["name"] for a in REQUIRED_METALS_ASSETS]
REQUIRED_ENERGY_SYMBOLS: list[str] = [a["name"] for a in REQUIRED_ENERGY_ASSETS]
REQUIRED_INDEX_SYMBOLS:  list[str] = [a["name"] for a in REQUIRED_INDEX_ASSETS]


def get_required_runtime_assets() -> list[str]:
    """Semua asset symbols yang WAJIB ada saat warmup."""
    return (
        REQUIRED_CRYPTO_SYMBOLS
        + REQUIRED_FOREX_SYMBOLS
        + REQUIRED_METALS_SYMBOLS
    )


def get_assets_by_category(category: str) -> list[ForexAsset]:
    return [a for a in ALL_NON_CRYPTO_ASSETS if a["category"] == category]
