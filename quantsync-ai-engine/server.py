import sys
import os

# FIX: Force UTF-8 encoding for Windows console to handle emojis
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

print("Importing core libraries...", flush=True)
import grpc
from concurrent import futures
import time
from datetime import datetime, timezone
import uuid
import numpy as np
import pandas as pd
print("Importing TA libraries...", flush=True)
from ta.trend import MACD
from ta.momentum import RSIIndicator
print("Importing ML/Data libraries...", flush=True)
import torch
import gc
import logging
from dotenv import load_dotenv
import os
import warnings

# Suppress aiohttp deprecation warnings on Python 3.13
warnings.filterwarnings("ignore", category=DeprecationWarning, module="aiohttp")

print("Loading .env...", flush=True)
# Load .env from root
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

print("Importing local models and storage...", flush=True)
# Real models and utilities
from models.ppo_agent import PPOAgent
from storage.vector_db import VectorStore
from storage.tidb_store import TiDBStore, MarketData
from utils.reasoner import get_reasoner

print("Importing proto files...", flush=True)
# Generated from proto
import signal_pb2
import signal_pb2_grpc

print("Setup logging...", flush=True)
logger = logging.getLogger(__name__)

class SignalService(signal_pb2_grpc.SignalServiceServicer):
    def __init__(self):
        print("[SignalService] Initializing components...", flush=True)
        print("[SignalService] Loading VectorStore...", flush=True)
        self.vector_db = VectorStore()
        print("[SignalService] Loading TiDBStore...", flush=True)
        self.tidb = TiDBStore()
        print("[SignalService] Loading PPOAgent...", flush=True)
        self.ppo = PPOAgent()
        # Ensure we try to load the model
        if not self.ppo.load():
            logger.warning("PPO Model not found. Signal generator will use random weights until trained.")
        print("[SignalService] Loading Reasoner...", flush=True)
        self.reasoner = get_reasoner()
        print("[SignalService] Initialization complete.", flush=True)

    def _get_temporal_features(self):
        """Calculates New York temporal features using zoneinfo."""
        from zoneinfo import ZoneInfo
        from datetime import datetime
        
        tz_ny = ZoneInfo("America/New_York")
        ny_now = datetime.now(tz_ny)
        
        hour_ny = ny_now.hour
        day_of_week = ny_now.weekday()
        
        is_ny_open = 0
        if 0 <= day_of_week <= 4:
            current_minutes = hour_ny * 60 + ny_now.minute
            if 570 <= current_minutes <= 960:
                is_ny_open = 1
        
        return np.array([hour_ny, day_of_week, is_ny_open], dtype=np.float32)

    def _prepare_observation(self, asset):
        """
        Fetches real data from TiDB and prepares the 15-feature observation vector.
        """
        from sqlalchemy import text
        query = text("SELECT open, high, low, close, volume FROM market_data WHERE asset = :asset ORDER BY timestamp DESC LIMIT 50")
        
        try:
            with self.tidb.Session() as session:
                result = session.execute(query, {"asset": asset}).fetchall()
                if not result or len(result) < 20: 
                    return None, None
                
                # Convert to DataFrame (reverse to get chronological order)
                df = pd.DataFrame(result[::-1], columns=['open', 'high', 'low', 'close', 'volume'])
                
                # Add Indicators
                df['rsi'] = RSIIndicator(close=df['close'], window=14).rsi()
                macd = MACD(close=df['close'])
                df['macd'] = macd.macd()
                df['macd_signal'] = macd.macd_signal()
                df['macd_diff'] = macd.macd_diff()
                
                # Real Sentiment from Vector DB (Fase 2)
                sentiment_text = self.vector_db.query_sentiment(asset, n_results=1)
                # Simple sentiment scoring: neutral 0.5, bullish keywords +0.1, bearish -0.1
                sentiment_score = 0.5
                bullish_keywords = ["bullish", "buy", "up", "growth", "positive", "strong"]
                bearish_keywords = ["bearish", "sell", "down", "crash", "negative", "weak"]
                
                for kw in bullish_keywords:
                    if kw in sentiment_text.lower(): sentiment_score += 0.05
                for kw in bearish_keywords:
                    if kw in sentiment_text.lower(): sentiment_score -= 0.05
                
                df['sentiment'] = np.clip(sentiment_score, 0, 1)
                
                # Fill NaNs
                df = df.fillna(0)
                
                latest = df.iloc[-1]
                base_obs = np.array([
                    latest['open'], latest['high'], latest['low'], latest['close'], latest['volume'],
                    latest['rsi'], latest['macd'], latest['macd_signal'], latest['macd_diff'],
                    latest['sentiment']
                ], dtype=np.float32)
                
                # Add Temporal Features (15 features total for QuantSyncEnv)
                # hour_ny (1), is_ny_open (1), hour_london (1), is_london_open (1), is_overlap (1)
                from zoneinfo import ZoneInfo
                from datetime import timezone
                tz_ny = ZoneInfo("America/New_York")
                tz_london = ZoneInfo("Europe/London")
                now_utc = datetime.now(timezone.utc)
                dt_ny = now_utc.astimezone(tz_ny)
                dt_london = now_utc.astimezone(tz_london)
                
                h_ny = dt_ny.hour + dt_ny.minute / 60.0
                is_ny_open = 1.0 if 8 <= dt_ny.hour < 17 else 0.0
                h_london = dt_london.hour + dt_london.minute / 60.0
                is_london_open = 1.0 if 8 <= dt_london.hour < 16 else 0.0
                is_overlap = 1.0 if (is_ny_open and is_london_open) else 0.0
                
                temporal_obs = np.array([h_ny, is_ny_open, h_london, is_london_open, is_overlap], dtype=np.float32)
                
                full_obs = np.concatenate([base_obs, temporal_obs])
                
                return full_obs, float(latest['close'])
        except Exception as e:
            logger.error(f"Error preparing observation for {asset}: {e}")
            return None, None

    def _get_all_assets(self):
        """
        Fetches unique assets from the market_data table.
        """
        from sqlalchemy import select, func
        try:
            with self.tidb.Session() as session:
                query = select(MarketData.asset).distinct()
                results = session.execute(query).fetchall()
                return [r[0] for r in results]
        except Exception as e:
            logger.error(f"Error fetching assets: {e}")
            return ["BTC/USDT", "ETH/USDT", "EUR/USD", "GBP/USD"]

    def GetTradingSignal(self, request, context):
        """
        Generates a trading signal with mTLS protection and memory optimization.
        """
        asset = request.asset
        if asset == "ALL":
            available_assets = self._get_all_assets()
            asset = available_assets[0] if available_assets else "BTC/USDT"
        
        # 1. Get Real Observation
        obs, current_price = self._prepare_observation(asset)
        if obs is None:
            return signal_pb2.SignalResponse(
                asset=asset,
                reason=f"Insufficent market data for {asset} in TiDB."
            )

        # 2. PPO Prediction with Memory Optimization (Fase 22)
        with torch.no_grad():
            ppo_result = self.ppo.predict_signal(obs, current_price)
        
        # 3. RAG Synthesis & LLM Reasoner
        probability = ppo_result.get("probability", 0.0)
        # Mock winrate based on probability for consistency
        winrate = float(np.clip(probability * 0.85 + np.random.uniform(-3, 3), 40, 95))
        
        reason = "Market conditions stable. Waiting for optimal entry point."
        if ppo_result["action"] != "hold":
            context_docs = self.vector_db.query_sentiment(asset)
            reason = self.reasoner.generate_reason(
                asset=asset,
                action=ppo_result["action"],
                probability=probability,
                winrate=winrate,
                context_docs=context_docs
            )
            
            # Forced Garbage Collection after heavy LLM/RAG process (Fase 22)
            gc.collect()

        # Enforce rules from rules.md (Fase 2)
        is_crypto = "/" in asset and ("USDT" in asset or "USDC" in asset)
        final_action = ppo_result["action"]
        final_type = ppo_result["type_signal"]

        if is_crypto:
            # Crypto Spot: action: "buy" (hardcoded), type_signal: "long" (hardcoded)
            final_action = "buy"
            final_type = "long"
            # If PPO suggested sell, we override to hold or just skip it in StreamSignals
            # For now, we follow the UI rule that crypto signals shown are always buys.
        
        return signal_pb2.SignalResponse(
            id_signal=str(uuid.uuid4()),
            no=1,
            asset=asset,
            price=current_price,
            action=final_action,
            type_action="market",
            type_signal=final_type,
            tp1=ppo_result["tp1"],
            tp2=ppo_result["tp2"],
            sl1=ppo_result["sl1"],
            sl2=ppo_result["sl2"],
            probability_pct=probability,
            winrate_pct=winrate,
            reason=reason,
            timestamp=datetime.now(timezone.utc).isoformat()
        )


    def StreamSignals(self, request, context):
        logger.info(f"Opening Stream for {request.asset}...")
        while context.is_active():
            if request.asset == "ALL":
                assets_to_scan = self._get_all_assets()
            else:
                assets_to_scan = [request.asset]

            for asset in assets_to_scan:
                temp_request = signal_pb2.SignalRequest(asset=asset)
                signal = self.GetTradingSignal(temp_request, context)
                
                # Optimization (Fase 2): Only stream if probability > 80%
                if signal.action != "hold" and signal.id_signal and signal.probability_pct > 80:
                    yield signal
                elif signal.action != "hold":
                    logger.info(f"Signal for {asset} suppressed (Probability: {signal.probability_pct:.2f}%)")
            
            time.sleep(60) # Scan every 1 minute

