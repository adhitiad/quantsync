import sys
import os
import logging
from datetime import datetime

# Tambahkan root directory ke sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ingestion.dukascopy_ingestor import DukascopyIngestor
from storage.vector_db import VectorStore

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("TestFase29")

def test_dukascopy():
    logger.info("🧪 Mengetes Dukascopy Ingestor (Python 3.13 Native)...")
    try:
        ingestor = DukascopyIngestor()
        # Test fetch 1 hour of data for EUR/USD
        df = ingestor.fetch_ohlcv("EUR/USD", days=1)
        if df is not None and not df.is_empty():
            logger.info(f"✅ Dukascopy Test Sukses! Berhasil mengambil {len(df)} baris data.")
            print(df.head())
        else:
            logger.error("❌ Dukascopy Test Gagal: Data kosong.")
    except Exception as e:
        logger.error(f"❌ Dukascopy Test Error: {e}")

def test_vector_db():
    logger.info("🧪 Mengetes Koneksi Vector DB (Milvus/Zilliz)...")
    try:
        store = VectorStore()
        if store.vector_store:
            logger.info("✅ Vector DB Inisialisasi Sukses!")
        else:
            logger.error("❌ Vector DB Gagal diinisialisasi (None).")
    except Exception as e:
        logger.error(f"❌ Vector DB Test Error: {e}")

if __name__ == "__main__":
    logger.info("=== STARTING LOCAL TESTING FASE 29 ===")
    test_dukascopy()
    test_vector_db()
    logger.info("=== TESTING COMPLETED ===")
