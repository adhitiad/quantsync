package ws

import (
	"encoding/json"
	"log"
	"sync"

	"github.com/quantsync/quantsync-gateway/internal/auth"
)

// Hub maintains the set of active clients and broadcasts messages.
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
		broadcast:  make(chan []byte),
		register:   make(chan *Client),
		unregister: make(chan *Client),
	}
}

func (h *Hub) Run() {
	for {
		select {
		case client := <-h.register:
			h.mu.Lock()
			h.clients[client] = true
			h.mu.Unlock()
			log.Printf("Client registered: %s", client.ID)

		case client := <-h.unregister:
			h.mu.Lock()
			if _, ok := h.clients[client]; ok {
				delete(h.clients, client)
				close(client.Send)
			}
			h.mu.Unlock()
			log.Printf("Client unregistered: %s", client.ID)

		case message := <-h.broadcast:
			var signal map[string]interface{}
			if err := json.Unmarshal(message, &signal); err != nil {
				continue
			}

			h.mu.RLock()
			for client := range h.clients {
				requiredPlan := "free"
				if val, ok := signal["required_plan"].(string); ok {
					requiredPlan = val
				}

				if auth.CheckPermission(client.Claims.Role, client.Claims.Plan, requiredPlan) {
					select {
					case client.Send <- message:
					default:
						close(client.Send)
						delete(h.clients, client)
					}
				}
			}
			h.mu.RUnlock()
		}
	}
}

func (h *Hub) BroadcastSignal(data interface{}) {
	msg, err := json.Marshal(data)
	if err != nil {
		log.Printf("Error marshaling signal: %v", err)
		return
	}
	h.broadcast <- msg
}
