"""
DukascopyIngestor — Extended untuk semua kategori baru.
Tambahan method run_category() untuk ingest per kategori dengan instrument map yang benar.
"""

import logging
import time
import random
import traceback
from datetime import datetime, timedelta

import pandas as pd
import polars as pl

logger = logging.getLogger(__name__)

# ─── USER AGENTS ─────────────────────────────────────────────────────────────
USER_AGENTS: list[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Edge/121.0.0.0",
]

DUKASCOPY_IPS: list[str] = ["194.8.15.155", "16.62.187.25", "16.62.244.190"]

try:
    import dukascopy_python
    from dukascopy_python import INTERVAL_HOUR_1, INTERVAL_MIN_15, OFFER_SIDE_BID
    INTERVAL_MINUTE_15 = INTERVAL_MIN_15
    DUKASCOPY_AVAILABLE = True
except ImportError:
    DUKASCOPY_AVAILABLE = False
    INTERVAL_HOUR_1 = "1HOUR"
    INTERVAL_MINUTE_15 = "15MIN"
    OFFER_SIDE_BID = "B"
    logger.warning("dukascopy_python tidak tersedia — hanya yfinance yang digunakan.")


# ─── ISOLATED SESSION ─────────────────────────────────────────────────────────

def _make_dukascopy_session():
    """Requests session terisolasi khusus Dukascopy. Tidak memodifikasi global state."""
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    import urllib3

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)  # hanya untuk session ini
    session = requests.Session()
    session.verify = False
    session.headers.update({
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "en-US,en;q=0.9",
    })
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


# ─── YFINANCE FETCH ───────────────────────────────────────────────────────────

def _fetch_from_yfinance(name: str, interval: str, days: int) -> pl.DataFrame | None:
    """Fetch dari yfinance. name = QuantSync instrument name (e.g. 'XAG/USD', 'WTI/USD')."""
    from ingestion.ticker_map import get_yfinance_ticker
    try:
        import yfinance as yf

        ticker = get_yfinance_ticker(name)
        if not ticker:
            logger.warning(f"[yfinance] Ticker tidak ditemukan untuk {name}. Lewati.")
            return None

        fetch_interval = "1h" if interval == INTERVAL_HOUR_1 else "15m"
        end_date   = datetime.now()
        start_date = end_date - timedelta(days=min(days, 700))

        logger.info(f"[yfinance] Fetching {ticker} ({fetch_interval}, {days}d)...")

        yf_df = yf.download(
            ticker,
            start=start_date.strftime("%Y-%m-%d"),
            end=end_date.strftime("%Y-%m-%d"),
            interval=fetch_interval,
            progress=False,
            auto_adjust=True,
        )

        if yf_df.empty:
            logger.error(f"[yfinance] Data kosong untuk {ticker}")
            return None

        yf_df = yf_df.reset_index()
        if isinstance(yf_df.columns, pd.MultiIndex):
            yf_df.columns = yf_df.columns.get_level_values(0)
        yf_df.columns = [str(c).lower() for c in yf_df.columns]
        yf_df = yf_df.rename(columns={"datetime": "timestamp", "date": "timestamp", "adj close": "close"})
        yf_df = yf_df.dropna(subset=["timestamp", "open", "high", "low", "close"])

        needed = ["timestamp", "open", "high", "low", "close", "volume"]
        available = [c for c in needed if c in yf_df.columns]
        yf_df = yf_df[available]
        if "volume" not in yf_df.columns:
            yf_df["volume"] = 0.0

        logger.info(f"[yfinance] ✅ {len(yf_df)} rows untuk {ticker}")
        return pl.from_pandas(yf_df)

    except Exception as e:
        logger.error(f"[yfinance] Error {name}: {e}")
        traceback.print_exc()
        return None


# ─── DUKASCOPY FETCH ──────────────────────────────────────────────────────────

