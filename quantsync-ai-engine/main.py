import sys
import os
import time
import datetime
import asyncio

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from scrapers.rss_scraper import RSSScraper
from scrapers.search_engine import SearchEngine
from storage.vector_db import VectorStore
from utils.processor import DataProcessor
from ingestion.crypto_ingestor import CryptoIngestor
from ingestion.dukascopy_ingestor import DukascopyIngestor

async def run_worker():
    print("🚀 AI Engine Worker Started (True Parallel Async Loop)...")
    
    rss = RSSScraper()
    search = SearchEngine()
    db = VectorStore()
    processor = DataProcessor()
    
    crypto = CryptoIngestor()
    forex = DukascopyIngestor()
    
    last_forex_sync = None

    # Asset list
    crypto_symbols = [
        "BTC/USDT", "BTC/USDC",
        "ETH/USDT", "ETH/USDC",
        "SOL/USDT", "SOL/USDC",
        "BNB/USDT", "BNB/USDC"
    ]

    while True:
        try:
            now = datetime.datetime.now()
            print(f"[{now.strftime('%H:%M:%S')}] Memulai siklus penarikan data...")
            
            tasks = []
            
            # 1. Tambahkan Tugas Crypto (Sudah Async)
            tasks.append(crypto.run(symbols=crypto_symbols))
            
            # 2. Tambahkan Tugas Forex (Bungkus Sync ke Thread terpisah agar tidak memblokir Crypto)
            if last_forex_sync is None or (now - last_forex_sync).total_seconds() > 14400:
                print(f"[{now.strftime('%H:%M:%S')}] Menjadwalkan sinkronisasi Forex (Dukascopy/Yahoo)...")
                tasks.append(asyncio.to_thread(forex.run, days=2))
                last_forex_sync = now
                
            # 3. JALANKAN CRYPTO & FOREX SECARA BERSAMAAN (PARALEL)
            await asyncio.gather(*tasks, return_exceptions=True)
            
            # 4. News/Sentiment Scraping (Bungkus Sync ke Thread)
            print(f"[{now.strftime('%H:%M:%S')}] Mengambil data Sentimen Berita...")
            def run_scrapers():
                rss_data = rss.scrape_all()
                search_data = []
                for asset in ["Bitcoin", "Ethereum", "EURUSD", "Gold"]:
                    search_data.extend(search.search_sentiment(asset))
                return rss_data + search_data
                
            total_data = await asyncio.to_thread(run_scrapers)
            
            # 5. Simpan Sentimen ke Vector DB Milvus
            if total_data:
                df = processor.process_scraped_data(total_data)
                vector_records = processor.prepare_for_vector_db(df)
                db.add_documents(vector_records)
            
            print(f"[{now.strftime('%H:%M:%S')}] Siklus selesai. Menunggu 15 menit untuk siklus berikutnya...")
            await asyncio.sleep(900)
            
        except Exception as e:
            print(f"❌ Worker loop error: {e}")
            await asyncio.sleep(60)

def start_worker():
    """Entry point for background threading initiated by server.py"""
    # FIX KRUSIAL: Injeksi kebijakan Asyncio khusus Windows di dalam Thread baru
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    # Buat dan jalankan event loop untuk thread ini
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_worker())

if __name__ == "__main__":
    start_worker()