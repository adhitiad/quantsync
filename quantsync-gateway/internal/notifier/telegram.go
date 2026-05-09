package notifier

import (
	"fmt"
	"log"

	tgbotapi "github.com/go-telegram-bot-api/telegram-bot-api/v5"
)

type TelegramNotifier struct {
	Bot *tgbotapi.BotAPI
}

// NewTelegramNotifier initializes the Telegram Bot API client
func NewTelegramNotifier(token string) *TelegramNotifier {
	if token == "" {
		log.Println("⚠️ Telegram: Bot token is missing in system_configs, skipping init")
		return nil
	}

	bot, err := tgbotapi.NewBotAPI(token)
	if err != nil {
		log.Printf("❌ Telegram: Initialization failed: %v", err)
		return nil
	}

	log.Printf("✅ Telegram: Bot authorized on account %s", bot.Self.UserName)
	return &TelegramNotifier{Bot: bot}
}

// Send sends a message to a Telegram Chat ID or Username
func (t *TelegramNotifier) Send(chatID string, message string) error {
	if t.Bot == nil {
		return nil
	}

	var id int64
	_, err := fmt.Sscanf(chatID, "%d", &id)
	if err != nil {
		log.Printf("❌ Telegram: Invalid Chat ID format %s: %v", chatID, err)
		return err
	}

	msg := tgbotapi.NewMessage(id, message)
	msg.ParseMode = "Markdown" // Enable markdown for elegant formatting

	_, err = t.Bot.Send(msg)
	if err != nil {
		log.Printf("❌ Telegram: Failed to send message to %d: %v", id, err)
		return err
	}

	return nil
}
