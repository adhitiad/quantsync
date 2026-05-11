"""
server.py — Fixed Version
Critical Fix #3: gRPC tidak lagi silent fallback ke insecure port di production.
- ENV=production → crash jelas jika sertifikat tidak ada
- ENV=development → warn + izinkan insecure (untuk local dev tanpa certs)
- winrate tidak lagi menggunakan np.random (deterministik)
- _get_all_assets() di-cache via Redis/in-memory dengan TTL
"""

import sys
import os

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

print("Importing core libraries...", flush=True)
import grpc
from concurrent import futures
import time
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import uuid
import numpy as np
import pandas as pd
import gc
import logging

print("Importing TA libraries...", flush=True)
from ta.trend import MACD
from ta.momentum import RSIIndicator

print("Importing ML/Data libraries...", flush=True)
import torch
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning, module="aiohttp")

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

print("Importing local modules...", flush=True)
from models.ppo_agent import PPOAgent
from storage.vector_db import VectorStore
from storage.supabase_store import SupabaseStore, MarketData
from health_status import runtime_health
from runtime_assets import get_required_runtime_assets
from utils.reasoner import get_reasoner

print("Importing proto files...", flush=True)
import signal_pb2
import signal_pb2_grpc

print("Setup logging...", flush=True)
logger = logging.getLogger(__name__)

# ─── ENV CHECK ────────────────────────────────────────────────────────────────
APP_ENV = os.getenv("APP_ENV", "development").lower()
IS_PRODUCTION = APP_ENV == "production"


# ─── ASSET CACHE (menggantikan query DB setiap iterasi stream) ────────────────
_asset_cache: list[str] = []
_asset_cache_ts: float = 0.0
_ASSET_CACHE_TTL: float = 300.0  # 5 menit
_asset_cache_lock = threading.Lock()


def _get_cached_assets(db: SupabaseStore) -> list[str]:
    global _asset_cache, _asset_cache_ts
    now = time.monotonic()
    with _asset_cache_lock:
        if _asset_cache and (now - _asset_cache_ts) < _ASSET_CACHE_TTL:
            return list(_asset_cache)
    # Refresh cache
    from sqlalchemy import select
    try:
        with db.Session() as session:
            query = select(MarketData.asset).distinct()
            results = session.execute(query).fetchall()
            db_assets = [r[0] for r in results]
    except Exception as e:
        logger.error(f"Error fetching assets for cache: {e}")
        db_assets = []

    merged: list[str] = []
    for asset in get_required_runtime_assets() + db_assets:
        if asset not in merged:
            merged.append(asset)

    with _asset_cache_lock:
        _asset_cache = merged
        _asset_cache_ts = time.monotonic()

    return merged


# ─── WINRATE (deterministik, bukan random) ────────────────────────────────────
def _calculate_winrate(probability: float, rr_ratio: float) -> float:
    """
    Winrate dihitung deterministik dari probability dan reward-risk ratio.
    Formula: base + RR bonus, clipped [45, 92].
    Ganti dengan data backtest real ketika tersedia.
    """
    base = probability * 0.80
    rr_bonus = min(rr_ratio * 3.0, 10.0)
    return float(np.clip(base + rr_bonus, 45.0, 92.0))


# ─── GRPC SERVICE ─────────────────────────────────────────────────────────────

