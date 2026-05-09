import sys
import os
import time
import datetime
import asyncio
import traceback

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from scrapers.rss_scraper import RSSScraper
from scrapers.search_engine import SearchEngine
from storage.vector_db import VectorStore
from utils.processor import DataProcessor
from ingestion.crypto_ingestor import CryptoIngestor
from ingestion.dukascopy_ingestor import DukascopyIngestor
from runtime_assets import REQUIRED_CRYPTO_SYMBOLS, REQUIRED_FOREX_SYMBOLS


async def run_worker():
    print("🚀 [Worker] AI Engine Background Service Started (True Parallel Mode)...")

    rss = RSSScraper()
    search = SearchEngine()
    db = VectorStore()
    processor = DataProcessor()

    crypto = CryptoIngestor()
    forex = DukascopyIngestor()

    last_forex_sync = None

    while True:
        try:
            now = datetime.datetime.now()
            print(f"\n[{now.strftime('%H:%M:%S')}] 🔄 MEMULAI SIKLUS INGESTION DATA...")
            print(
                f"[{now.strftime('%H:%M:%S')}] 📦 Runtime wajib: {len(REQUIRED_CRYPTO_SYMBOLS)} crypto, {len(REQUIRED_FOREX_SYMBOLS)} forex."
            )

            tasks = []

            # 1. JALUR CRYPTO (Native Async)
            # Crypto berjalan langsung di Event Loop utama
            tasks.append(crypto.run(symbols=REQUIRED_CRYPTO_SYMBOLS))

            # 2. JALUR FOREX (Sync to Thread)
            # Sinkronisasi Forex setiap 4 jam (14400 detik) atau saat pertama kali jalan
            if (
                last_forex_sync is None
                or (now - last_forex_sync).total_seconds() > 14400
            ):
                print(
                    f"[{now.strftime('%H:%M:%S')}] 📅 Menjadwalkan sinkronisasi Forex (Dukascopy/Yahoo)..."
                )
                # Melempar proses sinkron yang memblokir ke OS Thread Pool agar tidak mengganggu Crypto
                tasks.append(asyncio.to_thread(forex.run, days=2))
                last_forex_sync = now

            # 3. EKSEKUSI PARALEL (CRYPTO & FOREX BERJALAN BERSAMAAN)
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Evaluasi jika ada Task yang error agar loop tidak mati
            for i, res in enumerate(results):
                if isinstance(res, Exception):
                    print(f"❌ [Worker Error] Task {i} gagal: {res}")

            # 4. JALUR SCRAPING & VECTOR DB (Sync to Thread)
            def run_scrapers_and_save():
                print(
                    f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 📰 Mengambil data Berita & Update Milvus..."
                )
                rss_data = rss.scrape_all()
                search_data = []
                for asset in ["Bitcoin", "Ethereum", "EURUSD", "Gold"]:
                    search_data.extend(search.search_sentiment(asset))

                total_data = rss_data + search_data

                if total_data:
                    df = processor.process_scraped_data(total_data)
                    vector_records = processor.prepare_for_vector_db(df)
                    db.add_documents(vector_records)  # Insert ke Milvus (Zilliz)
                    print(
                        f"[{datetime.datetime.now().strftime('%H:%M:%S')}] ✅ Berhasil menyimpan sentimen ke Vector DB."
                    )

            # Lempar scraping dan Milvus network request ke Thread agar tidak memblokir loop
            await asyncio.to_thread(run_scrapers_and_save)

            print(
                f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 🏁 Siklus Selesai. Menunggu 15 Menit..."
            )
            await asyncio.sleep(900)

        except Exception as e:
            print(f"❌ [CRITICAL] Worker loop error: {e}")
            traceback.print_exc()
            await asyncio.sleep(60)


def start_worker():
    """Entry point for background threading initiated by server.py"""
    # FIX KRUSIAL: Proteksi Event Loop untuk Windows OS (Wajib saat digabungkan dengan gRPC)
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    # Buat Event Loop baru yang terisolasi khusus untuk thread Background Worker ini
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(run_worker())
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()


if __name__ == "__main__":
    start_worker()
