import logging
import time
from datetime import datetime, timedelta
import polars as pl
import ssl

# --- SELECTIVE BYPASS (SSL & DNS) ---
import socket
import ssl
import logging
import traceback

# DNS Mapping for Bypass (Multi-IP Fallback)
DUKASCOPY_IPS = ["194.8.15.155", "16.62.187.25", "16.62.244.190"]
DNS_BYPASS = {
    "freeserv.dukascopy.com": DUKASCOPY_IPS[0],
    "www.dukascopy.com": DUKASCOPY_IPS[0]
}

import random
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/121.0.0.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1"
]

original_getaddrinfo = socket.getaddrinfo

def patched_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    if host in DNS_BYPASS:
        return original_getaddrinfo(DNS_BYPASS[host], port, family, type, proto, flags)
    return original_getaddrinfo(host, port, family, type, proto, flags)

socket.getaddrinfo = patched_getaddrinfo

# Selective SSL Bypass & Stealth for Requests
try:
    import requests
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    original_request = requests.Session.request
    def patched_request(self, method, url, *args, **kwargs):
        if "dukascopy.com" in url:
            kwargs['verify'] = False
            # Add Random User-Agent for Anti-Banned
            if 'headers' not in kwargs or kwargs['headers'] is None:
                kwargs['headers'] = {}
            kwargs['headers']['User-Agent'] = random.choice(USER_AGENTS)
            kwargs['headers']['Accept-Language'] = "en-US,en;q=0.9"
            
            if 'timeout' not in kwargs:
                kwargs['timeout'] = 15
        return original_request(self, method, url, *args, **kwargs)
    requests.Session.request = patched_request
    
    import requests.api
    original_api_request = requests.api.request
    def patched_api_request(method, url, **kwargs):
        if "dukascopy.com" in url:
            kwargs['verify'] = False
            if 'headers' not in kwargs or kwargs['headers'] is None:
                kwargs['headers'] = {}
            kwargs['headers']['User-Agent'] = random.choice(USER_AGENTS)
            
            if 'timeout' not in kwargs:
                kwargs['timeout'] = 15
        return original_api_request(method, url, **kwargs)
    requests.api.request = patched_api_request
except Exception:
    pass

# Monkey Patch dukascopy_python to be more robust
import dukascopy_python
original_stream = dukascopy_python._stream
original_fetch_internal = dukascopy_python._fetch

def patched_fetch_internal(*args, **kwargs):
    try:
        data = original_fetch_internal(*args, **kwargs)
        logger.info(f"Internal fetch returned {len(data) if data else 0} rows.")
        if isinstance(data, list):
            # Filter out any None rows that Dukascopy might return
            return [row for row in data if row is not None]
        return data
    except Exception as e:
        logging.getLogger(__name__).error(f"Internal fetch error: {e}")
        return []

def patched_stream(*args, **kwargs):
    # This wrapper handles the generator logic safely
    try:
        # We use a manual loop to handle potential issues inside the generator
        gen = original_stream(*args, **kwargs)
        while True:
            try:
                row = next(gen)
                if row is not None:
                    yield row
            except StopIteration:
                break
            except Exception as e:
                logging.getLogger(__name__).error(f"Generator yielded error: {e}")
                break
    except Exception as e:
        logging.getLogger(__name__).error(f"Stream error: {e}", exc_info=True)

dukascopy_python._stream = patched_stream
dukascopy_python._fetch = patched_fetch_internal
# -----------------------------------------------------




# --------------------------------------

import dukascopy_python
# Import konstanta langsung dari modul utama jika memungkinkan, atau gunakan string literal sebagai fallback yang aman
try:
    from dukascopy_python import (
        INTERVAL_HOUR_1,
        INTERVAL_MIN_15,
        OFFER_SIDE_BID
    )
    INTERVAL_MINUTE_15 = INTERVAL_MIN_15
except ImportError:
    # Fallback string literals jika konstanta tidak ditemukan (v4.0.1+ constants)
    INTERVAL_HOUR_1 = "1HOUR"
    INTERVAL_MINUTE_15 = "15MIN"
    OFFER_SIDE_BID = "B"

# Instruments (Dukascopy names often need slash)
INSTRUMENT_FX_MAJORS_EUR_USD = "EUR/USD"
INSTRUMENT_FX_MAJORS_GBP_USD = "GBP/USD"
INSTRUMENT_METALS_XAU_USD = "XAU/USD"

from storage.tidb_store import TiDBStore

logger = logging.getLogger(__name__)

