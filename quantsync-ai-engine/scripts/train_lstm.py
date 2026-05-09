import os
import sys
import logging
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset
import numpy as np
import pandas as pd
import polars as pl
from sklearn.preprocessing import MinMaxScaler
from datetime import datetime, timedelta, timezone
import joblib

# Add parent directory to path to import local modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from storage.supabase_store import SupabaseStore
from models.lstm_model import LSTMPredictor, get_device

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("LSTM_Trainer")

class MarketDataset(Dataset):
    def __init__(self, data, window_size=60):
        self.data = torch.FloatTensor(data)
        self.window_size = window_size

    def __len__(self):
        return len(self.data) - self.window_size

    def __getitem__(self, idx):
        # Input: window of data, Target: next closing price
        x = self.data[idx : idx + self.window_size]
        y = self.data[idx + self.window_size, 3]  # Index 3 is 'close'
        return x, y

def train_lstm(asset="BTC/USDC", category="crypto", years=7):
    logger.info(f"🚀 Memulai training LSTM untuk {asset} ({category}) - Data {years} tahun")
    
    device = get_device()
    store = SupabaseStore()
    
    # 1. Fetch Data (7 Years)
    # Estimate total rows based on H1 (1 hour) resolution
    # 7 years * 365 days * 24 hours = 61,320 rows
    # If M1, it would be millions. Let's assume H1/M15 for stability first.
    limit = years * 365 * 24 * 4  # Assume M15 (15 min) -> 4 points per hour
    
    logger.info(f"📡 Mengambil data historis dari Supabase (Limit: {limit})...")
    df_pl = store.get_historical_data(category, asset, limit=limit)
    
    if df_pl.is_empty():
        logger.error("❌ Tidak ada data di database untuk training.")
        return

    df = df_pl.to_pandas()
    logger.info(f"📊 Berhasil memuat {len(df)} baris data.")

    # 2. Preprocessing & Feature Engineering
    # Features: Open, High, Low, Close, Volume
    features = df[['open', 'high', 'low', 'close', 'volume']].values
    
    # Scale Data
    scaler = MinMaxScaler(feature_range=(0, 1))
    scaled_data = scaler.fit_transform(features)
    
    # Save Scaler for later inference
    scaler_path = f"models/weights/scaler_lstm_{asset.replace('/', '_')}.pkl"
    os.makedirs("models/weights", exist_ok=True)
    joblib.dump(scaler, scaler_path)
    logger.info(f"💾 Scaler disimpan ke {scaler_path}")

    # 3. Create Dataset & Loader
    window_size = 60 # 60 lookback periods
    dataset = MarketDataset(scaled_data, window_size=window_size)
    
    train_size = int(0.8 * len(dataset))
    val_size = len(dataset) - train_size
    train_data, val_data = torch.utils.data.random_split(dataset, [train_size, val_size])
    
    train_loader = DataLoader(train_data, batch_size=64, shuffle=True)
    val_loader = DataLoader(val_data, batch_size=64, shuffle=False)

    # 4. Initialize Model
    input_dim = 5  # OHLCV
    hidden_dim = 128
    num_layers = 2
    output_dim = 1
    
    model = LSTMPredictor(input_dim, hidden_dim, num_layers, output_dim).to(device)
    criterion = nn.MSELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)

    # 5. Training Loop
    epochs = 20
    best_loss = float('inf')
    model_path = f"models/weights/lstm_{asset.replace('/', '_')}.pth"

    logger.info("🔥 Memulai Training Epochs...")
    for epoch in range(epochs):
        model.train()
        train_loss = 0
        for x_batch, y_batch in train_loader:
            x_batch, y_batch = x_batch.to(device), y_batch.to(device)
            
            optimizer.zero_grad()
            outputs = model(x_batch)
            loss = criterion(outputs.squeeze(), y_batch)
            loss.backward()
            optimizer.step()
            train_loss += loss.item()
        
        # Validation
        model.eval()
        val_loss = 0
        with torch.no_grad():
            for x_val, y_val in val_loader:
                x_val, y_val = x_val.to(device), y_val.to(device)
                outputs = model(x_val)
                loss = criterion(outputs.squeeze(), y_val)
                val_loss += loss.item()
        
        avg_train_loss = train_loss / len(train_loader)
        avg_val_loss = val_loss / len(val_loader)
        
        logger.info(f"Epoch [{epoch+1}/{epochs}] | Train Loss: {avg_train_loss:.6f} | Val Loss: {avg_val_loss:.6f}")
        
        if avg_val_loss < best_loss:
            best_loss = avg_val_loss
            torch.save(model.state_with_info if hasattr(model, 'state_with_info') else model.state_dict(), model_path)
            logger.info(f"⭐ Best model saved (Loss: {best_loss:.6f})")

    logger.info(f"✅ Training Selesai! Model terbaik disimpan di {model_path}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset", type=str, default="BTC/USDC")
    parser.add_argument("--category", type=str, default="crypto")
    parser.add_argument("--years", type=int, default=7)
    args = parser.parse_args()
    
    train_lstm(asset=args.asset, category=args.category, years=args.years)
