# QuantSync

QuantSync adalah stack trading signal real-time dengan arsitektur:

- `quantsync-ai-engine` untuk ingest `crypto` dan `forex`, analisis, dan gRPC signal source
- `quantsync-gateway` untuk WebSocket gateway, health endpoint, docs endpoint, dan fan-out ke client
- `quantsync-notifier` untuk publish notifikasi dari event Redis
- `Supabase Postgres` sebagai primary database
- `Redis` sebagai cache, pub/sub, dan rate limiting

## Arsitektur

```mermaid
graph TD
    RSS[Scraper RSS/Berita] --> VectorDB[(Vector DB)]
    DDG[Search Sentiment] --> VectorDB
    VectorDB --> AI[quantsync-ai-engine]
    AI --> PPO[PPO / Rules]
    AI --> LSTM[LSTM / Features]

    AI <== gRPC + mTLS ==> Gateway[quantsync-gateway]

    Gateway --> Supabase[(Supabase Postgres)]
    Gateway --> Redis[(Redis)]
    Gateway <== WebSocket ==> Client[Frontend / Trader]

    Redis --> Notifier[quantsync-notifier]
```

## Yang Sudah Tersedia

- Runtime docs di `/api/docs`
- Raw AsyncAPI spec di `/api/docs/asyncapi.yaml`
- Postman collection di `/api/docs/postman.json`
- Gateway health di `/health`
- AI engine health internal di port `8081`
- Runtime warmup untuk memastikan minimal ada data `crypto` dan `forex`

## Target Environment

README ini mendukung dua mode utama:

- local development di Windows
- deployment manual di EC2 Amazon Linux

Untuk EC2, jalur yang direkomendasikan adalah Amazon Linux 2023.

## Prasyarat

Sebelum mulai, pastikan ini tersedia:

1. Docker Desktop atau Docker daemon aktif
2. Akses internet untuk Supabase, Redis, dan sumber market data
3. File `.env` di root proyek
4. Sertifikat mTLS di folder `certs/`

### Windows Local

- Windows 10/11
- Docker Desktop aktif
- Git opsional untuk clone repository

### EC2 Amazon Linux

- EC2 instance dengan outbound internet
- Security Group minimal membuka:
  - `22/tcp` untuk SSH
  - `8080/tcp` untuk gateway HTTP dan docs
  - `50051/tcp` hanya jika memang perlu expose gRPC dari luar
- domain dan reverse proxy opsional kalau ingin `wss://`

## Konfigurasi Environment

1. Salin `.env.example` menjadi `.env`
2. Isi minimal variabel ini:

```env
DATABASE_URL=postgresql://postgres.YOUR_PROJECT_REF:YOUR_PASSWORD@aws-1-us-east-1.pooler.supabase.com:5432/postgres?sslmode=require
WSS_PORT=8080
GRPC_PORT=50051
JWT_SECRET=your_local_jwt_secret
NVIDIA_API_KEY=your_nvidia_api_key
```

Catatan:

- `DATABASE_URL` wajib mengarah ke Supabase Postgres
- `REDIS_URL` untuk Docker sudah diatur dari `docker-compose.yml`
- token Telegram, WhatsApp, SMTP, dan secret lain dibaca dari tabel `system_configs`

## Sertifikat mTLS

Kalau folder `certs/` belum ada atau belum lengkap, generate dulu:

```bash
bash scripts/gen_certs.sh
```

Minimal file ini harus ada:

- `certs/ca.crt`
- `certs/server.crt`
- `certs/server.key`
- `certs/client.crt`
- `certs/client.key`

## Jalur 1: Menjalankan Di Local Windows

### 1. Pastikan Docker aktif

Di Windows, buka Docker Desktop sampai statusnya `Running`.

### 2. Jalankan stack

```bash
docker compose up -d --build
```

Service yang akan naik:

- `redis`
- `quantsync-ai-engine`
- `quantsync-gateway`
- `quantsync-notifier`

