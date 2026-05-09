package notifier

import (
	"context"
	"fmt"
	"log"

	"github.com/skip2/go-qrcode"
	"go.mau.fi/whatsmeow"
	waProto "go.mau.fi/whatsmeow/binary/proto"
	"go.mau.fi/whatsmeow/store/sqlstore"
	"go.mau.fi/whatsmeow/types"
	waLog "go.mau.fi/whatsmeow/util/log"
	"google.golang.org/protobuf/proto"
	_ "modernc.org/sqlite"
)

type WhatsAppNotifier struct {
	Client *whatsmeow.Client
}

// NewWhatsAppNotifier initializes the whatsmeow client using SQLite for session storage
func NewWhatsAppNotifier() *WhatsAppNotifier {
	// For local testing and stability, we use SQLite for WhatsApp sessions.
	// TiDB is used for global configs and signals.
	dbPath := "whatsapp_sessions.db"
	container, err := sqlstore.New(context.Background(), "sqlite", fmt.Sprintf("file:%s?_foreign_keys=on", dbPath), waLog.Noop)
	if err != nil {
		log.Printf("❌ WhatsApp: Failed to create sqlite store: %v", err)
		return nil
	}

	deviceStore, err := container.GetFirstDevice(context.Background())
	if err != nil {
		log.Printf("❌ WhatsApp: Failed to get device store: %v", err)
		return nil
	}

	client := whatsmeow.NewClient(deviceStore, waLog.Noop)

	// If not logged in, prompt for QR Code
	if client.Store.ID == nil {
		qrChan, _ := client.GetQRChannel(context.Background())
		err = client.Connect()
		if err != nil {
			log.Printf("❌ WhatsApp: Connection failed: %v", err)
			return nil
		}
		go func() {
			for evt := range qrChan {
				if evt.Event == "code" {
					fmt.Println("\n📸 SCAN THIS QR CODE TO LOGIN WHATSAPP:")
					q, _ := qrcode.New(evt.Code, qrcode.Medium)
					fmt.Println(q.ToSmallString(false))
				} else {
					log.Printf("WhatsApp Event: %s", evt.Event)
				}
			}
		}()
	} else {
		err = client.Connect()
		if err != nil {
			log.Printf("❌ WhatsApp: Reconnection failed: %v", err)
			return nil
		}
	}

	return &WhatsAppNotifier{Client: client}
}

// Send sends a message to a WhatsApp number (format: 628123xxx)
func (w *WhatsAppNotifier) Send(target, message string) error {
	if w.Client == nil {
		return fmt.Errorf("whatsapp client not connected")
	}

	// Auto-append server if missing
	jid := types.NewJID(target, types.DefaultUserServer)
	
	msg := &waProto.Message{
		Conversation: proto.String(message),
	}

	_, err := w.Client.SendMessage(context.Background(), jid, msg)
	if err != nil {
		log.Printf("❌ WhatsApp: Failed to send message to %s: %v", target, err)
		return err
	}

	return nil
}
