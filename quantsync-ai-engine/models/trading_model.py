import torch
import torch.nn as nn
import os

class TradingModel(nn.Module):
    def __init__(self, input_dim, hidden_dim, output_dim, num_layers=2):
        super(TradingModel, self).__init__()
        
        # Hardware Detection & Setup
        self.device = self._detect_device()
        
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        
        # LSTM Layer
        self.lstm = nn.LSTM(input_dim, hidden_dim, num_layers, batch_first=True)
        
        # Dense (Fully Connected) Layers
        self.fc1 = nn.Linear(hidden_dim, 64)
        self.fc2 = nn.Linear(64, output_dim)
        
        self.to(self.device)
        print(f"Model initialized on: {self.device}")

    def _detect_device(self):
        if torch.cuda.is_available():
            device = torch.device("cuda")
            # Maximize VRAM allocation awareness
            torch.cuda.empty_cache()
            # Set memory growth if needed (not direct in torch but we can check available memory)
            free_mem, total_mem = torch.cuda.mem_get_info()
            print(f"CUDA Detected. Total VRAM: {total_mem / 1024**3:.2f} GB, Free: {free_mem / 1024**3:.2f} GB")
        else:
            device = torch.device("cpu")
            print("CUDA not available, falling back to CPU.")
        return device

    def forward(self, x):
        # Initialize hidden and cell states
        h0 = torch.zeros(self.num_layers, x.size(0), self.hidden_dim).to(self.device)
        c0 = torch.zeros(self.num_layers, x.size(0), self.hidden_dim).to(self.device)
        
        # LSTM forward
        out, _ = self.lstm(x, (h0, c0))
        
        # Decode the hidden state of the last time step
        out = self.fc1(out[:, -1, :])
        out = torch.relu(out)
        out = self.fc2(out)
        return out

if __name__ == "__main__":
    # Test model initialization
    model = TradingModel(input_dim=10, hidden_dim=32, output_dim=3)
