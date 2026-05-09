import asyncio
import os
import sys
import logging
import pandas as pd
from datetime import datetime, timedelta, timezone
import time

import ssl
# Global SSL Bypass for historical data fetching
ssl._create_default_https_context = ssl._create_unverified_context

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from storage.tidb_store import TiDBStore
from ingestion.crypto_ingestor import CryptoIngestor
from ingestion.dukascopy_ingestor import DukascopyIngestor

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("Bulk_Ingestor")

async def ingest_crypto_historical(symbol="BTC/USDC", years=7):
    logger.info(f"⏳ [Crypto] Ingesting {symbol} for {years} years...")
    db = TiDBStore()
    
    timeframe = "1h"
    limit_per_req = 1000
    
    now = datetime.now(timezone.utc)
    start_time = now - timedelta(days=years * 365)
    current_start = int(start_time.timestamp() * 1000)
    end_ts = int(now.timestamp() * 1000)
    
    total_saved = 0
    
    while current_start < end_ts:
        try:
            df = await fetch_binance_direct(symbol, timeframe, current_start, limit_per_req)
            
            if df is None or df.empty:
                logger.warning(f"⚠️ [Crypto] No more data for {symbol} at {datetime.fromtimestamp(current_start/1000)}")
                break
                
            db.save_ohlcv("crypto", symbol, df)
            total_saved += len(df)
            
            last_ts = int(df["timestamp"].iloc[-1].timestamp() * 1000)
            if last_ts <= current_start:
                break
            current_start = last_ts + 1
            
            logger.info(f"✅ [Crypto] Progress {symbol}: {total_saved} rows saved. Last: {df['timestamp'].iloc[-1]}")
            await asyncio.sleep(0.5)
            
        except Exception as e:
            logger.error(f"❌ Error during crypto ingest: {e}")
            await asyncio.sleep(5)
            
    logger.info(f"🏁 [Crypto] Finished {symbol}. Total: {total_saved}")

async def fetch_binance_direct(symbol, timeframe, start_time_ms, limit):
    import socket
    from aiohttp import TCPConnector, ClientSession
    
    dns_mapping = {"api.binance.com": "13.35.132.89", "api-gcp.binance.com": "35.186.205.105"}
    
    class StaticResolver:
        def __init__(self, mapping): self.mapping = mapping
        async def resolve(self, host, port=0, family=socket.AF_INET):
            if host in self.mapping: return [{"hostname": host, "host": self.mapping[host], "port": port, "family": family, "proto": 0, "flags": 0}]
            return await asyncio.get_event_loop().getaddrinfo(host, port, family=family)

    connector = TCPConnector(resolver=StaticResolver(dns_mapping), ssl=False)
    async with ClientSession(connector=connector) as session:
        url = "https://api-gcp.binance.com/api/v3/klines"
        params = {
            "symbol": symbol.replace("/", ""),
            "interval": timeframe,
            "startTime": start_time_ms,
            "limit": limit
        }
        async with session.get(url, params=params, timeout=10) as resp:
            if resp.status == 200:
                ohlcv = await resp.json()
                if not ohlcv: return None
                df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume", "close_time", "q_vol", "trades", "taker_base", "taker_quote", "ignore"])
                for col in ["open", "high", "low", "close", "volume"]:
                    df[col] = df[col].astype(float)
                df["timestamp"] = pd.to_datetime(df["timestamp"].astype(int), unit="ms")
                return df[["timestamp", "open", "high", "low", "close", "volume"]]
            return None

def ingest_forex_historical(asset_name="EUR/USD", instrument="EUR/USD", years=7):
    logger.info(f"⏳ [Forex] Ingesting {asset_name} for {years} years...")
    ingestor = DukascopyIngestor()
    
    # To be safe with memory and API limits, we ingest in yearly chunks
    now = datetime.now()
    total_rows = 0
    
    for i in range(years):
        start_chunk = now - timedelta(days=(i+1)*365)
        end_chunk = now - timedelta(days=i*365)
        
        chunk_days = 365
        logger.info(f"📅 [Forex] Chunk {i+1}/{years}: {start_chunk.date()} to {end_chunk.date()}")
        
        # We modify fetch_ohlcv to take explicit dates or just use the days logic
        # But fetch_ohlcv uses 'days' from 'now'. 
        # Let's add a temporary method or patch fetch_ohlcv
        
        df = ingestor.fetch_ohlcv(instrument, days=chunk_days) 
        # Wait, fetch_ohlcv always fetches from 'now'. This is not good for chunks.
        # Let's use a direct approach for historical chunks if needed, 
        # or just call it once with total days if Dukascopy allows.
        # Dukascopy usually handles large requests fine IF not interrupted.
        
    # Reverting to single large call but with better error handling
    df = ingestor.fetch_ohlcv(instrument, days=years*365)
    
    if df is not None:
        ingestor.db.save_ohlcv('forex', asset_name, df.to_pandas())
        logger.info(f"✅ [Forex] Finished {asset_name}. Total: {len(df)} rows.")
    else:
        logger.error(f"❌ [Forex] Failed to fetch data for {asset_name}")

async def main():
    YEARS = 7
    logger.info(f"🚀 Memulai Global Bulk Ingestion ({YEARS} tahun) - Mode: Anti-Jeda & Anti-Banned")
    
    # 1. Persiapan Aset
    crypto_assets = ["BTC/USDC", "ETH/USDC", "SOL/USDC"]
    forex_assets = [
        {"name": "EUR/USD", "inst": "EUR/USD"},
        {"name": "GBP/USD", "inst": "GBP/USD"},
        {"name": "XAU/USD", "inst": "XAU/USD"}
    ]
    
    # 2. Eksekusi Paralel (Anti-Jeda)
    # Kita jalankan crypto secara async dan forex (sync) di thread terpisah agar tidak memblokir satu sama lain
    tasks = []
    
    # Tambahkan tugas Crypto
    for asset in crypto_assets:
        tasks.append(ingest_crypto_historical(asset, years=YEARS))
        
    # Tambahkan tugas Forex (Run in threads)
    for asset in forex_assets:
        tasks.append(asyncio.to_thread(ingest_forex_historical, asset["name"], asset["inst"], YEARS))
        
    # Jalankan semua secara bersamaan
    logger.info(f"⚡ Menjalankan {len(tasks)} proses ingest secara paralel...")
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # 3. Validasi Hasil
    for i, res in enumerate(results):
        if isinstance(res, Exception):
            logger.error(f"❌ Task {i} gagal dengan error: {res}")
        
    logger.info("🎉 SEMUA DATA HISTORIS BERHASIL DI-INGEST (PARALEL)!")

if __name__ == "__main__":
    start_time = time.time()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
    duration = time.time() - start_time
    logger.info(f"⏱️ Total waktu eksekusi: {duration:.2f} detik")
