package notifier

import (
	"context"
	"encoding/json"
	"log"

	"github.com/quantsync/quantsync-gateway/internal/database"
	"github.com/quantsync/quantsync-gateway/internal/models"
)


func StartNotifierWorker() {
	// Initialize notifiers from database configs
	InitNotifier()

	ctx := context.Background()
	pubsub := database.RedisClient.Subscribe(ctx, "signal_events")

	log.Println("✅ Notifier Worker started, listening to Redis: signal_events")

	ch := pubsub.Channel()

	for msg := range ch {
		var signal models.SignalHistory
		if err := json.Unmarshal([]byte(msg.Payload), &signal); err != nil {
			log.Printf("❌ Error unmarshaling signal event: %v", err)
			continue
		}

		// Parallel dispatch to all registered users
		log.Printf("📢 Dispatching signal for %s...", signal.Asset)
		go DispatchSignalToUsers(signal)
	}
}
