package ws

import (
	"encoding/json"
	"log"
	"sync"

	"github.com/quantsync/quantsync-gateway/internal/auth"
)

// Hub maintains the set of active clients and broadcasts messages to eligible ones.
type Hub struct {
	clients    map[*Client]bool
	broadcast  chan []byte
	register   chan *Client
	unregister chan *Client
	mu         sync.RWMutex
}

func NewHub() *Hub {
	return &Hub{
		clients:    make(map[*Client]bool),
		broadcast:  make(chan []byte, 256), // buffered — hindari BroadcastSignal block saat tidak ada consumer
		register:   make(chan *Client, 32),
		unregister: make(chan *Client, 32),
	}
}

func (h *Hub) Run() {
	for {
		select {
		case client := <-h.register:
			h.mu.Lock()
			h.clients[client] = true
			h.mu.Unlock()
			log.Printf("[Hub] Client registered: %s (total: %d)", client.ID, h.clientCount())

		case client := <-h.unregister:
			h.mu.Lock()
			if _, ok := h.clients[client]; ok {
				delete(h.clients, client)
				close(client.Send)
			}
			h.mu.Unlock()
			log.Printf("[Hub] Client unregistered: %s (total: %d)", client.ID, h.clientCount())

		case message := <-h.broadcast:
			h.fanOut(message)
		}
	}
}

// fanOut distributes a message to all eligible clients.
// FIX: Data race dihapus — collect slow/dead clients dulu, baru delete setelah RUnlock.
func (h *Hub) fanOut(message []byte) {
	var signal map[string]interface{}
	if err := json.Unmarshal(message, &signal); err != nil {
		log.Printf("[Hub] Invalid message JSON: %v", err)
		return
	}

	requiredPlan := "free"
	if val, ok := signal["required_plan"].(string); ok {
		requiredPlan = val
	}

	// Kumpulkan client yang koneksinya mati (channel penuh / closed)
	var deadClients []*Client

	h.mu.RLock()
	for client := range h.clients {
		if !auth.CheckPermission(client.Claims.Role, client.Claims.Plan, requiredPlan) {
			continue
		}
		select {
		case client.Send <- message:
			// OK
		default:
			// Channel penuh → client lambat / mati, tandai untuk dihapus
			deadClients = append(deadClients, client)
		}
	}
	h.mu.RUnlock()

	// Hapus dead clients setelah RUnlock — tidak lagi di dalam RLock
	if len(deadClients) > 0 {
		h.mu.Lock()
		for _, client := range deadClients {
			if _, ok := h.clients[client]; ok {
				delete(h.clients, client)
				close(client.Send)
				log.Printf("[Hub] Dead client evicted: %s", client.ID)
			}
		}
		h.mu.Unlock()
	}
}

// BroadcastSignal marshal dan kirim ke channel broadcast.
// Non-blocking karena channel sudah buffered — jika penuh, sinyal di-drop dengan log warning.
func (h *Hub) BroadcastSignal(data interface{}) {
	msg, err := json.Marshal(data)
	if err != nil {
		log.Printf("[Hub] Error marshaling signal: %v", err)
		return
	}

	select {
	case h.broadcast <- msg:
	default:
		log.Printf("[Hub] Broadcast channel full — signal dropped (lagging consumers)")
	}
}

func (h *Hub) clientCount() int {
	h.mu.RLock()
	defer h.mu.RUnlock()
	return len(h.clients)
}
