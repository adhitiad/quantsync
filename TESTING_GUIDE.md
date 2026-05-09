# QuantSync Testing Guide

Dokumen ini menjelaskan jalur testing yang sesuai dengan runtime sekarang.

## 1. Sebelum Testing

Pastikan stack sudah sehat:

1. Jalankan `docker compose up -d --build`
2. Cek `docker compose ps`
3. Pastikan `quantsync-ai-engine` dan `quantsync-gateway` sudah `healthy`
4. Cek `http://localhost:8080/api/docs`

## 2. Pengujian WebSocket Dengan Postman

QuantSync mendistribusikan sinyal lewat WebSocket pada gateway.

### Langkah-langkah

1. Import file `quantsync_postman_collection.json`
2. Isi variable `jwt_token`
3. Buka request `WSS Signal Stream`
4. Ubah URL menjadi `ws://localhost:8080/ws?token={{jwt_token}}`
5. Klik `Connect`
6. Setelah connected, kirim heartbeat:

```json
{"type":"ping"}
```

Kalau runtime sudah hangat dan sinyal tersedia, kamu akan menerima event `new_signal`.

## 3. Pengujian gRPC Ke AI Engine

Gunakan ini untuk mengetes AI engine secara langsung, bukan untuk mensimulasikan gateway lama.

### Langkah-langkah

1. Buat request gRPC baru di Postman
2. Target server: `localhost:50051`
3. Import `proto/signal.proto`
4. Pilih service `signal.SignalService`
5. Pilih salah satu method:

- `GetTradingSignal`
- `StreamSignals`

6. Aktifkan TLS/mTLS dan lampirkan:

- `certs/client.crt`
- `certs/client.key`

7. Untuk request tunggal, pakai payload contoh:

```json
{
  "asset": "BTC/USDT",
  "category": "crypto"
}
```

8. Untuk stream, gunakan:

```json
{
  "asset": "ALL",
  "category": ""
}
```

## 4. Pengujian Docs

Endpoint docs runtime:

- `http://localhost:8080/api/docs`
- `http://localhost:8080/api/docs/asyncapi.yaml`
- `http://localhost:8080/api/docs/postman.json`
- `http://localhost:8080/api/docs/markdown`

## 5. Troubleshooting

- `401 Unauthorized`: token JWT salah atau tidak valid
- `429 Rate limit exceeded`: plan user kena limiter
- AI engine lama `starting`: market data `crypto` atau `forex` belum cukup
- gRPC TLS error: cek isi folder `certs/`