class SignalService(signal_pb2_grpc.SignalServiceServicer):
    def __init__(self):
        print("[SignalService] Initializing components...", flush=True)
        self.vector_db = VectorStore()
        self.db = SupabaseStore()
        runtime_health.set("db_ready", True)
        self.ppo = PPOAgent()
        if not self.ppo.load():
            logger.warning("PPO Model not found. Akan menggunakan random weights sampai training selesai.")
        self.reasoner = get_reasoner()
        print("[SignalService] Initialization complete.", flush=True)

    def _prepare_observation(self, asset: str):
        """
        Ambil 50 candle H1 terbaru dari Supabase dan bangun observation vector (15 features).

        FIX 1: _get_temporal_features() dihapus — dead code, 3-feature vs 5-feature mismatch.
        FIX 2: Query filter WHERE timeframe = 'H1' agar tidak mix resolusi setelah migration.
        """
        from sqlalchemy import text

        # FIX 2: tambah filter timeframe = 'H1'
        query = text(
            "SELECT open, high, low, close, volume "
            "FROM market_data "
            "WHERE asset = :asset AND timeframe = 'H1' "
            "ORDER BY timestamp DESC LIMIT 50"
        )

        try:
            with self.db.Session() as session:
                result = session.execute(query, {"asset": asset}).fetchall()

            if not result or len(result) < 20:
                return None, None

            df = pd.DataFrame(result[::-1], columns=["open", "high", "low", "close", "volume"])
            df["rsi"] = RSIIndicator(close=df["close"], window=14).rsi()
            macd = MACD(close=df["close"])
            df["macd"]        = macd.macd()
            df["macd_signal"] = macd.macd_signal()
            df["macd_diff"]   = macd.macd_diff()

            sentiment_text  = self.vector_db.query_sentiment(asset, n_results=1)
            sentiment_score = 0.5
            for kw in ["bullish", "buy", "up", "growth", "positive", "strong"]:
                if kw in sentiment_text.lower():
                    sentiment_score += 0.05
            for kw in ["bearish", "sell", "down", "crash", "negative", "weak"]:
                if kw in sentiment_text.lower():
                    sentiment_score -= 0.05

            df["sentiment"] = np.clip(sentiment_score, 0.0, 1.0)
            df = df.fillna(0)
            latest = df.iloc[-1]

            base_obs = np.array([
                latest["open"], latest["high"], latest["low"], latest["close"], latest["volume"],
                latest["rsi"],  latest["macd"], latest["macd_signal"], latest["macd_diff"],
                latest["sentiment"],
            ], dtype=np.float32)

            from zoneinfo import ZoneInfo
            tz_ny     = ZoneInfo("America/New_York")
            tz_london = ZoneInfo("Europe/London")
            now_utc   = datetime.now(timezone.utc)
            dt_ny     = now_utc.astimezone(tz_ny)
            dt_london = now_utc.astimezone(tz_london)

            h_ny           = dt_ny.hour     + dt_ny.minute     / 60.0
            is_ny_open     = 1.0 if 8 <= dt_ny.hour     < 17 else 0.0
            h_london       = dt_london.hour + dt_london.minute / 60.0
            is_london_open = 1.0 if 8 <= dt_london.hour < 16 else 0.0
            is_overlap     = 1.0 if (is_ny_open and is_london_open) else 0.0

            temporal_obs = np.array(
                [h_ny, is_ny_open, h_london, is_london_open, is_overlap],
                dtype=np.float32,
            )
            return np.concatenate([base_obs, temporal_obs]), float(latest["close"])

        except Exception as e:
            logger.error("Error preparing observation for %s: %s", asset, e)
            return None, None

    def GetTradingSignal(self, request, context):
        asset = request.asset
        if asset == "ALL":
            available = _get_cached_assets(self.db)
            asset = available[0] if available else "BTC/USDT"

        obs, current_price = self._prepare_observation(asset)
        if obs is None:
            return signal_pb2.SignalResponse(
                asset=asset,
                action="hold",
                type_action="wait",
                type_signal="neutral",
                probability_pct=0.0,
                winrate_pct=0.0,
                reason=f"Insufficient market data for {asset} in Supabase.",
            )

        with torch.no_grad():
            ppo_result = self.ppo.predict_signal(obs, current_price)

        is_crypto = "/" in asset and ("USDT" in asset or "USDC" in asset)
        suppressed_crypto_sell = is_crypto and ppo_result["action"] == "sell"

        probability = ppo_result.get("probability", 0.0)
        rr_ratio = ppo_result.get("rr_ratio", 1.0)

        # ─── Deterministik winrate (tidak lagi np.random) ──────────────
        winrate = _calculate_winrate(probability, rr_ratio)

        reason = "Market conditions stable. Waiting for optimal entry point."
        if ppo_result["action"] != "hold" and not suppressed_crypto_sell:
            context_docs = self.vector_db.query_sentiment(asset)
            reason = self.reasoner.generate_reason(
                asset=asset,
                action=ppo_result["action"],
                probability=probability,
                winrate=winrate,
                context_docs=context_docs,
            )
            gc.collect()  # setelah LLM call yang heavy
        elif suppressed_crypto_sell:
            reason = "Crypto spot: sinyal sell disuppress menjadi hold (only long allowed)."

        final_action = ppo_result["action"]
        final_type = ppo_result["type_signal"]
        final_probability = probability
        final_winrate = winrate
        final_type_action = "market"

        if is_crypto:
            if final_action == "buy":
                final_type = "long"
            elif final_action == "sell":
                final_action, final_type, final_probability = "hold", "neutral", 0.0

        if final_action == "hold":
            final_probability, final_winrate, final_type_action = 0.0, 0.0, "wait"

        return signal_pb2.SignalResponse(
            id_signal=str(uuid.uuid4()),
            no=1,
            asset=asset,
            price=current_price,
            action=final_action,
            type_action=final_type_action,
            type_signal=final_type,
            tp1=ppo_result["tp1"],
            tp2=ppo_result["tp2"],
            sl1=ppo_result["sl1"],
            sl2=ppo_result["sl2"],
            probability_pct=final_probability,
            winrate_pct=final_winrate,
            reason=reason,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def wait_until_runtime_data_ready(
        self, timeout_seconds: int = 180, min_rows: int = 20, poll_interval: int = 5
    ) -> bool:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            ready, detail = self.db.has_runtime_market_coverage(min_rows=min_rows)
            if ready:
                runtime_health.set("runtime_data_ready", True)
                logger.info("Runtime market data siap. Crypto=%s Forex=%s", detail["crypto"], detail["forex"])
                return True
            logger.info("Menunggu data runtime. Crypto=%s Forex=%s", detail["crypto"], detail["forex"])
            time.sleep(poll_interval)

        runtime_health.set("runtime_data_ready", False)
        return False

    def StreamSignals(self, request, context):
        logger.info(f"Opening stream for {request.asset}...")
        while context.is_active():
            if request.asset == "ALL":
                assets_to_scan = _get_cached_assets(self.db)
            else:
                assets_to_scan = [request.asset]

            for asset in assets_to_scan:
                temp_req = signal_pb2.SignalRequest(asset=asset)
                signal = self.GetTradingSignal(temp_req, context)
                if signal.action != "hold" and signal.id_signal and signal.probability_pct > 80:
                    yield signal
                elif signal.action != "hold":
                    logger.info(f"Signal {asset} suppressed (prob={signal.probability_pct:.1f}%)")

            time.sleep(60)


# ─── GRPC SERVER STARTUP ──────────────────────────────────────────────────────

def _load_mtls_credentials() -> grpc.ServerCredentials:
    """
    Load sertifikat mTLS. Raise exception jelas jika gagal — jangan silent fallback.
    """
    cert_dir = os.getenv("CERTS_DIR", "certs")
    ca_path     = os.path.join(cert_dir, "ca.crt")
    cert_path   = os.path.join(cert_dir, "server.crt")
    key_path    = os.path.join(cert_dir, "server.key")

    missing = [p for p in [ca_path, cert_path, key_path] if not os.path.exists(p)]
    if missing:
        raise FileNotFoundError(
            f"Sertifikat mTLS tidak ditemukan: {missing}\n"
            f"Jalankan: bash scripts/gen_certs.sh"
        )

    with open(ca_path, "rb") as f:
        ca_cert = f.read()
    with open(cert_path, "rb") as f:
        server_cert = f.read()
    with open(key_path, "rb") as f:
        server_key = f.read()

    return grpc.ssl_server_credentials(
        [(server_key, server_cert)],
        root_certificates=ca_cert,
        require_client_auth=True,
    )


def serve():
    print("AI Engine serve() starting...", flush=True)

    # ─── Health HTTP server ───────────────────────────────────────────────────
    def start_health_server():
        health_port = int(os.getenv("HEALTH_PORT", "8081"))

        class HealthHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path != "/health":
                    self.send_response(404)
                    self.end_headers()
                    return
                if runtime_health.is_ready():
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b"ok")
                else:
                    self.send_response(503)
                    self.end_headers()
                    self.wfile.write(b"warming")

            def log_message(self, format, *args):
                return

        server = ThreadingHTTPServer(("0.0.0.0", health_port), HealthHandler)
        logger.info("Health server running on port %s", health_port)
        server.serve_forever()

    # ─── Background worker ────────────────────────────────────────────────────
    import threading
    from main import start_worker

    threading.Thread(target=start_health_server, daemon=True).start()
    threading.Thread(target=start_worker, daemon=True).start()

    # ─── gRPC server ──────────────────────────────────────────────────────────
    print("[INIT] Initializing gRPC server...", flush=True)
    grpc_server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))

    print("[INIT] Initializing SignalService...", flush=True)
    service = SignalService()

    warmup_timeout = int(os.getenv("RUNTIME_WARMUP_TIMEOUT_SECONDS", "180"))
    min_rows = int(os.getenv("RUNTIME_WARMUP_MIN_ROWS", "20"))
    if not service.wait_until_runtime_data_ready(timeout_seconds=warmup_timeout, min_rows=min_rows):
        logger.warning("Warmup timeout setelah %s detik. Server tetap dinyalakan.", warmup_timeout)

    signal_pb2_grpc.add_SignalServiceServicer_to_server(service, grpc_server)

    grpc_port = int(os.getenv("GRPC_PORT", "50051"))

    # ─── CRITICAL FIX: mTLS tanpa silent fallback ─────────────────────────────
    try:
        credentials = _load_mtls_credentials()
        grpc_server.add_secure_port(f"[::]:{grpc_port}", credentials)
        runtime_health.set("grpc_ready", True)
        logger.info("✅ gRPC server started on port %s with mTLS", grpc_port)

    except FileNotFoundError as e:
        if IS_PRODUCTION:
            # Production: WAJIB crash — tidak boleh jalan tanpa enkripsi
            logger.critical(
                "❌ PRODUCTION: mTLS sertifikat tidak ditemukan. Server TIDAK AKAN berjalan.\n%s", e
            )
            raise SystemExit(1)
        else:
            # Development: warn tapi izinkan insecure
            logger.warning(
                "⚠️  DEVELOPMENT: mTLS sertifikat tidak ditemukan, fallback ke insecure port.\n"
                "Set APP_ENV=production untuk enforce mTLS.\n%s", e
            )
            grpc_server.add_insecure_port(f"[::]:{grpc_port}")
            runtime_health.set("grpc_ready", True)
            logger.info("gRPC server (INSECURE) started on port %s", grpc_port)

    grpc_server.start()
    grpc_server.wait_for_termination()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    serve()
