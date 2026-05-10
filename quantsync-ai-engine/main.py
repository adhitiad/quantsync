"""
quantsync-ai-engine/main.py — Fix #4
last_sync per kategori diupdate HANYA jika task sync berhasil.
Jika gagal, kategori akan dicoba lagi di siklus berikutnya.
"""

import asyncio
import datetime
import logging
import os
import sys
import traceback
from dataclasses import dataclass, field

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from scrapers.rss_scraper import RSSScraper
from scrapers.search_engine import SearchEngine
from storage.vector_db import VectorStore
from utils.processor import DataProcessor
from ingestion.crypto_ingestor import CryptoIngestor
from ingestion.dukascopy_ingestor import DukascopyIngestor
from runtime_assets import (
    REQUIRED_CRYPTO_SYMBOLS,
    get_assets_by_category,
)

logger = logging.getLogger(__name__)

# ─── Interval per kategori (detik) ───────────────────────────────────────────
SYNC_INTERVAL: dict[str, int] = {
    "forex":     14400,   # 4 jam
    "commodity": 3600,    # 1 jam — metals + energy lebih volatile
    "index":     3600,    # 1 jam — ikut sesi pasar
}

SCRAPE_INTERVAL = 900   # 15 menit


# ─── Task result tracker ──────────────────────────────────────────────────────

@dataclass
class SyncTask:
    """Representasi satu task sync — category + coroutine-nya."""
    category: str
    coro: asyncio.Future | None = field(default=None, repr=False)


async def run_worker() -> None:
    logger.info("🚀 [Worker] AI Engine Background Service Started...")

    rss       = RSSScraper()
    search    = SearchEngine()
    vector_db = VectorStore()
    processor = DataProcessor()
    crypto    = CryptoIngestor()
    forex     = DukascopyIngestor()

    # last_sync per kategori — hanya diupdate jika task sukses
    last_sync: dict[str, datetime.datetime | None] = {k: None for k in SYNC_INTERVAL}
    last_scrape: datetime.datetime | None = None

    while True:
        try:
            now = datetime.datetime.now()
            logger.info("[%s] 🔄 Memulai siklus ingestion...", now.strftime("%H:%M:%S"))

            # ── 1. Kumpulkan tasks yang scheduled ─────────────────────────────
            crypto_task   = asyncio.create_task(crypto.run(symbols=REQUIRED_CRYPTO_SYMBOLS))
            sync_tasks: list[SyncTask] = []

            for category, interval in SYNC_INTERVAL.items():
                prev = last_sync[category]
                due  = prev is None or (now - prev).total_seconds() >= interval
                if not due:
                    continue

                assets = get_assets_by_category(category)
                logger.info(
                    "[%s] 📅 Jadwalkan sync %s (%d aset, interval=%dm)",
                    now.strftime("%H:%M:%S"), category, len(assets), interval // 60,
                )
                task = SyncTask(
                    category=category,
                    coro=asyncio.create_task(
                        asyncio.to_thread(forex.run_category, assets, 2)
                    ),
                )
                sync_tasks.append(task)

            # ── 2. Jalankan semua task — crypto selalu, non-crypto jika due ───
            all_tasks: list[asyncio.Task] = [crypto_task] + [t.coro for t in sync_tasks]
            results = await asyncio.gather(*all_tasks, return_exceptions=True)

            # ── 3. Update last_sync HANYA jika berhasil ───────────────────────
            # Index 0 = crypto (tidak perlu last_sync)
            # Index 1..N = sync_tasks
            crypto_result = results[0]
            if isinstance(crypto_result, Exception):
                logger.error("❌ Crypto ingest failed: %s", crypto_result)

            for i, task in enumerate(sync_tasks):
                result = results[i + 1]
                if isinstance(result, Exception):
                    logger.error(
                        "❌ Sync %s failed: %s — akan dicoba ulang di siklus berikutnya.",
                        task.category, result,
                    )
                    # FIX: last_sync TIDAK diupdate → retry di siklus berikutnya
                else:
                    last_sync[task.category] = now
                    logger.info("✅ Sync %s selesai.", task.category)

            # ── 4. Scraping & Vector DB ───────────────────────────────────────
            scrape_due = (
                last_scrape is None
                or (now - last_scrape).total_seconds() >= SCRAPE_INTERVAL
            )
            if scrape_due:
                try:
                    await asyncio.to_thread(_run_scrapers, rss, search, processor, vector_db)
                    last_scrape = now  # update hanya jika berhasil
                except Exception as e:
                    logger.error("❌ Scraping failed: %s — akan dicoba ulang.", e)

            logger.info(
                "[%s] 🏁 Siklus selesai. Menunggu 60 detik...",
                datetime.datetime.now().strftime("%H:%M:%S"),
            )
            await asyncio.sleep(60)

        except Exception as e:
            logger.critical("[CRITICAL] Worker loop error: %s", e)
            traceback.print_exc()
            await asyncio.sleep(60)


def _run_scrapers(rss, search, processor, db) -> None:
    now_str = datetime.datetime.now().strftime("%H:%M:%S")
    logger.info("[%s] 📰 Scraping berita & sentimen...", now_str)

    rss_data    = rss.scrape_all()
    search_data: list = []
    for kw in ["Bitcoin", "Ethereum", "EURUSD", "Gold", "Silver", "Crude Oil", "S&P 500", "Nasdaq"]:
        search_data.extend(search.search_sentiment(kw))

    total = rss_data + search_data
    if total:
        df             = processor.process_scraped_data(total)
        vector_records = processor.prepare_for_vector_db(df)
        db.add_documents(vector_records)
        logger.info("[%s] ✅ %d records → Vector DB.", now_str, len(vector_records))


def start_worker() -> None:
    """Entry point dari server.py (dipanggil via threading.Thread)."""
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(run_worker())
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    start_worker()
