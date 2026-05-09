package ws

import (
	"context"
	"fmt"
	"strconv"
	"strings"
	"time"

	"github.com/quantsync/quantsync-gateway/internal/database"
	"github.com/quantsync/quantsync-gateway/internal/config"
)

// RateLimiter handles token bucket logic per user using Redis.
type RateLimiter struct {
	ctx context.Context
}

func NewRateLimiter() *RateLimiter {
	return &RateLimiter{
		ctx: context.Background(),
	}
}

// Allow checks if a request is allowed for a given user and plan.
func (rl *RateLimiter) Allow(userID int64, plan string) (bool, error) {
	key := fmt.Sprintf("rate_limit:%d", userID)
	
	// Get limits from Config (loaded from TiDB to Redis)
	// Example key: RATE_LIMIT_FREE, RATE_LIMIT_PRO
	configKey := fmt.Sprintf("RATE_LIMIT_%s", strings.ToUpper(plan))
	limitStr := config.GetConfig(configKey)
	if limitStr == "" {
		limitStr = "10" // Default fallback
	}
	
	limit, _ := strconv.Atoi(limitStr)
	interval := 60 * time.Second // 1 minute interval

	// Token Bucket Logic via Lua Script for Atomicity
	script := `
		local key = KEYS[1]
		local limit = tonumber(ARGV[1])
		local interval = tonumber(ARGV[2])
		local now = tonumber(ARGV[3])

		local bucket = redis.call("HMGET", key, "tokens", "last_refill")
		local tokens = tonumber(bucket[1])
		local last_refill = tonumber(bucket[2])

		if tokens == nil then
			tokens = limit
			last_refill = now
		else
			local elapsed = now - last_refill
			local refill = math.floor(elapsed * (limit / interval))
			tokens = math.min(limit, tokens + refill)
			last_refill = now
		end

		if tokens >= 1 then
			tokens = tokens - 1
			redis.call("HMSET", key, "tokens", tokens, "last_refill", last_refill)
			redis.call("EXPIRE", key, interval)
			return 1
		else
			return 0
		end
	`

	res, err := database.RedisClient.Eval(rl.ctx, script, []string{key}, limit, interval.Seconds(), time.Now().Unix()).Result()
	if err != nil {
		return false, err
	}

	return res.(int64) == 1, nil
}
