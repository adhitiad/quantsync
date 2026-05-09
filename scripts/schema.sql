-- Schema for AI Trading Signal Hub (Supabase Postgres)

-- 1. Users Table
CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) DEFAULT 'user' CHECK (role IN ('user', 'admin', 'superadmin')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Subscriptions Table
CREATE TABLE IF NOT EXISTS subscriptions (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    plan VARCHAR(40) DEFAULT 'free' CHECK (plan IN ('free', 'plus', 'pro', 'enterprise_pay_as_you_go')),
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'expired', 'cancelled')),
    expires_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 3. SystemConfigs Table (Replacement for .env)
CREATE TABLE IF NOT EXISTS system_configs (
    "key" VARCHAR(100) PRIMARY KEY,
    "value" TEXT NOT NULL,
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. SignalHistory Table (Unified for Crypto & Forex)
CREATE TABLE IF NOT EXISTS signal_histories (
    id_signal VARCHAR(100) PRIMARY KEY,
    no INT NOT NULL,
    category VARCHAR(20) NOT NULL CHECK (category IN ('crypto', 'forex')),
    asset VARCHAR(20) NOT NULL,
    price NUMERIC(20, 8) NOT NULL,
    action VARCHAR(10) NOT NULL, -- 'buy' for crypto, 'buy/sell' for forex
    type_action VARCHAR(20) NOT NULL, -- limit/stop/market/hold
    type_signal VARCHAR(10) DEFAULT 'long', -- 'long' for crypto, dynamic for forex if needed
    tp1 NUMERIC(20, 8),
    tp2 NUMERIC(20, 8),
    sl1 NUMERIC(20, 8),
    sl2 NUMERIC(20, 8),
    probability_pct NUMERIC(5, 2),
    winrate_pct NUMERIC(5, 2),
    reason TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Seed Initial System Configs (Placeholder for required API Keys)
INSERT INTO system_configs ("key", "value", description) VALUES
('REDIS_ADDR', 'localhost:6379', 'Redis Server Address'),
('DATABASE_URL', 'postgresql://postgres.YOUR_PROJECT_REF:YOUR_PASSWORD@aws-1-us-east-1.pooler.supabase.com:5432/postgres?sslmode=require', 'Supabase Postgres Connection String'),
('TELEGRAM_BOT_TOKEN', '', 'Telegram Bot API Token'),
('TELEGRAM_CHAT_ID', '', 'Telegram Chat/Channel ID for Notifications'),
('POSTAL_API_KEY', '', 'Postal Email Server API Key'),
('WHATSAPP_WEBHOOK_URL', '', 'WhatsApp Webhook Endpoint')
ON CONFLICT ("key") DO UPDATE SET
    "value" = EXCLUDED."value",
    description = EXCLUDED.description,
    updated_at = CURRENT_TIMESTAMP;
