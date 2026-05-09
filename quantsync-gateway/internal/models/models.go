package models

import (
	"time"
)

type User struct {
	ID                  int64     `gorm:"primaryKey" json:"id"`
	Username            string    `gorm:"unique;not null" json:"username"`
	Email               string    `gorm:"unique;not null" json:"email"`
	PasswordHash        string    `gorm:"not null" json:"-"`
	Role                string    `gorm:"type:varchar(20);default:'user'" json:"role"`
	TelegramID          string    `json:"telegram_id"`
	WhatsAppNumber      string    `json:"whatsapp_number"`
	NotificationEnabled bool      `gorm:"default:false" json:"notification_enabled"`
	CreatedAt           time.Time `json:"created_at"`
	UpdatedAt           time.Time `json:"updated_at"`
}

type Subscription struct {
	ID        int64      `gorm:"primaryKey" json:"id"`
	UserID    int64      `gorm:"not null" json:"user_id"`
	Plan      string     `gorm:"type:varchar(40);default:'free'" json:"plan"`
	Status    string     `gorm:"type:varchar(20);default:'active'" json:"status"`
	ExpiresAt *time.Time `json:"expires_at"`
	CreatedAt time.Time  `json:"created_at"`
	UpdatedAt time.Time  `json:"updated_at"`
}

type SystemConfig struct {
	Key         string    `gorm:"primaryKey;column:key;type:varchar(100)" json:"key"`
	Value       string    `gorm:"column:value;type:text" json:"value"`
	Description string    `gorm:"column:description" json:"description"`
	UpdatedAt   time.Time `gorm:"column:updated_at" json:"updated_at"`
}

type SignalHistory struct {
	IDSignal       string    `gorm:"primaryKey" json:"id_signal"`
	No             int       `json:"no"`
	Category       string    `gorm:"type:varchar(20);not null" json:"category"`
	Asset          string    `json:"asset"`
	Price          float64   `json:"price"`
	Action         string    `json:"action"`
	TypeAction     string    `json:"type_action"`
	TypeSignal     string    `json:"type_signal"`
	TP1            float64   `json:"tp1"`
	TP2            float64   `json:"tp2"`
	SL1            float64   `json:"sl1"`
	SL2            float64   `json:"sl2"`
	ProbabilityPct float64   `json:"probability_pct"`
	WinratePct     float64   `json:"winrate_pct"`
	Reason         string    `json:"reason"`
	Timestamp      time.Time `json:"timestamp"`
}

type MarketData struct {
	ID        int64     `gorm:"primaryKey" json:"id"`
	Category  string    `gorm:"type:varchar(20);not null" json:"category"`
	Asset     string    `gorm:"index:idx_asset_ts;not null" json:"asset"`
	Open      float64   `json:"open"`
	High      float64   `json:"high"`
	Low       float64   `json:"low"`
	Close     float64   `json:"close"`
	Volume    float64   `json:"volume"`
	Timestamp time.Time `gorm:"index:idx_asset_ts;not null" json:"timestamp"`
}