### 3. Tunggu healthcheck hijau

Cek status:

```bash
docker compose ps
```

Yang diharapkan:

- `redis` sehat
- `quantsync-ai-engine` sehat
- `quantsync-gateway` sehat

Kalau `quantsync-ai-engine` masih `starting`, itu normal saat warmup. Engine sedang menunggu:

- koneksi Supabase siap
- minimal satu aset `crypto` punya data cukup
- minimal satu aset `forex` punya data cukup

### 4. Cek endpoint health

Gateway:

```bash
curl http://localhost:8080/health
```

Hasil sehat:

```text
ok
```

### 5. Buka API docs

Di browser:

```text
http://localhost:8080/api/docs
```

Di sana ada:

- ringkasan endpoint runtime
- link download AsyncAPI
- link download Postman collection
- preview docs markdown

### 6. Verifikasi WebSocket runtime

Endpoint utama client:

```text
ws://localhost:8080/ws?token=YOUR_JWT_TOKEN
```

Kalau kamu pakai TLS terminator/reverse proxy di depan gateway, endpoint-nya menjadi:

```text
wss://your-domain/ws?token=YOUR_JWT_TOKEN
```

### 7. Verifikasi data `crypto` dan `forex`

Saat startup, worker AI engine akan:

- ingest `crypto`: `BTC/USDT`, `BTC/USDC`, `ETH/USDT`, `ETH/USDC`, `SOL/USDT`, `SOL/USDC`, `BNB/USDT`, `BNB/USDC`
- ingest `forex`: `EUR/USD`, `GBP/USD`, `XAU/USD`

Kalau gateway sehat tetapi stream masih belum ada signal, cek log:

```bash
docker compose logs -f quantsync-ai-engine
docker compose logs -f quantsync-gateway
```

### 8. Stop service local

```bash
docker compose down
```

## Jalur 2: Menjalankan Di EC2 Amazon Linux

### 1. Launch instance

Gunakan Amazon Linux 2023 bila memungkinkan.

Catatan:

- AWS menyebut `docker`, `containerd`, dan `nerdctl` tersedia di repository inti AL2023.
- Pada AL2, paket container dulu banyak dipasang lewat `amazon-linux-extras`, jadi langkahnya memang berbeda.

### 2. SSH ke instance

```bash
ssh -i your-key.pem ec2-user@YOUR_EC2_PUBLIC_IP
```

### 3. Install Docker di Amazon Linux 2023

```bash
sudo dnf update -y
sudo dnf install -y docker git
sudo systemctl enable --now docker
sudo usermod -aG docker ec2-user
newgrp docker
```

### 4. Install Docker Compose plugin

```bash
sudo dnf install -y docker-compose-plugin
docker compose version
```

### 5. Clone project

```bash
git clone <REPO_URL>
cd quantsync
```

### 6. Siapkan environment

```bash
cp .env.example .env
```

Lalu isi minimal:

```env
DATABASE_URL=postgresql://postgres.YOUR_PROJECT_REF:YOUR_PASSWORD@aws-1-us-east-1.pooler.supabase.com:5432/postgres?sslmode=require
WSS_PORT=8080
GRPC_PORT=50051
JWT_SECRET=your_ec2_jwt_secret
NVIDIA_API_KEY=your_nvidia_api_key
```

### 7. Siapkan sertifikat

Kalau sertifikat belum ada:

```bash
bash scripts/gen_certs.sh
```

### 8. Jalankan stack di EC2

```bash
docker compose up -d --build
```

### 9. Cek status

```bash
docker compose ps
curl http://localhost:8080/health
```

Kalau dari laptop:

```text
http://YOUR_EC2_PUBLIC_IP:8080/api/docs
ws://YOUR_EC2_PUBLIC_IP:8080/ws?token=YOUR_JWT_TOKEN
```

### 10. Lihat log jika warmup masih berjalan

