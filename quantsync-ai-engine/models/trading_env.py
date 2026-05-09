import gymnasium as gym
from gymnasium import spaces
import numpy as np

from zoneinfo import ZoneInfo
from datetime import datetime

class TradingEnv(gym.Env):
    """
    Custom Environment for Reinforcement Learning in Trading.
    Updated for Gymnasium standard with Temporal Context (Fase 17).
    """
    def __init__(self, df, initial_balance=10000):
        super(TradingEnv, self).__init__()
        
        self.df = df
        self.initial_balance = initial_balance
        self.current_step = 0
        
        # New York Timezone for Market Context
        self.tz_ny = ZoneInfo("America/New_York")
        
        # Actions: 0 = Hold, 1 = Buy, 2 = Sell
        self.action_space = spaces.Discrete(3)
        
        # Observation space: 10 Technical/Sentiment + 3 Temporal = 13 total
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=(13,), dtype=np.float32)
        
        self.reset()

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.balance = self.initial_balance
        self.net_worth = self.initial_balance
        self.shares_held = 0
        self.current_step = 0
        
        observation, _ = self._next_observation()
        info = {}
        return observation, info

    def _get_temporal_features(self, dt=None):
        """Calculates New York temporal features."""
        if dt is None:
            dt = datetime.now(ZoneInfo("UTC"))
        
        # Convert to NY Time
        ny_now = dt.astimezone(self.tz_ny)
        
        hour_ny = ny_now.hour
        day_of_week = ny_now.weekday() # 0-6
        
        # NY Session: 09:30 - 16:00 (EST/EDT)
        is_ny_open = 0
        if 0 <= day_of_week <= 4: # Mon-Fri
            current_minutes = hour_ny * 60 + ny_now.minute
            if 570 <= current_minutes <= 960: # 9:30 to 16:00
                is_ny_open = 1
                
        return np.array([hour_ny, day_of_week, is_ny_open], dtype=np.float32)

    def _next_observation(self):
        # Return the data at current_step
        if self.current_step >= len(self.df):
            return np.zeros(13, dtype=np.float32), None
        
        # 10 base features
        base_obs = self.df.iloc[self.current_step].values.astype(np.float32)
        
        # 3 temporal features
        timestamp = self.df.index[self.current_step] if hasattr(self.df.index, 'tz') else None
        temporal_obs = self._get_temporal_features(timestamp)
        
        full_obs = np.concatenate([base_obs, temporal_obs])
        return full_obs, timestamp

    def step(self, action):
        current_price = self.df.iloc[self.current_step]['close']
        
        # Execute trade
        if action == 1: # Buy
            total_possible = self.balance / current_price
            self.shares_held += total_possible
            self.balance = 0
        elif action == 2: # Sell
            self.balance += self.shares_held * current_price
            self.shares_held = 0
            
        self.current_step += 1
        self.net_worth = self.balance + (self.shares_held * current_price)
        
        reward = self.net_worth - self.initial_balance
        
        # Gymnasium standard: terminated (goal/limit) and truncated (time limit)
        terminated = self.current_step >= len(self.df) - 1
        truncated = False
        
        observation = self._next_observation() if not terminated else np.zeros(5, dtype=np.float32)
        info = {"net_worth": self.net_worth}
        
        return observation, reward, terminated, truncated, info

    def render(self, mode='human'):
        print(f'Step: {self.current_step}, Net Worth: {self.net_worth}')

