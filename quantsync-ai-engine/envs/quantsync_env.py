import gymnasium as gym
from gymnasium import spaces
import numpy as np
import polars as pl
from ta.trend import MACD
from ta.momentum import RSIIndicator
from zoneinfo import ZoneInfo
from datetime import datetime

class QuantSyncEnv(gym.Env):
    """
    Advanced Trading Environment for QuantSync.
    Implements institutional standards: fees, slippage, and temporal context.
    """
    def __init__(self, df, initial_balance=10000, fee_maker=0.0001, fee_taker=0.0005, slippage=0.0001, spread=0.0002):
        super(QuantSyncEnv, self).__init__()
        
        # Timezones
        self.tz_ny = ZoneInfo("America/New_York")
        self.tz_london = ZoneInfo("Europe/London")
        
        # Data & Config
        self.df = self._add_indicators(df)
        self.initial_balance = initial_balance
        self.fee_maker = fee_maker # Maker fee (limit orders)
        self.fee_taker = fee_taker # Taker fee (market orders)
        self.slippage = slippage   # Market slippage simulation
        self.spread = spread       # Bid-Ask spread
        
        # State: 
        # Base: OHLCV (5) + RSI (1) + MACD (3) + Sentiment (1) = 10
        # Temporal: Hour NY (1), NY Open (1), Hour London (1), London Open (1), Overlap (1) = 5
        # Total = 15 features
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=(15,), dtype=np.float32)
        
        # Actions: [Action, TP1_Factor, TP2_Factor, SL1_Factor, SL2_Factor]
        self.action_space = spaces.Box(
            low=np.array([-1, 0.005, 0.01, 0.005, 0.01]), 
            high=np.array([1, 0.05, 0.1, 0.05, 0.1]), 
            dtype=np.float32
        )
        
        self.reset()

    def _add_indicators(self, df_pl):
        # Convert to pandas for ta library
        df = df_pl.to_pandas()
        
        # RSI
        df['rsi'] = RSIIndicator(close=df['close'], window=14).rsi()
        
        # MACD
        macd = MACD(close=df['close'])
        df['macd'] = macd.macd()
        df['macd_signal'] = macd.macd_signal()
        df['macd_diff'] = macd.macd_diff()
        
        # Sentiment Placeholder
        if 'sentiment' not in df.columns:
            df['sentiment'] = 0.5
            
        # Clean NaNs
        df = df.fillna(0)
        return df

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.balance = self.initial_balance
        self.shares_held = 0
        self.current_step = 0
        self.net_worth = self.initial_balance
        self.max_net_worth = self.initial_balance
        self.hold_duration = 0
        
        observation = self._get_observation()
        return observation, {}

    def _get_observation(self):
        row = self.df.iloc[self.current_step]
        
        # Base indicators (10)
        base_obs = [
            row['open'], row['high'], row['low'], row['close'], row['volume'],
            row['rsi'], row['macd'], row['macd_signal'], row['macd_diff'],
            row['sentiment']
        ]
        
        # Temporal Context (5)
        # Handle timestamp if available, else fallback to dummy
        if 'timestamp' in row:
            ts = row['timestamp']
            if isinstance(ts, str):
                dt_utc = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            elif hasattr(ts, 'to_pydatetime'):
                dt_utc = ts.to_pydatetime()
            else:
                dt_utc = datetime.fromtimestamp(ts / 1e9) # Assuming nanoseconds from polars
                
            dt_ny = dt_utc.astimezone(self.tz_ny)
            dt_london = dt_utc.astimezone(self.tz_london)
            
            h_ny = dt_ny.hour + dt_ny.minute / 60.0
            is_ny_open = 1.0 if 8 <= dt_ny.hour < 17 else 0.0
            
            h_london = dt_london.hour + dt_london.minute / 60.0
            is_london_open = 1.0 if 8 <= dt_london.hour < 16 else 0.0
            
            is_overlap = 1.0 if (is_ny_open and is_london_open) else 0.0
        else:
            h_ny, is_ny_open, h_london, is_london_open, is_overlap = 0.0, 0.0, 0.0, 0.0, 0.0

        temporal_obs = [h_ny, is_ny_open, h_london, is_london_open, is_overlap]
        
        return np.array(base_obs + temporal_obs, dtype=np.float32)

    def step(self, action_vec):
        action_val = action_vec[0]
        current_price = self.df.iloc[self.current_step]['close']
        prev_net_worth = self.net_worth
        
        # 1. Execute Logic
        if action_val > 0.33: # Buy
            if self.balance > 0:
                entry_price = current_price * (1 + self.slippage + (self.spread / 2))
                cost = self.balance * self.fee_taker
                self.shares_held = (self.balance - cost) / entry_price
                self.balance = 0
                self.hold_duration = 0
        elif action_val < -0.33: # Sell
            if self.shares_held > 0:
                exit_price = current_price * (1 - self.slippage - (self.spread / 2))
                self.balance = self.shares_held * exit_price * (1 - self.fee_taker)
                self.shares_held = 0
                self.hold_duration = 0
        else: # Hold
            if self.shares_held > 0:
                self.hold_duration += 1
        
        self.current_step += 1
        self.net_worth = self.balance + (self.shares_held * current_price)
        self.max_net_worth = max(self.max_net_worth, self.net_worth)
        
        # 2. Reward Calculation
        pnl = (self.net_worth - prev_net_worth) / prev_net_worth
        drawdown = (self.max_net_worth - self.net_worth) / self.max_net_worth
        drawdown_penalty = 0
        if drawdown > 0.02:
            drawdown_penalty = np.exp(drawdown * 10) - 1
            
        hold_penalty = 0
        if self.shares_held > 0 and self.hold_duration > 50:
            hold_penalty = 0.001 * (self.hold_duration - 50)
            
        reward = pnl - drawdown_penalty - hold_penalty
        
        # 3. Termination
        terminated = self.current_step >= len(self.df) - 1
        truncated = self.net_worth < (self.initial_balance * 0.5)
        
        obs = self._get_observation() if not terminated else np.zeros(15, dtype=np.float32)
        
        info = {
            "net_worth": self.net_worth,
            "drawdown": drawdown,
            "tp1": current_price * (1 + action_vec[1]) if action_val > 0 else 0,
            "sl1": current_price * (1 - action_vec[3]) if action_val > 0 else 0
        }
        
        return obs, reward, terminated, truncated, info

    def render(self):
        print(f"Step: {self.current_step} | NW: {self.net_worth:.2f} | Hold: {self.hold_duration}")
