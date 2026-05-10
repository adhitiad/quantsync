# QuantSync — Critical Fixes Summary

## File yang Diubah

| File | Fix |
|------|-----|
| `quantsync-ai-engine/ingestion/dukascopy_ingestor.py` | Critical #1: Isolated SSL/Session |
| `quantsync-ai-engine/storage/supabase_store.py`       | Critical #2: Upsert + Bulk Insert + Kolom `timeframe` |
| `quantsync-ai-engine/server.py`                       | Critical #3: mTLS tidak silent fallback + Winrate deterministik + Asset cache |
| `quantsync-notifier/main.py`                          | Critical #4: Async Redis pubsub |

---

## Breaking Changes

### 1. Schema Migration (otomatis dijalankan saat startup)
`supabase_store.py` sekarang menjalankan migration idempotent saat init:
- Tambah kolom `timeframe VARCHAR(10) DEFAULT 'H1'`
- Tambah unique constraint `(asset, timeframe, timestamp)`
- Rebuild index `idx_asset_tf_ts`

Tidak perlu manual migration jika menggunakan Docker Compose (migration jalan otomatis).

### 2. `save_ohlcv` Signature Berubah
```python
# Sebelum
db.save_ohlcv(category, asset, df)

# Sesudah — wajib tambah timeframe
db.save_ohlcv(category, asset, df, timeframe="H1")  # default "H1" jika tidak diisi
```

### 3. `REQUIRED_FOREX_ASSETS` perlu field `category`
Di `runtime_assets.py`, tiap entry forex sekarang butuh field `category`:
```python
REQUIRED_FOREX_ASSETS = [
    {"name": "EUR/USD", "inst": "EUR/USD", "category": "forex"},
    {"name": "GBP/USD", "inst": "GBP/USD", "category": "forex"},
    {"name": "XAU/USD", "inst": "XAU/USD", "category": "forex"},
]
```

### 4. `.env` Perlu Tambah `APP_ENV`
```env
# production = enforce mTLS (crash jika cert tidak ada)
# development = warn saja, izinkan insecure (default jika tidak diset)
APP_ENV=production
```

---

## Dependency Tambahan

### quantsync-ai-engine (requirements.txt)
```
# Tidak ada tambahan dependency baru
# sqlalchemy[asyncio] sudah include pg_insert
# Pastikan sqlalchemy >= 1.4 untuk on_conflict_do_nothing()
sqlalchemy>=2.0.0
psycopg[binary]>=3.0.0
```

### quantsync-notifier (requirements.txt)
```diff
- redis==5.0.1
+ redis[asyncio]>=5.0.0    # redis.asyncio sudah built-in di v4+
+ aiohttp>=3.9.0            # untuk async email via Postal
```

---

## Test Checklist

### Critical #1 — SSL Isolation
```bash
# Tidak ada lagi log ini setelah fix:
# "Patching socket.getaddrinfo globally"
# Verifikasi: grep "socket.getaddrinfo" logs → tidak ada
docker compose logs quantsync-ai-engine | grep -i "socket\|ssl_bypass"
```

### Critical #2 — No Duplicate
```sql
-- Jalankan ingestor 2x, cek row count tidak berlipat
SELECT asset, timeframe, COUNT(*) FROM market_data GROUP BY asset, timeframe;

-- Cek constraint ada
SELECT constraint_name FROM information_schema.table_constraints
WHERE table_name = 'market_data' AND constraint_type = 'UNIQUE';
```

### Critical #3 — mTLS Enforcement
```bash
# Test production mode tanpa cert → harus exit 1
APP_ENV=production python server.py  # tanpa folder certs/

# Test development mode → warn tapi tetap jalan
APP_ENV=development python server.py  # tanpa folder certs/
```

### Critical #4 — Async Notifier
```bash
# Publish test message ke Redis
redis-cli PUBLISH signal_events '{"asset":"BTC/USDT","action":"buy","type_signal":"long","price":65000,"tp1":66000,"tp2":67000,"sl1":64000,"winrate_pct":75,"reason":"Test","timestamp":"2025-01-01T00:00:00Z"}'

# Cek notifier menerima tanpa hang
docker compose logs -f quantsync-notifier
```
