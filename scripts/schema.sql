-- Schema for AI Trading Signal Hub (TiDB)

-- 1. Users Table
CREATE TABLE IF NOT EXISTS users (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('user', 'admin', 'superadmin') DEFAULT 'user',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- 2. Subscriptions Table
CREATE TABLE IF NOT EXISTS subscriptions (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    plan ENUM('free', 'plus', 'pro', 'enterprise_pay_as_you_go') DEFAULT 'free',
    status ENUM('active', 'expired', 'cancelled') DEFAULT 'active',
    expires_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 3. SystemConfigs Table (Replacement for .env)
CREATE TABLE IF NOT EXISTS system_configs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    config_key VARCHAR(100) NOT NULL UNIQUE,
    config_value TEXT NOT NULL,
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- 4. SignalHistory Table (Unified for Crypto & Forex)
CREATE TABLE IF NOT EXISTS signal_history (
    id_signal VARCHAR(100) PRIMARY KEY,
    no INT NOT NULL,
    category ENUM('crypto', 'forex') NOT NULL,
    asset VARCHAR(20) NOT NULL,
    price DECIMAL(20, 8) NOT NULL,
    action VARCHAR(10) NOT NULL, -- 'buy' for crypto, 'buy/sell' for forex
    type_action VARCHAR(20) NOT NULL, -- limit/stop/market/hold
    type_signal VARCHAR(10) DEFAULT 'long', -- 'long' for crypto, dynamic for forex if needed
    tp1 DECIMAL(20, 8),
    tp2 DECIMAL(20, 8),
    sl1 DECIMAL(20, 8),
    sl2 DECIMAL(20, 8),
    probability_pct DECIMAL(5, 2),
    winrate_pct DECIMAL(5, 2),
    reason TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Seed Initial System Configs (Placeholder for required API Keys)
INSERT INTO system_configs (config_key, config_value, description) VALUES 
('REDIS_ADDR', 'localhost:6379', 'Redis Server Address'),
('TIDB_DSN', 'root@tcp(127.0.0.1:4000)/quantsync?charset=utf8mb4&parseTime=True&loc=Local', 'TiDB Connection String'),
('TELEGRAM_BOT_TOKEN', '', 'Telegram Bot API Token'),
('TELEGRAM_CHAT_ID', '', 'Telegram Chat/Channel ID for Notifications'),
('POSTAL_API_KEY', '', 'Postal Email Server API Key'),
('WHATSAPP_WEBHOOK_URL', '', 'WhatsApp Webhook Endpoint');
