import sys
import os
import time
import datetime

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from scrapers.rss_scraper import RSSScraper
from scrapers.search_engine import SearchEngine
from storage.vector_db import VectorStore
from utils.processor import DataProcessor
from ingestion.crypto_ingestor import CryptoIngestor
from ingestion.dukascopy_ingestor import DukascopyIngestor
import asyncio

async def run_worker():
    print("AI Engine Worker Started (Async Loop)...")
    
    rss = RSSScraper()
    search = SearchEngine()
    db = VectorStore()
    processor = DataProcessor()
    
    crypto = CryptoIngestor()
    forex = DukascopyIngestor()
    
    last_forex_sync = None

    # Asset list with USDT and USDC pairs (Fase 1/2 Refactor)
    crypto_symbols = [
        "BTC/USDT", "BTC/USDC",
        "ETH/USDT", "ETH/USDC",
        "SOL/USDT", "SOL/USDC",
        "BNB/USDT", "BNB/USDC"
    ]

    while True:
        try:
            now = datetime.datetime.now()
            
            # 1. Market Data Ingestion (Fase 15 & 28)
            print(f"[{now.strftime('%H:%M:%S')}] Fetching Market Data for {len(crypto_symbols)} pairs...")
            # Crypto is async
            await crypto.run(symbols=crypto_symbols)
            
            # 2. Forex Sync (Dukascopy)
            # Run on startup (last_forex_sync is None) or every 4 hours
            if last_forex_sync is None or (now - last_forex_sync).total_seconds() > 14400:
                print(f"[{now.strftime('%H:%M:%S')}] Running Forex Sync (Dukascopy)...")
                # Run sync in thread pool if it blocks too much, but here we run it directly for visibility
                forex.run(days=2) # Fetch last 2 days to bridge any gaps
                last_forex_sync = now
            
            # 3. News/Sentiment Scraping
            print("Fetching News/Sentiment...")
            # Run in executor if it blocks too much, but for now we keep it simple
            rss_data = rss.scrape_all()
            
            # Focused Asset Search
            assets = ["Bitcoin", "Ethereum", "EURUSD", "Gold"]
            search_data = []
            for asset in assets:
                search_data.extend(search.search_sentiment(asset))
            
            # 4. Combine and Process
            total_data = rss_data + search_data
            if total_data:
                df = processor.process_scraped_data(total_data)
                vector_records = processor.prepare_for_vector_db(df)
                db.add_documents(vector_records)
            
            print("Cycle completed. Waiting 15 minutes...")
            await asyncio.sleep(900)
            
        except Exception as e:
            print(f"Worker error: {e}")
            await asyncio.sleep(60)

def start_worker():
    """Entry point for threading"""
    asyncio.run(run_worker())

if __name__ == "__main__":
    start_worker()
