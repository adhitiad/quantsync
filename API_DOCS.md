# QuantSync API & Protocol Documentation

Dokumentasi ini menjelaskan protokol komunikasi internal dan eksternal dalam ekosistem QuantSync. REST publik tetap minimal; distribusi sinyal utama berjalan lewat WebSocket dan dokumentasi runtime tersedia di `/api/docs`.

## 1. Internal gRPC Protocol (Python AI -> Go Gateway)

Komunikasi antara Python AI Engine dan Go Gateway menggunakan gRPC dengan pengamanan mTLS.

**Proto Definition (`proto/signal.proto`):**
```protobuf
syntax = "proto3";
package signal;

service SignalService {
  rpc GetTradingSignal (SignalRequest) returns (SignalResponse);
  rpc StreamSignals (SignalRequest) returns (stream SignalResponse);
}

message SignalRequest {
  string asset = 1;
  string category = 2;
}

message SignalResponse {
  string id_signal = 1;
  int32 no = 2;
  string asset = 3;
  double price = 4;
  string action = 5;
  string type_action = 6;
  string type_signal = 7;
  double tp1 = 8;
  double tp2 = 9;
  double sl1 = 10;
  double sl2 = 11;
  double probability_pct = 12;
  double winrate_pct = 13;
  string reason = 14;
  string timestamp = 15;
}
```

## 2. Client WebSocket Protocol (Go Gateway -> User Frontend/App)

Saat running via Docker local, semua koneksi klien menggunakan WebSocket pada gateway port `8080`.

Endpoint local:

`ws://localhost:8080/ws?token=<JWT_TOKEN>`

Endpoint production dengan TLS terminator:

`wss://<your-domain>/ws?token=<JWT_TOKEN>`

### A. Authentication

- Klien wajib menyertakan JWT token yang valid di query parameter
- Server memverifikasi token sebelum upgrade koneksi
- Token invalid atau kadaluarsa akan ditolak dengan `401 Unauthorized`

### B. Heartbeat (Ping/Pong)

- Client sends: `{"type": "ping"}`
- Server responds: `{"type": "pong"}`

### C. Signal Push Event (Server to Client)

Setiap kali Go Gateway menerima sinyal dari AI Engine, payload akan di-broadcast ke klien yang terverifikasi dalam format JSON berikut:

```json
{
  "event": "new_signal",
  "data": {
    "id_signal": "sig-88392-btc",
    "asset": "BTC/USDT",
    "price": 64500.50,
    "action": "buy",
    "type_action": "market",
    "type_signal": "long",
    "tp1": 65000.00,
    "tp2": 66500.00,
    "sl1": 63000.00,
    "sl2": 62000.00,
    "probability_pct": 85.5,
    "winrate_pct": 78.2,
    "reason": "Momentum bullish terdeteksi dan sentimen pasar mendukung entry buy.",
    "timestamp": "2026-05-06T06:32:00Z"
  }
}
```

## 3. Rate Limiting (WebSocket)

Sistem menerapkan rate limiting berbasis User ID dan Paket Langganan:

- Free: `10/minute`
- Pro: `100/minute`
- Paket lain mengikuti konfigurasi `system_configs`

Jika batas terlampaui, server akan mengirimkan pesan error dan menutup koneksi sementara.

## 4. Runtime Docs

Gateway menyediakan docs runtime di:

- `/api/docs`
- `/api/docs/asyncapi.yaml`
- `/api/docs/postman.json`
- `/api/docs/markdown`
