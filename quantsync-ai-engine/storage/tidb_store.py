from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Enum, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
import logging
from dotenv import load_dotenv
from database.redis_config import get_redis_config

# Load .env dari root folder (naik dua level dari storage/)
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", ".env"))

logger = logging.getLogger(__name__)

Base = declarative_base()

class MarketData(Base):
    __tablename__ = 'market_data'
    id = Column(Integer, primary_key=True)
    category = Column(Enum('crypto', 'forex'), nullable=False)
    asset = Column(String(50), nullable=False)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)
    timestamp = Column(DateTime, nullable=False)

    __table_args__ = (
        Index('idx_asset_ts', 'asset', 'timestamp'),
    )

class SignalHistory(Base):
    __tablename__ = 'signal_histories'
    id_signal = Column(String(100), primary_key=True)
    no = Column(Integer)
    category = Column(Enum('crypto', 'forex'), nullable=False)
    asset = Column(String(50), nullable=False)
    price = Column(Float)
    action = Column(String(20))
    type_action = Column(String(50))
    type_signal = Column(String(50))
    tp1 = Column(Float)
    tp2 = Column(Float)
    sl1 = Column(Float)
    sl2 = Column(Float)
    probability_pct = Column(Float)
    winrate_pct = Column(Float)
    reason = Column(String(1000))
    timestamp = Column(DateTime, nullable=False)

    __table_args__ = (
        Index('idx_sig_asset_ts', 'asset', 'timestamp'),
    )

class TiDBStore:
    def __init__(self):
        """
        Menginisialisasi koneksi ke TiDB Cloud.
        DSN diambil dari Redis (Zero Hacker Rule).
        """
        self.redis_cfg = get_redis_config()
        self.dsn = self.redis_cfg.get_config("TIDB_DSN_PYTHON")
        
        if not self.dsn:
            # Fallback ke ENV jika Redis belum siap
            self.dsn = os.getenv("TIDB_DSN_PYTHON") or os.getenv("TIDB_DSN")
        
        if not self.dsn:
            # Last fallback untuk local dev (127.0.0.1 for Windows/Local, tidb for Docker)
            default_host = "127.0.0.1" if os.name == 'nt' else "tidb"
            self.dsn = f"mysql+pymysql://root@{default_host}:4000/quantsync"
            logger.warning(f"TiDB DSN tidak ditemukan di Redis/Env. Menggunakan default {default_host}.")
        
        # Konversi DSN jika dalam format Go (User:Pass@tcp(host:port)/db?params)
        if not self.dsn.startswith("mysql+pymysql://"):
            import re
            
            # Bersihkan query params (seperti ?tls=tidb) agar tidak mengganggu pymysql
            dsn_clean = self.dsn
            has_tls = "tls=" in self.dsn
            if "?" in dsn_clean:
                dsn_clean = dsn_clean.split("?")[0]
            
            # Parse format Go: user:password@tcp(host:port)/dbname
            match = re.match(r"(.+):(.*)@tcp\((.+)\)/(.+)", dsn_clean)
            if match:
                user, pw, host, db = match.groups()
                self.dsn = f"mysql+pymysql://{user}:{pw}@{host}/{db}"
            else:
                # Fallback jika format sudah setengah benar tapi ada tcp()
                self.dsn = self.dsn.replace("tcp(", "").replace(")", "")
                if "@" in self.dsn and not "://" in self.dsn:
                    self.dsn = "mysql+pymysql://" + self.dsn

        try:
            # TiDB Cloud membutuhkan SSL. Pymysql menggunakan 'ssl' di connect_args.
            connect_args = {}
            if "tidbcloud.com" in self.dsn or os.getenv("TIDB_SSL", "true").lower() == "true":
                try:
                    import certifi
                    # Gunakan bundle CA dari certifi agar tidak perlu download file .pem manual
                    connect_args["ssl"] = {"ca": certifi.where()}
                    logger.info("🔒 [TiDBStore] SSL/TLS enabled using certifi bundle")
                except ImportError:
                    connect_args["ssl"] = True
                    logger.warning("⚠️ [TiDBStore] certifi tidak ditemukan, menggunakan SSL default")

            self.engine = create_engine(
                self.dsn, 
                pool_recycle=3600,
                connect_args=connect_args
            )
            self.Session = sessionmaker(bind=self.engine)
            logger.info("✅ [TiDBStore] Engine database berhasil diinisialisasi")
        except Exception as e:
            logger.error(f"❌ Gagal inisialisasi TiDB engine: {e}")
            raise

    def save_ohlcv(self, category, asset, df):
        """
        df: Pandas DataFrame with columns [timestamp, open, high, low, close, volume]
        """
        session = self.Session()
        try:
            for _, row in df.iterrows():
                # Check if exists to avoid duplicates
                # This is simple version, in prod use UPSERT or bulk insert with ignore
                data = MarketData(
                    category=category,
                    asset=asset,
                    open=row['open'],
                    high=row['high'],
                    low=row['low'],
                    close=row['close'],
                    volume=row['volume'],
                    timestamp=row['timestamp']
                )
                session.add(data)
            session.commit()
            logger.info(f"Berhasil menyimpan {len(df)} records untuk {asset} ke TiDB.")
        except Exception as e:
            session.rollback()
            logger.error(f"Gagal menyimpan data ke TiDB: {e}")
        finally:
            session.close()

    def get_historical_data(self, category, asset, limit=1000):
        """
        Mengambil data historis dari TiDB untuk training AI.
        """
        import polars as pl
        session = self.Session()
        try:
            query = session.query(MarketData).filter(
                MarketData.category == category,
                MarketData.asset == asset
            ).order_by(MarketData.timestamp.desc()).limit(limit)
            
            data = []
            for row in query.all():
                data.append({
                    "timestamp": row.timestamp,
                    "open": row.open,
                    "high": row.high,
                    "low": row.low,
                    "close": row.close,
                    "volume": row.volume
                })
            
            if not data:
                return pl.DataFrame()
                
            # Reverse to ascending order for training
            data.reverse()
            return pl.DataFrame(data)
        except Exception as e:
            logger.error(f"Gagal mengambil data historis dari TiDB: {e}")
            return pl.DataFrame()
        finally:
            session.close()

    def get_config(self, key, default=None):
        """
        Mengambil konfigurasi sistem dari tabel system_configs (Zero Hacker Rule).
        """
        from sqlalchemy import text
        try:
            with self.engine.connect() as conn:
                # Auto-create table if not exists (Fase 1/2 robustness)
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS system_configs (
                        `key` VARCHAR(100) PRIMARY KEY,
                        `value` TEXT NOT NULL,
                        `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                    )
                """))
                conn.commit()
                
                result = conn.execute(
                    text("SELECT `value` FROM system_configs WHERE `key` = :key"),
                    {"key": key}
                ).fetchone()
                return result[0] if result else default
        except Exception as e:
            logger.warning(f"⚠️ [TiDBStore] Gagal mengambil config {key}: {e}")
            return default
