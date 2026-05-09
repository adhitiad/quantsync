# QuantSync API & Protocol Documentation

Dokumentasi ini menjelaskan protokol komunikasi internal dan eksternal dalam ekosistem QuantSync. **REST API dinonaktifkan secara total** untuk alasan keamanan dan performa real-time.

## 1. Internal gRPC Protocol (Python AI -> Go Gateway)

Komunikasi antara Python AI Engine (Brain) dan Go Gateway menggunakan gRPC dengan pengamanan **mTLS (Mutual TLS)**.

**Proto Definition (`proto/signal.proto`):**
```protobuf
syntax = "proto3";
package quantsync;

service SignalService {
  rpc PushSignal (SignalPayload) returns (SignalResponse);
}

message SignalPayload {
  string id_signal = 1;
  string asset = 2;          // e.g., "BTC/USDT" or "EUR/USD"
  string type_signal = 3;    // "Long" or "Short"
  string type_action = 4;    // "Limit", "Market", "Stop"
  string action = 5;         // "BUY" or "SELL"
  double price = 6;
  double tp1 = 7;
  double tp2 = 8;
  double sl1 = 9;
  double sl2 = 10;
  double probability_pct = 11;
  double winrate_pct = 12;
  string reason = 13;        // LangChain RAG output (NVIDIA Embeddings)
  string timestamp_utc = 14; 
}

message SignalResponse {
  bool success = 1;
  string message = 2;
}
```

---

## 2. Client WebSocket Protocol (Go Gateway -> User Frontend/App)

Semua koneksi klien menggunakan **WebSocket Secure (WSS)** pada port `8443`.

**Endpoint:** `wss://<your-domain-or-localhost>:8443/ws?token=<JWT_TOKEN>`

### A. Authentication
- Klien **WAJIB** menyertakan JWT token yang valid di query parameter saat melakukan handshake.
- Server akan memverifikasi token terhadap `JWT_SECRET` yang ada di database sebelum meng-upgrade koneksi.
- Jika token invalid atau kadaluarsa, koneksi akan ditolak dengan status **401 Unauthorized**.

### B. Heartbeat (Ping/Pong)
Untuk menjaga koneksi tetap aktif melewati load balancer/firewall:
- **Client sends:** `{"type": "ping"}` setiap 30 detik.
- **Server responds:** `{"type": "pong"}`.
- Jika dalam 15 detik (Aggressive Timeout) server tidak menerima ping/pong, koneksi akan di-drop.

### C. Signal Push Event (Server to Client)
Setiap kali Go Gateway menerima sinyal dari AI Engine, payload akan di-broadcast ke klien yang terverifikasi dalam format JSON berikut:

```json
{
  "event": "new_signal",
  "data": {
    "id_signal": "sig-88392-btc",
    "asset": "BTC/USDT",
    "action": "BUY",
    "order_type": "Limit",
    "signal_type": "Long",
    "entry_price": 64500.50,
    "take_profit": {
      "tp1": 65000.00,
      "tp2": 66500.00
    },
    "stop_loss": {
      "sl1": 63000.00,
      "sl2": 62000.00
    },
    "metrics": {
      "probability": 85.5,
      "winrate": 78.2
    },
    "analysis": {
      "reason": "MACD golden cross terdeteksi di timeframe H4. Sentimen pasar positif pasca rilis laporan ETF dari SEC (Confidence: High)."
    },
    "timestamps": {
      "utc": "2026-05-06T06:32:00Z",
      "wib": "13:32 WIB",
      "ny": "02:32 EST",
      "london": "07:32 BST"
    }
  }
}
```

---

## 3. Rate Limiting (WebSocket)

Sistem menerapkan rate limiting berbasis User ID dan Paket Langganan:
- **Free:** 10 messages / minute.
- **Pro:** 100 messages / minute.
- **Elite:** Unlimited.

Jika batas terlampaui, server akan mengirimkan pesan error dan menutup koneksi sementara.