class DukascopyIngestor:
    """
    DukascopyIngestor menggunakan library native dukascopy-python (v4.0.1+).
    Mendukung Python 3.13 dan bypass blokir ISP Indonesia.
    """
    def __init__(self):
        self.db = TiDBStore()
        self.max_retries = 3
        self.retry_delay = 5 

    def fetch_ohlcv(self, instrument, interval=INTERVAL_HOUR_1, days=7):
        """
        Mengambil data OHLCV dari Dukascopy dengan logic retry.
        Jika gagal total, fallback ke yfinance untuk data Forex/Gold.
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        offer_side = OFFER_SIDE_BID

        # 1. Try Dukascopy with IP Bypass
        for attempt in range(self.max_retries):
            try:
                # Rotate IP
                current_ip = DUKASCOPY_IPS[attempt % len(DUKASCOPY_IPS)]
                DNS_BYPASS["freeserv.dukascopy.com"] = current_ip
                DNS_BYPASS["www.dukascopy.com"] = current_ip
                
                logger.info(f"📡 [Dukascopy] Fetching {instrument} via {current_ip} ({days} days)...")
                
                # Disable verification at the context level for this specific fetch if possible
                # But dukascopy-python v4 uses requests internally which we already patched.
                # However, let's add an extra safety layer by temporarily disabling SSL globally
                import ssl
                original_ctx = ssl._create_default_https_context
                ssl._create_default_https_context = ssl._create_unverified_context
                
                try:
                    df_pandas = dukascopy_python.fetch(
                        instrument,
                        interval,
                        offer_side,
                        start_date,
                        end_date
                    )
                finally:
                    ssl._create_default_https_context = original_ctx

                if df_pandas is not None and not df_pandas.empty:
                    # Filter out null rows (Dukascopy JSONP null)
                    df_pandas = df_pandas.dropna()
                    if not df_pandas.empty:
                        df = pl.from_pandas(df_pandas.reset_index())
                        if "timestamp" in df.columns:
                            df = df.with_columns(pl.col("timestamp").cast(pl.Datetime))
                        logger.info(f"✅ [Dukascopy] Success! {len(df)} rows for {instrument}")
                        return df

                logger.warning(f"⚠️ [Dukascopy] Empty data for {instrument} (Attempt {attempt+1})")

            except Exception as e:
                # Detail error for debugging resets
                err_msg = str(e)
                if "10054" in err_msg or "Connection reset" in err_msg:
                    logger.error(f"❌ [Dukascopy] Connection Reset (ISP Block?) for {instrument} at {current_ip}")
                elif "SSL" in err_msg:
                    logger.error(f"❌ [Dukascopy] SSL Error for {instrument} at {current_ip}: {err_msg}")
                else:
                    logger.error(f"❌ [Dukascopy] Error for {instrument}: {e}")
                
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)

        # 2. Fallback to yfinance for Forex/Metal
        logger.info(f"🔄 [Fallback] Fetching {instrument} via yfinance...")
        try:
            import yfinance as yf
            # Map Dukascopy instrument to yfinance ticker
            ticker_map = {
                "EUR/USD": "EURUSD=X",
                "GBP/USD": "GBPUSD=X",
                "XAU/USD": "XAUUSD=X" # Gold Spot (XAUUSD=X is spot gold, better than GC=F)
            }
            ticker = ticker_map.get(instrument, instrument.replace("/", "") + "=X")
            
            # yf.download limits for 1h: max 730 days (2 years)
            # If days > 730 and interval is 1h, we might need to adjust or inform the user
            fetch_interval = "1h" if interval == INTERVAL_HOUR_1 else "15m"
            if days > 700 and fetch_interval in ["1h", "15m"]:
                logger.warning(f"⚠️ [yfinance] Interval {fetch_interval} limited to ~2 years. Fetching max available.")
            
            yf_df = yf.download(ticker, start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'), interval=fetch_interval)
            
            if not yf_df.empty:
                # Format to match our schema
                yf_df = yf_df.reset_index()
                # Clean columns (yf returns multi-index sometimes)
                if isinstance(yf_df.columns, pd.MultiIndex):
                    yf_df.columns = yf_df.columns.get_level_values(0)
                
                yf_df.columns = [str(col).lower() for col in yf_df.columns]
                
                # Ensure correct column mapping
                rename_map = {"datetime": "timestamp", "date": "timestamp", "adj close": "close"}
                yf_df = yf_df.rename(columns=rename_map)
                
                # Filter rows with NaNs in key columns
                yf_df = yf_df.dropna(subset=["timestamp", "open", "high", "low", "close"])
                
                # Keep only needed columns
                cols = ["timestamp", "open", "high", "low", "close", "volume"]
                available_cols = [c for c in cols if c in yf_df.columns]
                yf_df = yf_df[available_cols]
                
                if "volume" not in yf_df.columns:
                    yf_df["volume"] = 0
                
                logger.info(f"✅ [yfinance] Success! {len(yf_df)} rows for {instrument}")
                return pl.from_pandas(yf_df)
            else:
                logger.error(f"❌ [Fallback] yfinance returned empty data for {ticker}")
        except Exception as ye:
            logger.error(f"❌ [Fallback] yfinance failed: {ye}")
            traceback.print_exc()

        return None

        return None

    def run(self, days=3):
        """
        Main loop untuk sinkronisasi Forex (EUR/USD, GBP/USD) dan Metal (XAU/USD).
        """
        logger.info(f"Memulai sinkronisasi Forex/Metal (Days: {days})...")
        assets = [
            {"name": "EUR/USD", "inst": INSTRUMENT_FX_MAJORS_EUR_USD},
            {"name": "GBP/USD", "inst": INSTRUMENT_FX_MAJORS_GBP_USD},
            {"name": "XAU/USD", "inst": INSTRUMENT_METALS_XAU_USD}
        ]

        success_count = 0
        for asset in assets:
            logger.info(f"Processing {asset['name']}...")
            # Ambil H1 OHLCV
            df = self.fetch_ohlcv(asset["inst"], interval=INTERVAL_HOUR_1, days=days)
            
            if df is not None:
                self.db.save_ohlcv('forex', asset["name"], df.to_pandas())
                success_count += 1
            
            # Ambil M15 untuk analisis lebih detail
            df_m15 = self.fetch_ohlcv(asset["inst"], interval=INTERVAL_MINUTE_15, days=days)
            if df_m15 is not None:
                self.db.save_ohlcv('forex', asset["name"], df_m15.to_pandas())
        
        logger.info(f"Sinkronisasi selesai. Berhasil memuat {success_count}/{len(assets)} aset.")

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    ingestor = DukascopyIngestor()
    ingestor.run(days=7)
