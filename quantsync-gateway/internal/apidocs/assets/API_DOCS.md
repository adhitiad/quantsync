# QuantSync API & Protocol Documentation

Dokumentasi ini menjelaskan protokol komunikasi internal dan eksternal dalam ekosistem QuantSync. REST API dinonaktifkan secara total untuk alasan keamanan dan performa real-time.

## 1. Internal gRPC Protocol (Python AI -> Go Gateway)

Komunikasi antara Python AI Engine (Brain) dan Go Gateway menggunakan gRPC dengan pengamanan mTLS (Mutual TLS).

## 2. Client WebSocket Protocol (Go Gateway -> User Frontend/App)

Semua koneksi klien menggunakan WebSocket Secure (WSS).

Endpoint local: `ws://localhost:8080/ws?token=<JWT_TOKEN>`

Endpoint production: `wss://<your-domain>/ws?token=<JWT_TOKEN>`

### Authentication

- Klien wajib menyertakan JWT token yang valid di query parameter saat melakukan handshake.
- Jika token invalid atau kadaluarsa, koneksi akan ditolak dengan status 401.

### Heartbeat

- Client sends: `{"type": "ping"}`
- Server responds: `{"type": "pong"}`

### Signal Push Event

Server akan mengirim payload event `new_signal` saat sinyal baru tersedia.

## 3. Runtime Docs

- AsyncAPI spec: `/api/docs/asyncapi.yaml`
- Postman collection: `/api/docs/postman.json`
- Markdown docs: `/api/docs/markdown`
