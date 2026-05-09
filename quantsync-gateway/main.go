package main

import (
	"log"
	"net/http"
	"os"

	"github.com/joho/godotenv"
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
		redisURL = "redis://localhost:6379" // Default fallback
	}
	database.InitRedis(redisURL)

	database.LoadConfigsFromDB()

	// 3. Setup WebSocket Hub
	hub := ws.NewHub()
	go hub.Run()

	// 4. Start Notifier Worker (Redis Pub/Sub)
	go notifier.StartNotifierWorker()

	// 5. Start gRPC Client Stream Listener
	grpcAddr := "localhost:50051"
	signalClient := grpc.NewSignalClient(hub)
	go signalClient.StartStreaming(grpcAddr)

	// 5. Setup WebSocket Server (HANYA WebSocket, NO REST API)
	http.HandleFunc("/ws", func(w http.ResponseWriter, r *http.Request) {
		ws.ServeWs(hub, w, r)
	})

	// 6. Start HTTP/WSS Server
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
