package main

import (
	"context"
	"log"
	"net/http"
	"os"
	"time"

	"github.com/joho/godotenv"
	"github.com/quantsync/quantsync-gateway/internal/apidocs"
	"github.com/quantsync/quantsync-gateway/internal/auth"
	"github.com/quantsync/quantsync-gateway/internal/database"
	"github.com/quantsync/quantsync-gateway/internal/grpc"
	"github.com/quantsync/quantsync-gateway/internal/notifier"
	"github.com/quantsync/quantsync-gateway/internal/ws"
)

func main() {
	// Load .env file
	if err := godotenv.Load("../.env"); err != nil {
		log.Println("⚠️  Warning: No .env file found or error loading it. Using system environment variables.")
	}

	dsn := os.Getenv("DATABASE_URL")
	if dsn != "" {
		log.Printf("✅ Environment loaded. DSN length: %d", len(dsn))
	} else {
		log.Println("❌ Environment NOT loaded. DATABASE_URL is empty!")
	}
	log.Println("Starting AI Trading Signal Hub Backend (Gateway)...")

	// 1. Initialize Security Keys
	if err := auth.InitKeys(); err != nil {
		log.Fatalf("Failed to initialize security keys: %v", err)
	}

	// 2. Bootstrap Connections
	database.InitSupabase()

	redisURL := os.Getenv("REDIS_URL")
	if redisURL == "" {
		redisAddr := os.Getenv("REDIS_ADDR")
		if redisAddr != "" {
			redisURL = "redis://" + redisAddr
		} else {
			redisURL = "redis://localhost:6379" // Default fallback
		}
	}
	database.InitRedis(redisURL)

	database.LoadConfigsFromDB()

	// 3. Setup WebSocket Hub
	hub := ws.NewHub()
	go hub.Run()

	// 4. Start Notifier Worker (Redis Pub/Sub)
	go notifier.StartNotifierWorker()

	// 5. Start gRPC Client Stream Listener
	grpcAddr := os.Getenv("AI_ENGINE_ADDR")
	if grpcAddr == "" {
		grpcAddr = "localhost:50051"
	}
	signalClient := grpc.NewSignalClient(hub)
	go signalClient.StartStreaming(grpcAddr)

	// 5. Setup HTTP endpoints
	apidocs.Register(http.DefaultServeMux)

	http.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		ctx, cancel := context.WithTimeout(r.Context(), 2*time.Second)
		defer cancel()

		dbErr := database.PingSupabase(ctx)
		redisErr := database.PingRedis(ctx)
		streamConnected := signalClient.IsConnected()

		if dbErr != nil || redisErr != nil || !streamConnected {
			w.WriteHeader(http.StatusServiceUnavailable)
			_, _ = w.Write([]byte("unhealthy"))
			return
		}

		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte("ok"))
	})

	// 6. Setup WebSocket Server (HANYA WebSocket, NO REST API)
	http.HandleFunc("/ws", func(w http.ResponseWriter, r *http.Request) {
		ws.ServeWs(hub, w, r)
	})

	// 7. Start HTTP/WSS Server
	port := os.Getenv("WSS_PORT")
	if port == "" {
		port = "8443" // Default fallback sesuai arsitektur lokal
	}
	log.Printf("✅ Backend Gateway running on port %s (WS only)", port)

	// In production, use ListenAndServeTLS for WSS
	err := http.ListenAndServe(":"+port, nil)
	if err != nil {
		log.Fatal("ListenAndServe: ", err)
	}
}
