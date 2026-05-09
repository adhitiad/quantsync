package config

import (
	"context"
	"log"

	"github.com/quantsync/quantsync-gateway/internal/database"
	"github.com/quantsync/quantsync-gateway/internal/models"
)

var ctx = context.Background()

// LoadConfigsToRedis fetches all configurations from Supabase and stores them in Redis.
func LoadConfigsToRedis() {
	var configs []models.SystemConfig

	// Fetch from Supabase
	result := database.DB.Find(&configs)
	if result.Error != nil {
		log.Printf("Error fetching configs from Supabase: %v", result.Error)
		return
	}

	// Store in Redis
	for _, cfg := range configs {
		err := database.RedisClient.Set(ctx, "config:"+cfg.Key, cfg.Value, 0).Err()
		if err != nil {
			log.Printf("Error storing config %s in Redis: %v", cfg.Key, err)
		}
	}

	log.Printf("Successfully loaded %d configurations to Redis", len(configs))
}

// GetConfig retrieves a config value from Redis.
func GetConfig(key string) string {
	if database.RedisClient == nil {
		return ""
	}

	val, err := database.RedisClient.Get(ctx, "config:"+key).Result()
	if err != nil {
		// Fallback or handle error
		return ""
	}
	return val
}
