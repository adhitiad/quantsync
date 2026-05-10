"""
DukascopyIngestor — Extended yfinance ticker map untuk pairs baru.
Ganti YFINANCE_TICKER_MAP di dukascopy_ingestor.py dengan versi ini.
"""

# ─── YFINANCE TICKER MAP (lengkap) ───────────────────────────────────────────
# Key  : instrument name di runtime_assets (format standar QuantSync)
# Value: ticker simbol yfinance
YFINANCE_TICKER_MAP: dict[str, str] = {
    # ── Forex Majors ──────────────────────────────────────────────────────────
    "EUR/USD": "EURUSD=X",
    "GBP/USD": "GBPUSD=X",
    "USD/JPY": "USDJPY=X",
    "AUD/USD": "AUDUSD=X",
    "USD/CAD": "USDCAD=X",
    "USD/CHF": "USDCHF=X",
    "NZD/USD": "NZDUSD=X",
    # ── Forex Minor / Cross ───────────────────────────────────────────────────
    "EUR/GBP": "EURGBP=X",
    "EUR/JPY": "EURJPY=X",
    "GBP/JPY": "GBPJPY=X",
    "EUR/AUD": "EURAUD=X",
    "AUD/JPY": "AUDJPY=X",
    "EUR/CHF": "EURCHF=X",
    "GBP/CHF": "GBPCHF=X",
    "CAD/JPY": "CADJPY=X",
    "NZD/JPY": "NZDJPY=X",
    # ── Metals ────────────────────────────────────────────────────────────────
    "XAU/USD": "XAUUSD=X",   # Gold Spot
    "XAG/USD": "XAGUSD=X",   # Silver Spot
    "XPT/USD": "PL=F",       # Platinum Futures (yfinance tidak punya spot XPT)
    "XPD/USD": "PA=F",       # Palladium Futures
    # ── Energy ────────────────────────────────────────────────────────────────
    "WTI/USD": "CL=F",       # WTI Crude Oil Futures
    "BRT/USD": "BZ=F",       # Brent Crude Futures
    "NG/USD":  "NG=F",       # Natural Gas Futures
    # ── Indices ───────────────────────────────────────────────────────────────
    "US30":   "^DJI",        # Dow Jones Industrial Average
    "US500":  "^GSPC",       # S&P 500
    "NAS100": "^NDX",        # Nasdaq 100
    "GER40":  "^GDAXI",      # DAX 40
    "JP225":  "^N225",       # Nikkei 225
    "UK100":  "^FTSE",       # FTSE 100
    "FRA40":  "^FCHI",       # CAC 40
}

# ─── DUKASCOPY INSTRUMENT MAP ─────────────────────────────────────────────────
# Beberapa instrumen punya nama berbeda di Dukascopy vs standar kita.
# Jika tidak ada di map ini, kita pakai nama standar langsung.
DUKASCOPY_INSTRUMENT_MAP: dict[str, str] = {
    # Metals (Dukascopy pakai format ini)
    "XAU/USD": "XAU/USD",
    "XAG/USD": "XAG/USD",
    "XPT/USD": "XPT/USD",
    "XPD/USD": "XPD/USD",
    # Energy — Dukascopy support ini
    "WTI/USD": "WTI/USD",
    "BRT/USD": "BRN/USD",   # Dukascopy pakai "BRN" untuk Brent
    "NG/USD":  "NG/USD",
    # Indices — Dukascopy support CFD indices
    "US30":   "US30/USD",
    "US500":  "US500/USD",
    "NAS100": "NAS100/USD",
    "GER40":  "GER40/EUR",
    "JP225":  "JP225/JPY",
}


def get_dukascopy_instrument(name: str) -> str:
    """Resolve instrument name QuantSync → Dukascopy format."""
    return DUKASCOPY_INSTRUMENT_MAP.get(name, name)


def get_yfinance_ticker(name: str) -> str | None:
    """Resolve instrument name QuantSync → yfinance ticker. None jika tidak ada."""
    return YFINANCE_TICKER_MAP.get(name)
