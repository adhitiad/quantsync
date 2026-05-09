package database

import (
	"context"
	"log"

	"github.com/redis/go-redis/v9"
)

var (
	RedisClient *redis.Client
	ctx         = context.Background()
)

// InitRedis initializes the Redis client using a URL or fallback address.
func InitRedis(urlStr string) *redis.Client {
	opt, err := redis.ParseURL(urlStr)
	if err != nil {
		log.Printf("⚠️  Invalid Redis URL (%s), falling back to basic addr: %v", urlStr, err)
		opt = &redis.Options{
			Addr: urlStr,
		}
	}

	RedisClient = redis.NewClient(opt)

	_, err = RedisClient.Ping(ctx).Result()
	if err != nil {
		log.Fatalf("❌ Failed to connect to Redis at %s: %v", urlStr, err)
	}

	log.Printf("✅ Connected to Redis successfully (%s)", opt.Addr)
	return RedisClient
}

func PingRedis(ctx context.Context) error {
	if RedisClient == nil {
		return redis.ErrClosed
	}
	return RedisClient.Ping(ctx).Err()
}
