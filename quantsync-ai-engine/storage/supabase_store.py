from sqlalchemy import Column, DateTime, Float, Index, Integer, String, Text, create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import logging
import os
from dotenv import load_dotenv
from database.redis_config import get_redis_config

# Load .env dari root folder (naik dua level dari storage/)
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", ".env"))

logger = logging.getLogger(__name__)

Base = declarative_base()


class MarketData(Base):
    __tablename__ = "market_data"
    id = Column(Integer, primary_key=True, autoincrement=True)
    category = Column(String(20), nullable=False)
    asset = Column(String(50), nullable=False)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)
    timestamp = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_asset_ts", "asset", "timestamp"),
    )


class SignalHistory(Base):
    __tablename__ = "signal_histories"
    id_signal = Column(String(100), primary_key=True)
    no = Column(Integer)
    category = Column(String(20), nullable=False)
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
        Index("idx_sig_asset_ts", "asset", "timestamp"),
    )


class SupabaseStore:
    def __init__(self):
        """
        Menginisialisasi koneksi ke Supabase Postgres.
        DSN diambil dari Redis terlebih dulu, lalu fallback ke environment.
        """
        self.redis_cfg = get_redis_config()
        self.dsn = (
            self.redis_cfg.get_config("DATABASE_URL")
            or self.redis_cfg.get_config("SUPABASE_DATABASE_URL")
            or self.redis_cfg.get_config("SUPABASE_DB_DSN")
        )

        if not self.dsn:
            self.dsn = (
                os.getenv("DATABASE_URL")
                or os.getenv("SUPABASE_DATABASE_URL")
                or os.getenv("SUPABASE_DB_DSN")
            )

        if not self.dsn:
            raise RuntimeError("DATABASE_URL untuk Supabase tidak ditemukan di Redis/Env.")

        self.dsn = self._normalize_sqlalchemy_dsn(self.dsn)

        try:
            self.engine = create_engine(
                self.dsn,
                pool_pre_ping=True,
                pool_recycle=3600,
            )
            self.Session = sessionmaker(bind=self.engine)
            Base.metadata.create_all(self.engine)
            self._ensure_system_configs_table()
            logger.info("[SupabaseStore] Engine database berhasil diinisialisasi")
        except Exception as e:
            logger.error(f"Gagal inisialisasi Supabase engine: {e}")
            raise

    @staticmethod
    def _normalize_sqlalchemy_dsn(dsn):
        if dsn.startswith("postgresql+psycopg://"):
            return dsn
        if dsn.startswith("postgresql://"):
            return dsn.replace("postgresql://", "postgresql+psycopg://", 1)
        if dsn.startswith("postgres://"):
            return dsn.replace("postgres://", "postgresql+psycopg://", 1)
        return dsn

    def _ensure_system_configs_table(self):
        with self.engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS system_configs (
                    "key" VARCHAR(100) PRIMARY KEY,
                    "value" TEXT NOT NULL,
                    "description" TEXT,
                    "updated_at" TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.commit()

    def save_ohlcv(self, category, asset, df):
        """
        df: Pandas DataFrame with columns [timestamp, open, high, low, close, volume]
        """
        session = self.Session()
        try:
            for _, row in df.iterrows():
                data = MarketData(
                    category=category,
                    asset=asset,
                    open=row["open"],
                    high=row["high"],
                    low=row["low"],
                    close=row["close"],
                    volume=row["volume"],
                    timestamp=row["timestamp"],
                )
                session.add(data)
            session.commit()
            logger.info(f"Berhasil menyimpan {len(df)} records untuk {asset} ke Supabase.")
        except Exception as e:
            session.rollback()
            logger.error(f"Gagal menyimpan data ke Supabase: {e}")
        finally:
            session.close()

    def get_historical_data(self, category, asset, limit=1000):
        """
        Mengambil data historis dari Supabase untuk training AI.
        """
        import polars as pl

        session = self.Session()
        try:
            query = session.query(MarketData).filter(
                MarketData.category == category,
                MarketData.asset == asset,
            ).order_by(MarketData.timestamp.desc()).limit(limit)

            data = []
            for row in query.all():
                data.append({
                    "timestamp": row.timestamp,
                    "open": row.open,
                    "high": row.high,
                    "low": row.low,
                    "close": row.close,
                    "volume": row.volume,
                })

            if not data:
                return pl.DataFrame()

            data.reverse()
            return pl.DataFrame(data)
        except Exception as e:
            logger.error(f"Gagal mengambil data historis dari Supabase: {e}")
            return pl.DataFrame()
        finally:
            session.close()

    def get_config(self, key, default=None):
        """
        Mengambil konfigurasi sistem dari tabel system_configs.
        """
        try:
            with self.engine.connect() as conn:
                self._ensure_system_configs_table()

                result = conn.execute(
                    text('SELECT "value" FROM system_configs WHERE "key" = :key'),
                    {"key": key},
                ).fetchone()
                return result[0] if result else default
        except Exception as e:
            logger.warning(f"[SupabaseStore] Gagal mengambil config {key}: {e}")
            return default

    def get_assets_with_min_rows(self, category, min_rows=20):
        """
        Mengembalikan mapping asset -> jumlah row untuk asset yang sudah memenuhi minimum row.
        """
        try:
            with self.engine.connect() as conn:
                rows = conn.execute(
                    text(
                        """
                        SELECT asset, COUNT(*) AS row_count
                        FROM market_data
                        WHERE category = :category
                        GROUP BY asset
                        HAVING COUNT(*) >= :min_rows
                        """
                    ),
                    {"category": category, "min_rows": min_rows},
                ).fetchall()
                return {row[0]: row[1] for row in rows}
        except Exception as e:
            logger.warning(f"[SupabaseStore] Gagal menghitung asset {category}: {e}")
            return {}

    def has_runtime_market_coverage(self, min_rows=20):
        """
        Memastikan minimal ada satu asset crypto dan satu asset forex dengan data cukup
        agar engine tidak berjalan dalam kondisi kategori kosong.
        """
        from runtime_assets import REQUIRED_CRYPTO_SYMBOLS, REQUIRED_FOREX_SYMBOLS

        crypto_assets = self.get_assets_with_min_rows("crypto", min_rows=min_rows)
        forex_assets = self.get_assets_with_min_rows("forex", min_rows=min_rows)

        ready_crypto = [asset for asset in REQUIRED_CRYPTO_SYMBOLS if asset in crypto_assets]
        ready_forex = [asset for asset in REQUIRED_FOREX_SYMBOLS if asset in forex_assets]

        return bool(ready_crypto) and bool(ready_forex), {
            "crypto": ready_crypto,
            "forex": ready_forex,
        }
