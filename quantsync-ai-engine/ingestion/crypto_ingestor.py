import ccxt.async_support as ccxt
import asyncio
import pandas as pd
import polars as pl
import logging
import sys
import os

# --- FIX: Tambahkan root folder ke sys.path ---
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from storage.supabase_store import SupabaseStore

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
# Suppress aiohttp and ccxt session warnings
logging.getLogger("aiohttp.client").setLevel(logging.ERROR)
logging.getLogger("ccxt.base.exchange").setLevel(logging.ERROR)
logger = logging.getLogger(__name__)


class CryptoIngestor:
    """
    CryptoIngestor (Zero-VPN / Enterprise Edition)
    """

    def __init__(self):
        self.db = SupabaseStore()

    async def fetch_ohlcv(self, symbol="BTC/USDT", timeframe="1h", limit=100):
        # List bursa: Tokocrypto (Utama untuk ID) -> Binance (Fallback Global)
        exchanges_to_try = ["tokocrypto", "binance"]
        last_error = None

        # Ambil proxy dari environment
        proxy = os.getenv("HTTP_PROXY") or os.getenv("HTTPS_PROXY") or os.getenv("http_proxy") or os.getenv("https_proxy")

        # --- DNS & ISP BYPASS STRATEGY ---
        # Memetakan hostname ke IP untuk bypass DNS Poisoning ISP Indonesia
        dns_mapping = {
            "www.tokocrypto.com": "13.35.1.89",
            "www.tokocrypto.site": "13.35.1.89",
            "api.tokocrypto.com": "13.35.1.89",
            "cloudme-toko.2meta.app": "18.67.175.116",
            "api.binance.com": "13.35.132.89",
            "api-gcp.binance.com": "35.186.205.105"
        }

        # Zero Hacker Rule: Ambil API Keys dari Supabase
        api_keys = {
            "binance": {
                "key": self.db.get_config("BINANCE_API_KEY"),
                "secret": self.db.get_config("BINANCE_SECRET_KEY")
            },
            "tokocrypto": {
                "key": self.db.get_config("TOKOCRYPTO_API_KEY"),
                "secret": self.db.get_config("TOKOCRYPTO_SECRET_KEY")
            }
        }

        import socket
        from aiohttp import TCPConnector, ClientSession
        
        class StaticResolver:
            def __init__(self, mapping): self.mapping = mapping
            async def resolve(self, host, port=0, family=socket.AF_INET):
                if host in self.mapping:
                    logger.info(f"🎯 [DNS Bypass] {host} -> {self.mapping[host]}")
                    return [{"hostname": host, "host": self.mapping[host], "port": port, "family": family, "proto": 0, "flags": 0}]
                return await asyncio.get_event_loop().getaddrinfo(host, port, family=family)

        # Pre-calculated market data to bypass load_markets() / exchangeInfo
        # This is essential if ISP blocks the large exchangeInfo response
        manual_market = {
            'id': symbol.replace('/', ''),
            'symbol': symbol,
            'base': symbol.split('/')[0],
            'quote': symbol.split('/')[1],
            'precision': {'amount': 8, 'price': 8},
            'limits': {'amount': {'min': 0.00001}, 'price': {'min': 0.01}},
        }

        for exchange_id in exchanges_to_try:
            connector = TCPConnector(resolver=StaticResolver(dns_mapping), ssl=False)
            
            try:
                # 1. ATTEMPT VIA CCXT (With Manual Market Injection)
                try:
                    config = {
                        "enableRateLimit": True,
                        "options": {"defaultType": "spot", "skip_load_markets": True},
                        "timeout": 15000,
                        "connector": connector,
                    }
                    
                    if exchange_id == "binance":
                        target_url = "https://api-gcp.binance.com/api/v3"
                    else:
                        target_url = "https://www.tokocrypto.site/api/v3"
                        config.update({
                            "apiKey": api_keys["tokocrypto"]["key"],
                            "secret": api_keys["tokocrypto"]["secret"],
                        })

                    config["urls"] = {"api": {"public": target_url, "v3": target_url}}
                    
                    exchange = ccxt.binance(config)
                    # Force inject market to skip exchangeInfo
                    exchange.markets = {symbol: manual_market}
                    exchange.symbols = [symbol]
                    
                    logger.info(f"🔄 [Crypto] Mencoba {exchange_id} (CCXT Bypass) via {target_url}...")
                    ohlcv = await asyncio.wait_for(exchange.fetch_ohlcv(symbol, timeframe, limit=limit), timeout=10)
                    
                    if ohlcv:
                        await exchange.close()
                        await connector.close()
                        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
                        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
                        logger.info(f"✅ [Crypto] Sukses memuat {symbol} dari {exchange_id}")
                        return df
                except Exception as e:
                    logger.warning(f"⚠️ [Crypto] CCXT {exchange_id} gagal: {e}. Mencoba direct fetch...")

                # 2. FALLBACK: DIRECT AIOHTTP (Proven to work in test_bypass.py)
                async with ClientSession(connector=connector) as session:
                    params = {
                        "symbol": symbol.replace("/", ""),
                        "interval": timeframe,
                        "limit": limit
                    }
                    
                    # Binance/Tokocrypto V3 klines endpoint
                    url = f"{target_url}/klines"
                    async with session.get(url, params=params, timeout=10) as resp:
                        if resp.status == 200:
                            ohlcv = await resp.json()
                            df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume", "close_time", "q_vol", "trades", "taker_base", "taker_quote", "ignore"])
                            # Convert types
                            for col in ["open", "high", "low", "close", "volume"]:
                                df[col] = df[col].astype(float)
                            df["timestamp"] = pd.to_datetime(df["timestamp"].astype(int), unit="ms")
                            # Keep only standard columns
                            df = df[["timestamp", "open", "high", "low", "close", "volume"]]
                            logger.info(f"✅ [Crypto] Sukses memuat {symbol} dari {exchange_id} (Direct Bypass)")
                            return df
                        else:
                            last_error = f"HTTP {resp.status}: {await resp.text()}"

            except Exception as e:
                last_error = e
                logger.error(f"❌ [Crypto] Error kritis {exchange_id}: {e}")
            finally:
                if not connector.closed:
                    await connector.close()

        logger.error(f"❌ [Crypto] Gagal memproses {symbol}. Error terakhir: {last_error}")
        return None

        logger.error(f"❌ [Crypto] Gagal memproses {symbol} setelah mencoba semua bursa. Error terakhir: {last_error}")
        return None

    async def run(
        self,
        symbols=[
            "BTC/USDT",
            "ETH/USDT",
            "BNB/USDT",
            "SOL/USDT",
            "BTC/USDC",
            "ETH/USDC",
            "SOL/USDC",
            "BNB/USDC",
        ],
    ):
        logger.info(f"🚀 Memulai Pipeline Ingestion untuk {len(symbols)} aset...")

        for symbol in symbols:
            df = await self.fetch_ohlcv(symbol)
            if df is not None:
                self.db.save_ohlcv("crypto", symbol, df)
                logger.info(f"💾 [Storage] Data {symbol} berhasil diamankan ke Supabase.")

            await asyncio.sleep(2)  # Increased delay to be safer

        logger.info("🏁 Pipeline Crypto Ingestion selesai.")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    ingestor = CryptoIngestor()
    try:
        asyncio.run(ingestor.run())
    except KeyboardInterrupt:
        logger.info("⏹️ Eksekusi dihentikan oleh user.")
