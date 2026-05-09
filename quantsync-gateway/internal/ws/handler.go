package ws

import (
	"log"
	"net/http"

	"github.com/google/uuid"
	"github.com/gorilla/websocket"
	"github.com/quantsync/quantsync-gateway/internal/auth"
)

var upgrader = websocket.Upgrader{
	ReadBufferSize:  1024,
	WriteBufferSize: 1024,
	CheckOrigin: func(r *http.Request) bool {
		origin := r.Header.Get("Origin")
		// Izinkan CLI/Postman (Origin kosong), localhost, atau domain produksi
		if origin == "" || origin == "http://localhost:3000" || origin == "https://quantsync.com" {
			return true
		}
		log.Printf("[SECURITY] Rejected WebSocket Connection from Origin: %s", origin)
		return false
	},
}

var limiter = NewRateLimiter()

func ServeWs(hub *Hub, w http.ResponseWriter, r *http.Request) {
	token := r.URL.Query().Get("token")
	if token == "" {
		http.Error(w, "Unauthorized", http.StatusUnauthorized)
		return
	}

	claims, err := auth.ValidateToken(token)
	if err != nil {
		http.Error(w, "Invalid token", http.StatusUnauthorized)
		return
	}

	// Initial rate limit check before upgrading
	allowed, err := limiter.Allow(claims.UserID, claims.Plan)
	if err != nil || !allowed {
		http.Error(w, "Rate limit exceeded", http.StatusTooManyRequests)
		return
	}

	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Println("Upgrade error:", err)
		return
	}

	client := &Client{
		ID:     uuid.New().String(),
		Conn:   conn,
		Claims: claims,
		Send:   make(chan []byte, 256),
	}
	hub.register <- client

	// Start pumps in background
	go client.WritePump()
	go client.ReadPump(hub)
}
