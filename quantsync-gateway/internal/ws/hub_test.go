package ws

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/gorilla/websocket"
	"github.com/quantsync/quantsync-gateway/internal/auth"
)

func TestWebSocketHub(t *testing.T) {
	hub := NewHub()
	go hub.Run()

	// Mock server
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		ServeWs(hub, w, r)
	}))
	defer server.Close()

	// Prepare JWT token
	auth.InitKeys()
	token, _ := auth.GenerateToken(1, "user", "free")

	// Connect to WebSocket
	url := "ws" + strings.TrimPrefix(server.URL, "http") + "/ws?token=" + token
	wsConn, _, err := websocket.DefaultDialer.Dial(url, nil)
	if err != nil {
		t.Fatalf("Failed to connect: %v", err)
	}
	defer wsConn.Close()

	// Test broadcast
	testSignal := map[string]interface{}{
		"asset": "BTC",
		"required_plan": "free",
	}
	hub.BroadcastSignal(testSignal)

	// Read message
	_, message, err := wsConn.ReadMessage()
	if err != nil {
		t.Fatalf("Failed to read message: %v", err)
	}

	if !strings.Contains(string(message), "BTC") {
		t.Errorf("Expected message to contain BTC, got %s", string(message))
	}
}
