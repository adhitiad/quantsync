package notifier

import (
	"fmt"
	"log"
	"strings"
	"time"

	"github.com/quantsync/quantsync-gateway/internal/database"
	"github.com/quantsync/quantsync-gateway/internal/models"
	"github.com/quantsync/quantsync-gateway/internal/utils"
)

// NotificationManager handles multi-channel notifications
type NotificationManager struct {
	Telegram *TelegramNotifier
	WhatsApp *WhatsAppNotifier
	Email    *EmailNotifier
}

var Instance *NotificationManager

// InitNotifier initializes all notification channels using database configurations
func InitNotifier() {
	var configs []models.SystemConfig
	if err := database.DB.Find(&configs).Error; err != nil {
		log.Fatalf("Failed to load system configs for notifier: %v", err)
	}

	configMap := make(map[string]string)
	for _, c := range configs {
		configMap[c.Key] = c.Value
	}

	Instance = &NotificationManager{
		Telegram: NewTelegramNotifier(configMap["TELEGRAM_BOT_TOKEN"]),
		WhatsApp: NewWhatsAppNotifier(),
		Email:    NewEmailNotifier(configMap),
	}

	log.Println("✅ Notification service initialized with database configs")
}

// DispatchSignalToUsers scans active users and dispatches signals parallelly
func DispatchSignalToUsers(signal models.SignalHistory) {
	var users []models.User
	// Get users with notifications enabled
	if err := database.DB.Where("notification_enabled = ?", true).Find(&users).Error; err != nil {
		log.Printf("❌ Error fetching users for signal dispatch: %v", err)
		return
	}

	for _, user := range users {
		// Asynchronous delivery to avoid blocking the main stream
		go func(u models.User) {
			msg := FormatSignalMessage(signal)

			if u.TelegramID != "" {
				go Instance.Telegram.Send(u.TelegramID, msg)
			}
			if u.WhatsAppNumber != "" {
				go Instance.WhatsApp.Send(u.WhatsAppNumber, msg)
			}
			if u.Email != "" {
				go Instance.Email.Send(u.Email, msg)
			}
		}(user)
	}
}

// FormatSignalMessage prepares an elegant message in Asia/Jakarta timezone with QuantFund standards
func FormatSignalMessage(signal models.SignalHistory) string {
	loc, _ := time.LoadLocation(utils.ZoneJakarta)
	wibTime := signal.Timestamp.In(loc).Format("15:04 WIB, 02 Jan 2006")

	// Normalisasi Data
	typeSignal := toTitleCase(signal.TypeSignal)
	typeAction := toTitleCase(signal.TypeAction)
	action := strings.ToUpper(signal.Action)

	actionEmoji := "🚀"
	if strings.ToLower(signal.Action) == "sell" {
		actionEmoji = "📉"
	}

	return fmt.Sprintf(
		"🔔 *[QuantSync AI Signal]* 🔔\n"+
			"📈 Asset: %s | %s\n"+
			"⚙️ Order Type: %s\n"+
			"⚡ Action: %s %s @ %s\n\n"+
			"🎯 TP 1: %s\n"+
			"🎯 TP 2: %s\n"+
			"🛑 SL 1: %s\n"+
			"🛑 SL 2: %s\n\n"+
			"📊 Probabilitas: %.1f%%\n"+
			"🧠 Analisis: %s\n"+
			"⏱ Waktu: %s",
		signal.Asset, typeSignal,
		typeAction,
		action, actionEmoji, formatFloat(signal.Price),
		formatFloat(signal.TP1), formatFloat(signal.TP2),
		formatFloat(signal.SL1), formatFloat(signal.SL2),
		signal.WinratePct,
		signal.Reason,
		wibTime,
	)
}

// formatFloat converts float64 to string without scientific notation and trims trailing zeros
func formatFloat(f float64) string {
	s := fmt.Sprintf("%.8f", f)
	return strings.TrimRight(strings.TrimRight(s, "0"), ".")
}

// toTitleCase converts first letter to uppercase
func toTitleCase(s string) string {
	if len(s) == 0 {
		return s
	}
	return strings.ToUpper(s[:1]) + strings.ToLower(s[1:])
}
