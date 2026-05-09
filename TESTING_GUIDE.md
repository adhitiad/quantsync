# QuantSync Testing Guide

Dokumen ini menjelaskan cara melakukan pengujian (testing) pada sistem QuantSync menggunakan Postman.

## 1. Pengujian WebSocket (WSS)

Sistem QuantSync menggunakan WebSocket Secure (WSS) untuk streaming sinyal real-time.

### Langkah-langkah:
1. **Import Collection:**
   - Buka aplikasi Postman.
   - Klik tombol **Import** di pojok kiri atas.
   - Pilih file `quantsync_postman_collection.json` dari root directory proyek ini.
2. **Konfigurasi Variabel:**
   - Setelah di-import, klik pada tab **Variables** di level collection.
   - Masukkan token JWT yang valid ke kolom `Current Value` pada variabel `jwt_token`.
3. **Melakukan Koneksi:**
   - Pilih request **WSS Signal Stream**.
   - Pastikan URL mengarah ke `wss://localhost:8443/ws?token={{jwt_token}}`.
   - Klik **Connect**.
   - Jika berhasil, Anda akan melihat status `Connected` dan mulai menerima pesan `new_signal` saat ada aktivitas di AI Engine.

---

## 2. Pengujian gRPC (Python AI Engine Simulator)

Developer dapat menggunakan Postman untuk mensimulasikan Python AI Engine yang mengirimkan sinyal ke Go Gateway via gRPC.

### Langkah-langkah:
1. **Buat Request gRPC Baru:**
   - Di Postman, klik **New** -> **gRPC Request**.
2. **Masukkan URL Server:**
   - Masukkan `localhost:50051`.
3. **Import Protobuf Definition:**
   - Klik tab **Service Definition**.
   - Pilih **Import a .proto file**.
   - Cari dan pilih file `proto/signal.proto`.
   - Postman akan memuat service `quantsync.SignalService`.
4. **Pilih Method:**
   - Pilih method `PushSignal` dari dropdown.
5. **Konfigurasi TLS (mTLS):**
   - Karena Gateway menggunakan mTLS, klik tab **Settings** pada request.
   - Aktifkan **Enable SSL/TLS**.
   - Di bagian **Certificates**, tambahkan sertifikat client:
     - **CRT file:** `certs/client.crt`
     - **Key file:** `certs/client.key`
6. **Kirim Payload Mock:**
   - Masukkan JSON payload berikut di tab **Message**:
     ```json
     {
       "id_signal": "mock-sig-001",
       "asset": "BTC/USDT",
       "type_signal": "Long",
       "type_action": "Market",
       "action": "BUY",
       "price": 64000.50,
       "tp1": 65000.00,
       "tp2": 66000.00,
       "sl1": 63000.00,
       "sl2": 62500.00,
       "probability_pct": 88.5,
       "winrate_pct": 75.2,
       "reason": "Simulated signal from Postman for integration testing.",
       "timestamp_utc": "2026-05-06T06:40:00Z"
     }
     ```
   - Klik **Invoke**.
   - Gateway akan menerima sinyal ini dan mem-broadcast-nya ke semua klien WebSocket yang terkoneksi.

---

## 3. Troubleshooting
- **Handshake Error:** Pastikan sertifikat mTLS sudah di-generate (`scripts/gen_certs.sh`) dan di-mount dengan benar di Docker.
- **Unauthorized (401):** Periksa kembali apakah `JWT_SECRET` di database cocok dengan token yang Anda gunakan di Postman.