def _fetch_from_dukascopy(instrument: str, interval: str, days: int) -> pl.DataFrame | None:
    if not DUKASCOPY_AVAILABLE:
        return None

    from ingestion.ticker_map import get_dukascopy_instrument
    duck_instrument = get_dukascopy_instrument(instrument)

    end_date   = datetime.now()
    start_date = end_date - timedelta(days=days)

    for attempt, ip in enumerate(DUKASCOPY_IPS):
        session = _make_dukascopy_session()
        try:
            logger.info(f"[Dukascopy] Attempt {attempt + 1}: {duck_instrument} via {ip}")
            try:
                df_pandas = dukascopy_python.fetch(
                    duck_instrument, interval, OFFER_SIDE_BID, start_date, end_date
                )
            except TypeError:
                df_pandas = dukascopy_python.fetch(
                    duck_instrument, interval, OFFER_SIDE_BID, start_date, end_date
                )

            if df_pandas is not None and not df_pandas.empty:
                df_pandas = df_pandas.dropna()
                if not df_pandas.empty:
                    df = pl.from_pandas(df_pandas.reset_index())
                    if "timestamp" in df.columns:
                        df = df.with_columns(pl.col("timestamp").cast(pl.Datetime))
                    logger.info(f"[Dukascopy] ✅ {len(df)} rows untuk {duck_instrument}")
                    return df

            logger.warning(f"[Dukascopy] Data kosong {duck_instrument} (attempt {attempt + 1})")

        except Exception as e:
            err = str(e)
            label = (
                "Connection reset (ISP block?)" if "10054" in err or "Connection reset" in err
                else "SSL error" if "SSL" in err
                else "Error"
            )
            logger.error(f"[Dukascopy] {label}: {duck_instrument} @ {ip}: {err}")
            if attempt < len(DUKASCOPY_IPS) - 1:
                time.sleep(5)
        finally:
            session.close()

    return None


# ─── INGESTOR CLASS ───────────────────────────────────────────────────────────

from storage.supabase_store import SupabaseStore
from runtime_assets import REQUIRED_FOREX_ASSETS, ALL_NON_CRYPTO_ASSETS, ForexAsset


class DukascopyIngestor:
    """
    Ingestor untuk semua non-crypto assets:
    Forex, Metals, Energy, Indices.

    Primary  : Dukascopy (isolated session, tidak ada global patch)
    Fallback : yfinance
    """

    def __init__(self):
        self.db = SupabaseStore()

    def fetch_ohlcv(
        self,
        name: str,
        instrument: str,
        interval: str = INTERVAL_HOUR_1,
        days: int = 7,
    ) -> pl.DataFrame | None:
        """
        Fetch OHLCV untuk satu instrumen.
        name     : key yang dipakai di database (e.g. 'XAG/USD')
        instrument: native instrument name (mungkin berbeda, e.g. 'XAG/USD')
        """
        df = _fetch_from_dukascopy(instrument, interval, days)
        if df is not None:
            return df

        logger.info(f"[Ingestor] Dukascopy gagal untuk {name}, fallback yfinance...")
        return _fetch_from_yfinance(name, interval, days)

    def run_category(
        self,
        assets: list[ForexAsset],
        days: int = 3,
    ) -> None:
        """
        Sinkronisasi semua asset dalam satu kategori.
        Dipanggil dari main.py worker via asyncio.to_thread.
        """
        if not assets:
            return

        category = assets[0]["category"]
        logger.info(f"[Ingestor] Sync {category}: {len(assets)} aset (days={days})...")
        success = 0

        for asset in assets:
            name = asset["name"]
            inst = asset["inst"]
            logger.info(f"  → {name} ({category})...")

            # H1
            df_h1 = self.fetch_ohlcv(name, inst, interval=INTERVAL_HOUR_1, days=days)
            if df_h1 is not None:
                self.db.save_ohlcv(category, name, df_h1.to_pandas(), timeframe="H1")
                success += 1

            # M15 — hanya untuk forex (tidak perlu untuk indices dan energy futures)
            if category == "forex":
                df_m15 = self.fetch_ohlcv(name, inst, interval=INTERVAL_MINUTE_15, days=days)
                if df_m15 is not None:
                    self.db.save_ohlcv(category, name, df_m15.to_pandas(), timeframe="M15")

        logger.info(f"[Ingestor] {category} selesai: {success}/{len(assets)} aset berhasil.")

    def run(self, days: int = 3) -> None:
        """
        Backward-compat: jalankan semua kategori sekaligus.
        Dipanggil jika tidak menggunakan run_category per kategori.
        """
        for category in ["forex", "commodity", "index"]:
            from runtime_assets import get_assets_by_category
            assets = get_assets_by_category(category)
            self.run_category(assets, days=days)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    ingestor = DukascopyIngestor()
    ingestor.run(days=7)