def serve():
    print("AI Engine serve() starting...", flush=True)
    # Start background ingestion worker
    import threading
    from main import start_worker
    print("[INIT] Starting ingestion worker thread...", flush=True)
    worker_thread = threading.Thread(target=start_worker, daemon=True)

    worker_thread.start()
    
    print("[INIT] Initializing gRPC server...", flush=True)
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    print("[INIT] Initializing SignalService (this might take a while)...", flush=True)
    service = SignalService()
    signal_pb2_grpc.add_SignalServiceServicer_to_server(service, server)
    
    # mTLS Configuration (Fase 21)
    try:
        with open('certs/ca.crt', 'rb') as f:
            ca_cert = f.read()
        with open('certs/server.crt', 'rb') as f:
            server_cert = f.read()
        with open('certs/server.key', 'rb') as f:
            server_key = f.read()
            
        credentials = grpc.ssl_server_credentials(
            [(server_key, server_cert)],
            root_certificates=ca_cert,
            require_client_auth=True # ENFORCE mTLS
        )
        
        server.add_secure_port('[::]:50051', credentials)
        logger.info("✅ QuantSync AI Engine Server started on port 50051 with mTLS")
    except Exception as e:
        logger.error(f"Failed to start server with mTLS: {e}. Falling back to insecure for development.")
        server.add_insecure_port('[::]:50051')

    server.start()
    server.wait_for_termination()

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    serve()
