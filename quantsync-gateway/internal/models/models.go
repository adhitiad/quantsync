package models

import (
	"time"
)

type User struct {
	ID                  int64     `gorm:"primaryKey"                             json:"id"`
	Username            string    `gorm:"unique;not null"                        json:"username"`
	Email               string    `gorm:"unique;not null"                        json:"email"`
	PasswordHash        string    `gorm:"not null"                               json:"-"`
	Role                string    `gorm:"type:varchar(20);default:'user'"        json:"role"`
	TelegramID          string    `                                              json:"telegram_id"`
	WhatsAppNumber      string    `                                              json:"whatsapp_number"`
	NotificationEnabled bool      `gorm:"default:false"                          json:"notification_enabled"`
	CreatedAt           time.Time `                                              json:"created_at"`
	UpdatedAt           time.Time `                                              json:"updated_at"`
}

type Subscription struct {
	ID        int64      `gorm:"primaryKey"                             json:"id"`
	UserID    int64      `gorm:"not null"                               json:"user_id"`
	Plan      string     `gorm:"type:varchar(40);default:'free'"        json:"plan"`
	Status    string     `gorm:"type:varchar(20);default:'active'"      json:"status"`
	ExpiresAt *time.Time `                                              json:"expires_at"`
	CreatedAt time.Time  `                                              json:"created_at"`
	UpdatedAt time.Time  `                                              json:"updated_at"`
}

type SystemConfig struct {
	Key         string    `gorm:"primaryKey;column:key;type:varchar(100)" json:"key"`
	Value       string    `gorm:"column:value;type:text"                  json:"value"`
	Description string    `gorm:"column:description"                      json:"description"`
	UpdatedAt   time.Time `gorm:"column:updated_at"                       json:"updated_at"`
}

type SignalHistory struct {
	IDSignal       string    `gorm:"primaryKey"                            json:"id_signal"`
	No             int       `                                             json:"no"`
	Category       string    `gorm:"type:varchar(20);not null"             json:"category"`
	Asset          string    `                                             json:"asset"`
	Price          float64   `                                             json:"price"`
	Action         string    `                                             json:"action"`
	TypeAction     string    `                                             json:"type_action"`
	TypeSignal     string    `                                             json:"type_signal"`
	TP1            float64   `                                             json:"tp1"`
	TP2            float64   `                                             json:"tp2"`
	SL1            float64   `                                             json:"sl1"`
	SL2            float64   `                                             json:"sl2"`
	ProbabilityPct float64   `                                             json:"probability_pct"`
	WinratePct     float64   `                                             json:"winrate_pct"`
	Reason         string    `                                             json:"reason"`
	Timestamp      time.Time `gorm:"index:idx_sig_asset_ts"                json:"timestamp"`
	// FIX: tambah index untuk query signal per asset
	Asset2         string `gorm:"-"`
}

// MarketData — FIX: sinkronisasi dengan schema Python (supabase_store.py)
//
// Python migration menambahkan:
//   - Kolom   : timeframe VARCHAR(10) NOT NULL DEFAULT 'H1'
//   - Unique  : (asset, timeframe, timestamp) — constraint uq_asset_timeframe_ts
//   - Index   : idx_asset_tf_ts(asset, timeframe, timestamp)
//   - Hapus   : idx_asset_ts (sudah tidak relevan)
//
// GORM AutoMigrate bersifat ADDITIVE — tidak akan drop kolom/index lama.
// Pastikan migration Python sudah dijalankan SEBELUM gateway naik
// agar idx_asset_ts lama tidak berkonflik.
//
// Jika idx_asset_ts perlu di-drop manual:
//   DROP INDEX IF EXISTS idx_asset_ts;
type MarketData struct {
	ID       int64  `gorm:"primaryKey"                                           json:"id"`
	Category string `gorm:"type:varchar(20);not null"                            json:"category"`

	// FIX: hapus tag idx_asset_ts (index lama, sudah diganti Python)
	// Tambah composite unique index yang match dengan Python constraint
	Asset string `gorm:"not null;uniqueIndex:uq_asset_timeframe_ts,composite:asset_tf_ts" json:"asset"`

	// FIX: field baru — wajib ada agar query Go tidak ambigu antara H1 dan M15
	Timeframe string `gorm:"type:varchar(10);not null;default:'H1';uniqueIndex:uq_asset_timeframe_ts,composite:asset_tf_ts" json:"timeframe"`

	Open   float64 `json:"open"`
	High   float64 `json:"high"`
	Low    float64 `json:"low"`
	Close  float64 `json:"close"`
	Volume float64 `json:"volume"`

	// FIX: update index name ke idx_asset_tf_ts (match Python)
	Timestamp time.Time `gorm:"not null;uniqueIndex:uq_asset_timeframe_ts,composite:asset_tf_ts;index:idx_asset_tf_ts" json:"timestamp"`
}

// TableName eksplisit — hindari GORM pluralize jadi "market_data_s"
func (MarketData) TableName() string    { return "market_data" }
func (SignalHistory) TableName() string { return "signal_histories" }
func (SystemConfig) TableName() string  { return "system_configs" }
