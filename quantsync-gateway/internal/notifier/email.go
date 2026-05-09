package notifier

import (
	"crypto/tls"
	"log"
	"strconv"

	"gopkg.in/gomail.v2"
)

type EmailNotifier struct {
	Host string
	Port int
	User string
	Pass string
	From string
}

// NewEmailNotifier initializes the SMTP configuration from database map
func NewEmailNotifier(configs map[string]string) *EmailNotifier {
	port, _ := strconv.Atoi(configs["SMTP_PORT"])
	
	if configs["SMTP_HOST"] == "" {
		log.Println("⚠️ Email: SMTP Host is missing, skipping email init")
		return nil
	}

	return &EmailNotifier{
		Host: configs["SMTP_HOST"],
		Port: port,
		User: configs["SMTP_USER"],
		Pass: configs["SMTP_PASS"],
		From: configs["SMTP_FROM"],
	}
}

// Send dispatches an email via SMTP with TLS support
func (e *EmailNotifier) Send(to, message string) error {
	if e == nil || e.Host == "" {
		return nil
	}

	m := gomail.NewMessage()
	m.SetHeader("From", e.From)
	m.SetHeader("To", to)
	m.SetHeader("Subject", "🚀 QuantSync AI Trading Signal")
	m.SetBody("text/plain", message)

	d := gomail.NewDialer(e.Host, e.Port, e.User, e.Pass)
	
	// Support for servers with self-signed certs or local TLS (Mailcow/Postal)
	d.TLSConfig = &tls.Config{InsecureSkipVerify: true}

	if err := d.DialAndSend(m); err != nil {
		log.Printf("❌ Email: Failed to send to %s: %v", to, err)
		return err
	}

	return nil
}
