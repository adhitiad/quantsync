package notifier

import (
	"crypto/tls"
	"fmt"
	"log"
	"net/smtp"
	"os"
	"strings"
	"time"
)

// EmailNotifier handles email notifications
type EmailNotifier struct {
	config Config
}

// Config holds SMTP configuration.
// Semua value diambil dari environment — tidak ada hardcoded credential.
type Config struct {
	Host            string
	Port            string
	Username        string
	Password        string
	FromAddress     string
	TLSSkipVerify   bool // FIX: default false, hanya true jika SMTP_TLS_SKIP_VERIFY=true
}

func loadConfig() Config {
	host     := os.Getenv("SMTP_HOST")
	port     := os.Getenv("SMTP_PORT")
	username := os.Getenv("SMTP_USERNAME")
	password := os.Getenv("SMTP_PASSWORD")
	from     := os.Getenv("SMTP_FROM_EMAIL")

	if port == "" {
		port = "587"
	}
	if from == "" {
		from = username
	}

	// FIX: InsecureSkipVerify hanya aktif jika env var eksplisit "true"
	// Default: false (TLS terverifikasi penuh)
	skipVerify := strings.EqualFold(os.Getenv("SMTP_TLS_SKIP_VERIFY"), "true")

	appEnv := os.Getenv("APP_ENV")
	if skipVerify && strings.EqualFold(appEnv, "production") {
		// Production: override paksa ke false + log warning
		log.Printf(
			"[Email] ⚠️  SMTP_TLS_SKIP_VERIFY=true diabaikan di APP_ENV=production. " +
				"TLS verification diaktifkan paksa.",
		)
		skipVerify = false
	}

	return Config{
		Host:          host,
		Port:          port,
		Username:      username,
		Password:      password,
		FromAddress:   from,
		TLSSkipVerify: skipVerify,
	}
}

// NewEmailNotifier creates a new EmailNotifier instance
func NewEmailNotifier(configMap map[string]string) *EmailNotifier {
	// Override config with values from database if available
	if host, ok := configMap["SMTP_HOST"]; ok && host != "" {
		os.Setenv("SMTP_HOST", host)
	}
	if port, ok := configMap["SMTP_PORT"]; ok && port != "" {
		os.Setenv("SMTP_PORT", port)
	}
	if username, ok := configMap["SMTP_USERNAME"]; ok && username != "" {
		os.Setenv("SMTP_USERNAME", username)
	}
	if password, ok := configMap["SMTP_PASSWORD"]; ok && password != "" {
		os.Setenv("SMTP_PASSWORD", password)
	}
	if from, ok := configMap["SMTP_FROM_EMAIL"]; ok && from != "" {
		os.Setenv("SMTP_FROM_EMAIL", from)
	}

	return &EmailNotifier{
		config: loadConfig(),
	}
}

// Message represents an outgoing email.
type Message struct {
	To      []string
	Subject string
	Body    string
}

// Send mengirim email via SMTP dengan STARTTLS.
// FIX: InsecureSkipVerify dikontrol via env var, bukan hardcoded true.
func (e *EmailNotifier) Send(to, message string) error {
	cfg := e.config

	if cfg.Host == "" || cfg.Username == "" || cfg.Password == "" {
		return fmt.Errorf("SMTP config tidak lengkap (SMTP_HOST/USERNAME/PASSWORD kosong)")
	}

	addr := fmt.Sprintf("%s:%s", cfg.Host, cfg.Port)

	tlsCfg := &tls.Config{
		InsecureSkipVerify: cfg.TLSSkipVerify, // FIX: tidak lagi hardcoded true
		ServerName:         cfg.Host,
		MinVersion:         tls.VersionTLS12,
	}

	// Gunakan STARTTLS (port 587) — koneksi awal plaintext, di-upgrade ke TLS
	conn, err := smtp.Dial(addr)
	if err != nil {
		return fmt.Errorf("gagal dial SMTP %s: %w", addr, err)
	}
	defer conn.Close()

	if err := conn.StartTLS(tlsCfg); err != nil {
		return fmt.Errorf("gagal STARTTLS ke %s: %w", cfg.Host, err)
	}

	auth := smtp.PlainAuth("", cfg.Username, cfg.Password, cfg.Host)
	if err := conn.Auth(auth); err != nil {
		return fmt.Errorf("SMTP auth gagal: %w", err)
	}

	if err := conn.Mail(cfg.FromAddress); err != nil {
		return fmt.Errorf("SMTP MAIL FROM gagal: %w", err)
	}

	if err := conn.Rcpt(to); err != nil {
		return fmt.Errorf("SMTP RCPT TO %s gagal: %w", to, err)
	}

	w, err := conn.Data()
	if err != nil {
		return fmt.Errorf("SMTP DATA gagal: %w", err)
	}
	defer w.Close()

	header := buildHeader(cfg.FromAddress, []string{to}, "QuantSync Signal")
	body := header + "\r\n" + message
	if _, err := fmt.Fprint(w, body); err != nil {
		return fmt.Errorf("gagal menulis body email: %w", err)
	}

	log.Printf(
		"[Email] ✅ Terkirim ke %s (TLS skip_verify=%v)",
		to, cfg.TLSSkipVerify,
	)
	return nil
}

func buildHeader(from string, to []string, subject string) string {
	return fmt.Sprintf(
		"From: %s\r\nTo: %s\r\nSubject: %s\r\nDate: %s\r\nMIME-Version: 1.0\r\nContent-Type: text/plain; charset=UTF-8",
		from,
		strings.Join(to, ", "),
		subject,
		time.Now().UTC().Format(time.RFC1123Z),
	)
}
