package main

import (
	"context"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/joho/godotenv"
	"github.com/quantsync/quantsync-gateway/internal/apidocs"
	"github.com/quantsync/quantsync-gateway/internal/auth"
	"github.com/quantsync/quantsync-gateway/internal/database"
	interngrpc "github.com/quantsync/quantsync-gateway/internal/grpc"
	"github.com/quantsync/quantsync-gateway/internal/notifier"
	"github.com/quantsync/quantsync-gateway/internal/ws"
)

func main() {
	if err := godotenv.Load("../.env"); err != nil {
		log.Println("⚠️  No .env file found. Using system environment variables.")
	}

	dsn := os.Getenv("DATABASE_URL")
	if dsn == "" {
		log.Fatal("❌ DATABASE_URL is empty — cannot start without database connection.")
	}
	log.Printf("✅ DATABASE_URL loaded (len=%d)", len(dsn))

	log.Println("Starting QuantSync Gateway...")

	// ─── Root context dengan graceful shutdown ────────────────────────────────
	rootCtx, rootCancel := context.WithCancel(context.Background())
	defer rootCancel()

	// ─── Init ─────────────────────────────────────────────────────────────────
	if err := auth.InitKeys(); err != nil {
		log.Fatalf("Failed to initialize security keys: %v", err)
	}

	database.InitSupabase()

	redisURL := os.Getenv("REDIS_URL")
	if redisURL == "" {
		if addr := os.Getenv("REDIS_ADDR"); addr != "" {
			redisURL = "redis://" + addr
		} else {
			redisURL = "redis://localhost:6379"
		}
	}
	database.InitRedis(redisURL)
	database.LoadConfigsFromDB()

	// ─── WebSocket Hub ────────────────────────────────────────────────────────
	hub := ws.NewHub()
	go hub.Run()

	// ─── Notifier Worker ──────────────────────────────────────────────────────
	go notifier.StartNotifierWorker()

	// ─── gRPC Signal Stream ───────────────────────────────────────────────────
	grpcAddr := os.Getenv("AI_ENGINE_ADDR")
	if grpcAddr == "" {
		grpcAddr = "localhost:50051"
	}
	signalClient := interngrpc.NewSignalClient(hub)
	// FIX: pass context agar bisa di-cancel saat shutdown
	go signalClient.StartStreaming(rootCtx, grpcAddr)

	// ─── HTTP Endpoints ───────────────────────────────────────────────────────
	mux := http.NewServeMux()
	apidocs.Register(mux)

	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		ctx, cancel := context.WithTimeout(r.Context(), 2*time.Second)
		defer cancel()

		dbErr := database.PingSupabase(ctx)
		redisErr := database.PingRedis(ctx)
		streamOK := signalClient.IsConnected()

		if dbErr != nil || redisErr != nil || !streamOK {
			log.Printf("[Health] unhealthy — db=%v redis=%v stream=%v", dbErr, redisErr, streamOK)
			w.WriteHeader(http.StatusServiceUnavailable)
			_, _ = w.Write([]byte("unhealthy"))
			return
		}

		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte("ok"))
	})

	mux.HandleFunc("/ws", func(w http.ResponseWriter, r *http.Request) {
		ws.ServeWs(hub, w, r)
	})

	// ─── HTTP Server ──────────────────────────────────────────────────────────
	port := os.Getenv("WSS_PORT")
	if port == "" {
		port = "8080"
	}

	httpServer := &http.Server{
		Addr:         ":" + port,
		Handler:      mux,
		ReadTimeout:  15 * time.Second,
		WriteTimeout: 15 * time.Second,
		IdleTimeout:  60 * time.Second,
	}

	// ─── Graceful Shutdown ────────────────────────────────────────────────────
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)

	go func() {
		log.Printf("✅ Gateway running on :%s", port)
		if err := httpServer.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("ListenAndServe error: %v", err)
		}
	}()

	<-quit
	log.Println("Shutdown signal received. Gracefully stopping...")

	// Cancel root context → stop gRPC stream
	rootCancel()

	// Shutdown HTTP server dengan 10s deadline
	shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer shutdownCancel()
	if err := httpServer.Shutdown(shutdownCtx); err != nil {
		log.Printf("HTTP server forced shutdown: %v", err)
	}

	log.Println("Gateway stopped cleanly.")
}
