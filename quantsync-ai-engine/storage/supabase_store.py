"""
SupabaseStore — Fixed Version
Critical Fix #2: Upsert dengan ON CONFLICT DO NOTHING (no more duplicate rows)
Critical Fix #2b: Bulk insert menggantikan row-by-row
Critical Fix #2c: Tambah kolom `timeframe` agar H1 dan M15 bisa dibedakan
"""

import logging
import os

from dotenv import load_dotenv
from sqlalchemy import (
    Column, DateTime, Float, Index, Integer, String,
    UniqueConstraint, create_engine, event, text,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Load .env dari root (naik dua level dari storage/)
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", ".env"))

logger = logging.getLogger(__name__)

Base = declarative_base()


class MarketData(Base):
    __tablename__ = "market_data"

    id = Column(Integer, primary_key=True, autoincrement=True)
    category = Column(String(20), nullable=False)        # 'crypto' | 'forex' | 'commodity' | 'index'
    asset = Column(String(50), nullable=False)            # 'BTC/USDT', 'EUR/USD', 'CL=F', dst
    timeframe = Column(String(10), nullable=False, default="H1")  # 'H1' | 'M15' | '1d' dst
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)
    timestamp = Column(DateTime, nullable=False)

    __table_args__ = (
        # Unique constraint sebagai dasar ON CONFLICT upsert
        UniqueConstraint("asset", "timeframe", "timestamp", name="uq_asset_timeframe_ts"),
        # Composite index untuk query cepat
        Index("idx_asset_tf_ts", "asset", "timeframe", "timestamp"),
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
        Inisialisasi koneksi ke Supabase Postgres.
        DSN diambil dari environment dulu (lebih reliable),
        kemudian Redis sebagai sumber sekunder jika ada.
        """
        # ─── PRIMARY: ambil dari environment (tidak bergantung Redis) ─────────
        self.dsn = (
            os.getenv("DATABASE_URL")
            or os.getenv("SUPABASE_DATABASE_URL")
            or os.getenv("SUPABASE_DB_DSN")
        )

        # ─── SECONDARY: Redis sebagai sumber override (opsional) ──────────────
        if not self.dsn:
            try:
                from database.redis_config import get_redis_config
                redis_cfg = get_redis_config()
                self.dsn = (
                    redis_cfg.get_config("DATABASE_URL")
                    or redis_cfg.get_config("SUPABASE_DATABASE_URL")
                )
            except Exception as e:
                logger.warning(f"[SupabaseStore] Redis tidak tersedia untuk config lookup: {e}")

        if not self.dsn:
            raise RuntimeError(
                "DATABASE_URL tidak ditemukan di environment maupun Redis. "
                "Pastikan .env sudah diisi atau variabel environment sudah di-set."
            )

        self.dsn = self._normalize_sqlalchemy_dsn(self.dsn)

        try:
            self.engine = create_engine(
                self.dsn,
                pool_pre_ping=True,
                pool_recycle=3600,
                pool_size=5,
                max_overflow=10,
            )
            self.Session = sessionmaker(bind=self.engine)

            # Buat semua tabel + migrate schema jika perlu
            Base.metadata.create_all(self.engine)
            self._ensure_system_configs_table()
            self._migrate_add_timeframe_column()

            logger.info("[SupabaseStore] ✅ Engine database berhasil diinisialisasi")
        except Exception as e:
            logger.error(f"Gagal inisialisasi Supabase engine: {e}")
            raise

    # ─── DSN NORMALIZATION ────────────────────────────────────────────────────

    @staticmethod
    def _normalize_sqlalchemy_dsn(dsn: str) -> str:
        if dsn.startswith("postgresql+psycopg://"):
            return dsn
        if dsn.startswith("postgresql://"):
            return dsn.replace("postgresql://", "postgresql+psycopg://", 1)
        if dsn.startswith("postgres://"):
            return dsn.replace("postgres://", "postgresql+psycopg://", 1)
        return dsn

    # ─── SCHEMA SETUP ─────────────────────────────────────────────────────────

    def _ensure_system_configs_table(self):
        with self.engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS system_configs (
                    "key"         VARCHAR(100) PRIMARY KEY,
                    "value"       TEXT NOT NULL,
                    "description" TEXT,
                    "updated_at"  TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.commit()

    def _migrate_add_timeframe_column(self):
        """
        Migration idempotent: tambah kolom timeframe jika belum ada.
        Aman dijalankan berulang kali.
        """
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'market_data' AND column_name = 'timeframe'
            """)).fetchone()

            if not result:
                logger.info("[SupabaseStore] Menambahkan kolom 'timeframe' ke market_data...")
                conn.execute(text("""
                    ALTER TABLE market_data
                    ADD COLUMN IF NOT EXISTS timeframe VARCHAR(10) NOT NULL DEFAULT 'H1'
                """))
                # Drop index lama jika ada, buat yang baru
                conn.execute(text("DROP INDEX IF EXISTS idx_asset_ts"))
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_asset_tf_ts
                    ON market_data (asset, timeframe, timestamp)
                """))
                # Tambah unique constraint jika belum ada
                conn.execute(text("""
                    ALTER TABLE market_data
                    DROP CONSTRAINT IF EXISTS uq_asset_timeframe_ts
                """))
                conn.execute(text("""
                    ALTER TABLE market_data
                    ADD CONSTRAINT uq_asset_timeframe_ts
                    UNIQUE (asset, timeframe, timestamp)
                """))
                conn.commit()
                logger.info("[SupabaseStore] ✅ Migration 'timeframe' selesai.")

    # ─── CORE WRITE ───────────────────────────────────────────────────────────

    def save_ohlcv(
        self,
        category: str,
        asset: str,
        df,  # pandas DataFrame
        timeframe: str = "H1",
    ) -> int:
        """
        Simpan OHLCV ke Supabase menggunakan bulk upsert.
        ON CONFLICT (asset, timeframe, timestamp) DO NOTHING — aman dari duplikat.

        Returns:
            Jumlah rows yang benar-benar diinsert (bukan duplikat).
        """
        if df is None or df.empty:
            return 0

        # Normalize column names
        df = df.copy()
        if "timestamp" not in df.columns and df.index.name == "timestamp":
            df = df.reset_index()

        required_cols = ["timestamp", "open", "high", "low", "close", "volume"]
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            logger.error(f"[save_ohlcv] Kolom tidak lengkap untuk {asset}: {missing}")
            return 0

        if "volume" not in df.columns:
            df["volume"] = 0.0

        records = [
            {
                "category": category,
                "asset": asset,
                "timeframe": timeframe,
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row["volume"]),
                "timestamp": row["timestamp"],
            }
            for _, row in df.iterrows()
            if row["timestamp"] is not None
        ]

        if not records:
            return 0

        try:
            with self.engine.begin() as conn:  # auto-commit via context manager
                stmt = pg_insert(MarketData).values(records)
                stmt = stmt.on_conflict_do_nothing(
                    index_elements=["asset", "timeframe", "timestamp"]
                )
                result = conn.execute(stmt)
                inserted = result.rowcount
                logger.info(
                    f"[save_ohlcv] {asset}/{timeframe}: {inserted}/{len(records)} rows inserted "
                    f"({len(records) - inserted} duplikat dilewati)"
                )
                return inserted
        except Exception as e:
            logger.error(f"[save_ohlcv] Gagal menyimpan {asset}/{timeframe}: {e}")
            return 0

    # ─── CORE READ ────────────────────────────────────────────────────────────

    def get_historical_data(
        self,
        category: str,
        asset: str,
        limit: int = 1000,
        timeframe: str = "H1",
    ):
        """
        Ambil data historis dari Supabase untuk training AI.
        Returns: polars DataFrame
        """
        import polars as pl

        with self.Session() as session:
            try:
                query = (
                    session.query(MarketData)
                    .filter(
                        MarketData.category == category,
                        MarketData.asset == asset,
                        MarketData.timeframe == timeframe,
                    )
                    .order_by(MarketData.timestamp.desc())
                    .limit(limit)
                )

                rows = query.all()
                if not rows:
                    return pl.DataFrame()

                data = [
                    {
                        "timestamp": r.timestamp,
                        "open": r.open,
                        "high": r.high,
                        "low": r.low,
                        "close": r.close,
                        "volume": r.volume,
                    }
                    for r in reversed(rows)
                ]
                return pl.DataFrame(data)
            except Exception as e:
                logger.error(f"[get_historical_data] Error {asset}: {e}")
                return pl.DataFrame()

    # ─── CONFIG ───────────────────────────────────────────────────────────────

    def get_config(self, key: str, default=None):
        try:
            with self.engine.connect() as conn:
                result = conn.execute(
                    text('SELECT "value" FROM system_configs WHERE "key" = :key'),
                    {"key": key},
                ).fetchone()
                return result[0] if result else default
        except Exception as e:
            logger.warning(f"[SupabaseStore] Gagal ambil config {key}: {e}")
            return default

    # ─── COVERAGE CHECK ───────────────────────────────────────────────────────

    def get_assets_with_min_rows(
        self,
        category: str,
        min_rows: int = 20,
        timeframe: str = "H1",
    ) -> dict[str, int]:
        try:
            with self.engine.connect() as conn:
                rows = conn.execute(
                    text("""
                        SELECT asset, COUNT(*) AS row_count
                        FROM market_data
                        WHERE category = :category AND timeframe = :timeframe
                        GROUP BY asset
                        HAVING COUNT(*) >= :min_rows
                    """),
                    {"category": category, "min_rows": min_rows, "timeframe": timeframe},
                ).fetchall()
                return {r[0]: r[1] for r in rows}
        except Exception as e:
            logger.warning(f"[SupabaseStore] Gagal count asset {category}: {e}")
            return {}

    def has_runtime_market_coverage(self, min_rows: int = 20) -> tuple[bool, dict]:
        """
        Cek coverage runtime minimum.
        Ready = ada minimal 1 crypto H1 + 1 forex H1.
        Commodity (metals) dan index tidak memblok startup.
        """
        from runtime_assets import (
            REQUIRED_CRYPTO_SYMBOLS,
            REQUIRED_FOREX_SYMBOLS,
            REQUIRED_METALS_SYMBOLS,
        )

        crypto_assets = self.get_assets_with_min_rows("crypto",    min_rows=min_rows, timeframe="H1")
        forex_assets  = self.get_assets_with_min_rows("forex",     min_rows=min_rows, timeframe="H1")
        metal_assets  = self.get_assets_with_min_rows("commodity", min_rows=min_rows, timeframe="H1")

        ready_crypto = [a for a in REQUIRED_CRYPTO_SYMBOLS if a in crypto_assets]
        ready_forex  = [a for a in REQUIRED_FOREX_SYMBOLS  if a in forex_assets]
        ready_metals = [a for a in REQUIRED_METALS_SYMBOLS if a in metal_assets]

        return bool(ready_crypto) and bool(ready_forex), {
            "crypto":    ready_crypto,
            "forex":     ready_forex,
            "commodity": ready_metals,
        }