```bash
docker compose logs -f quantsync-ai-engine
docker compose logs -f quantsync-gateway
docker compose logs -f quantsync-notifier
```

### 11. Restart dan stop di EC2

Restart:

```bash
docker compose restart
```

Stop:

```bash
docker compose down
```

## Jalur 3: Auto-Start Di EC2 Dengan systemd

Repo ini sekarang menyediakan helper script:

```bash
sudo bash scripts/install_systemd_service.sh
```

Default-nya script akan:

- memasang unit `quantsync-compose.service`
- memakai user login sekarang, biasanya `ec2-user`
- memakai direktori repo saat ini sebagai `WorkingDirectory`
- enable service saat boot

Kalau repo kamu ada di path lain atau user lain, bisa override:

```bash
sudo PROJECT_DIR=/opt/quantsync RUN_USER=ec2-user bash scripts/install_systemd_service.sh
```

Setelah terpasang:

```bash
sudo systemctl start quantsync-compose
sudo systemctl status quantsync-compose
```

Kalau instance reboot, service ini akan otomatis menjalankan:

```bash
docker compose up -d
```

Untuk stop manual:

```bash
sudo systemctl stop quantsync-compose
```

Untuk disable auto-start:

```bash
sudo systemctl disable quantsync-compose
```

## Alur Operasional Singkat

Urutan normalnya seperti ini:

1. `redis` siap
2. `quantsync-ai-engine` connect ke Supabase dan mulai worker
3. worker isi market data `crypto` dan `forex`
4. AI engine health berubah sehat
5. `quantsync-gateway` connect ke AI engine stream
6. gateway health berubah sehat
7. client connect ke `/ws`
8. notifier ikut membaca event dari Redis

## Dokumentasi Runtime

Endpoint docs yang bisa langsung dipakai:

- `/api/docs`
- `/api/docs/asyncapi.yaml`
- `/api/docs/postman.json`
- `/api/docs/markdown`

## Testing Dengan Postman

1. Import `quantsync_postman_collection.json`
2. Isi variable `jwt_token`
3. Ubah URL websocket ke:

```text
ws://localhost:8080/ws?token={{jwt_token}}
```

4. Connect
5. Kirim heartbeat payload:

```json
{"type":"ping"}
```

## Troubleshooting

### Gateway health merah

Periksa:

- `DATABASE_URL` valid
- Redis hidup
- AI engine sudah sehat

### AI engine lama di status `starting`

Periksa:

- Supabase bisa diakses
- sumber data `crypto` dan `forex` bisa diambil
- log warmup di `quantsync-ai-engine`

### WebSocket `401 Unauthorized`

Periksa JWT token dan secret signing.

### WebSocket `429 Rate limit exceeded`

Periksa plan user dan konfigurasi rate limit di `system_configs`.

### Docker tidak bisa jalan

Kalau muncul error soal `dockerDesktopLinuxEngine`, berarti Docker daemon belum aktif.

### EC2 tidak bisa dibuka dari luar

Periksa:

- Security Group membuka `8080/tcp`
- instance punya public IP atau Elastic IP
- proses gateway sudah `healthy`

### EC2 bisa `curl localhost:8080/health` tapi browser luar gagal

Biasanya masalah ada di:

- Security Group
- NACL atau firewall host
- akses hanya ke private subnet tanpa bastion atau reverse proxy

### Amazon Linux 2

Kalau kamu memakai AL2, langkah install Docker bisa berbeda dari AL2023. Jalur paling aman untuk repo ini tetap Amazon Linux 2023 agar cocok dengan instruksi README ini.

## Mode Lokal Tanpa Docker

Mode ini bisa, tapi jalurnya lebih panjang karena kamu harus menyalakan:

1. Redis
2. `quantsync-ai-engine/server.py`
3. `quantsync-gateway/main.go`
4. `quantsync-notifier/main.py`

Untuk workflow harian, jalur yang disarankan tetap:

```bash
docker compose up -d --build
```
