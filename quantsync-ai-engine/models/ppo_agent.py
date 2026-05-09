import os
import torch
from stable_baselines3 import PPO
from envs.quantsync_env import QuantSyncEnv
import numpy as np

class PPOAgent:
    """
    PPO Reinforcement Learning Agent for QuantSync.
    Includes Safety Net (Circuit Breaker) logic for signal validation.
    """
    def __init__(self, model_path="storage/models/ppo_quantsync"):
        self.model_path = model_path
        self.model = None

    def train(self, df_train=None, total_timesteps=100000):
        if df_train is None:
            # Fetch from TiDB if no data provided
            from storage.tidb_store import TiDBStore
            tidb = TiDBStore()
            df_train = tidb.get_historical_data("crypto", "BTC/USDT", limit=5000)
            
            if df_train.is_empty():
                print("⚠️ [PPO] No data in TiDB for training. Using dummy data for initialization.")
                # Create dummy data for cold start
                import polars as pl
                from datetime import datetime, timedelta
                dummy_data = []
                start_time = datetime.now() - timedelta(days=10)
                price = 60000.0
                for i in range(1000):
                    price += np.random.normal(0, 100)
                    dummy_data.append({
                        "timestamp": start_time + timedelta(minutes=i),
                        "open": price, "high": price+10, "low": price-10, "close": price, "volume": 1.0
                    })
                df_train = pl.DataFrame(dummy_data)

        env = QuantSyncEnv(df_train)
        
        # M1 optimized or CUDA if available
        device = "cuda" if torch.cuda.is_available() else "cpu"
        
        self.model = PPO(
            "MlpPolicy", 
            env, 
            verbose=1, 
            device=device,
            learning_rate=3e-4,
            n_steps=2048,
            batch_size=64,
            ent_coef=0.01 # Encourage exploration
        )
        
        print(f"Starting PPO Training on {device}...")
        self.model.learn(total_timesteps=total_timesteps)
        
        # Save model
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        self.model.save(self.model_path)
        print(f"Model saved to {self.model_path}")

    def load(self):
        if os.path.exists(f"{self.model_path}.zip"):
            self.model = PPO.load(self.model_path)
            return True
        return False

    def predict_signal(self, observation, current_price):
        """
        Predict action and calculate dynamic TP/SL.
        Includes Circuit Breaker validation.
        """
        # Load model if not already loaded
        if self.model is None:
            if not self.load():
                # FAILSAFE: Fallback to neutral signal during development/pre-training phase
                print("DEBUG: [PPOAgent] Using fallback neutral signal (Model missing/not loaded)")
                return {
                    "action": "hold",
                    "type_signal": "neutral",
                    "tp1": float(current_price * 1.02),
                    "tp2": float(current_price * 1.05),
                    "sl1": float(current_price * 0.98),
                    "sl2": float(current_price * 0.95),
                    "probability": 0.0,
                    "is_valid": False
                }

        action_vec, _states = self.model.predict(observation, deterministic=True)
        
        # action_vec: [action_val, tp1_f, tp2_f, sl1_f, sl2_f]
        action_val = action_vec[0]
        tp1_f, tp2_f = action_vec[1], action_vec[2]
        sl1_f, sl2_f = action_vec[3], action_vec[4]

        # 1. Map Action
        action = "hold"
        type_signal = "neutral"
        
        if action_val > 0.33:
            action = "buy"
            type_signal = "long"
        elif action_val < -0.33:
            action = "sell"
            type_signal = "short"

        # 2. Dynamic TP/SL Calculation
        tp1 = current_price * (1 + tp1_f) if action == "buy" else current_price * (1 - tp1_f)
        tp2 = current_price * (1 + tp2_f) if action == "buy" else current_price * (1 - tp2_f)
        sl1 = current_price * (1 - sl1_f) if action == "buy" else current_price * (1 + sl1_f)
        sl2 = current_price * (1 - sl2_f) if action == "buy" else current_price * (1 + sl2_f)

        # 3. Circuit Breaker (Safety Net)
        # a) Reward-Risk Ratio check
        avg_tp_dist = (tp1_f + tp2_f) / 2
        avg_sl_dist = (sl1_f + sl2_f) / 2
        
        is_valid = True
        if action != "hold" and avg_sl_dist >= avg_tp_dist:
            print(f"CIRCUIT BREAKER: Signal Rejected (SL {avg_sl_dist:.4f} >= TP {avg_tp_dist:.4f})")
            action = "hold"
            is_valid = False

        # b) Volatility Spike Detection (Market Realism - Fase 13)
        high, low, close = observation[1], observation[2], observation[3]
        volatility = 0
        if close > 0:
            volatility = (high - low) / close
            if volatility > 0.05: # 5% volatility in one bar is extreme
                print(f"CIRCUIT BREAKER: Extreme Volatility Detected ({volatility:.2%}). Forcing HOLD.")
                action = "hold"
                is_valid = False

        # 4. Probability Calculation (Heuristic for Fase 2)
        # In PPO, we can estimate confidence by reward-risk ratio and volatility
        if action == "hold":
            probability = 0.0
        else:
            # Base probability 70% + bonus for good RR ratio - penalty for volatility
            rr_ratio = avg_tp_dist / max(avg_sl_dist, 0.0001)
            probability = 70.0 + (rr_ratio * 5.0) - (volatility * 100.0)
            probability = np.clip(probability, 50.0, 98.5)

        return {
            "action": action,
            "type_signal": type_signal,
            "tp1": float(tp1),
            "tp2": float(tp2),
            "sl1": float(sl1),
            "sl2": float(sl2),
            "probability": float(probability),
            "is_valid": is_valid
        }
