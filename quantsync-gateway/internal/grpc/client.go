package grpc

import (
	"context"
	"crypto/tls"
	"crypto/x509"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"math"
	"math/rand"
	"os"
	"sync/atomic"
	"time"

	"github.com/quantsync/quantsync-gateway/internal/database"
	"github.com/quantsync/quantsync-gateway/internal/utils"
	"github.com/quantsync/quantsync-gateway/internal/ws"
	pb "github.com/quantsync/quantsync-gateway/proto/signal"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials"
	"google.golang.org/grpc/keepalive"
)

const (
	backoffBase   = 2 * time.Second
	backoffMax    = 60 * time.Second
	backoffFactor = 2.0
	backoffJitter = 0.2 // ±20% jitter untuk hindari thundering herd
)

// SignalClient manages the gRPC streaming connection to the AI engine.
type SignalClient struct {
	hub       *ws.Hub
	connected atomic.Bool
}

func NewSignalClient(hub *ws.Hub) *SignalClient {
	return &SignalClient{hub: hub}
}

func (s *SignalClient) IsConnected() bool {
	return s.connected.Load()
}

// loadTLSCredentials memuat sertifikat mTLS dengan verifikasi penuh.
// FIX: InsecureSkipVerify dihapus — verifikasi cert chain dilakukan oleh TLS stack,
// bukan manual VerifyPeerCertificate yang bisa di-bypass.
func loadTLSCredentials() (credentials.TransportCredentials, error) {
	certDir := os.Getenv("CERTS_DIR")
	if certDir == "" {
		certDir = "certs"
	}

	caPath := certDir + "/ca.crt"
	clientCert := certDir + "/client.crt"
	clientKey := certDir + "/client.key"

	for _, path := range []string{caPath, clientCert, clientKey} {
		if _, err := os.Stat(path); err != nil {
			return nil, fmt.Errorf("sertifikat tidak ditemukan: %s", path)
		}
	}

	pemServerCA, err := os.ReadFile(caPath)
	if err != nil {
		return nil, fmt.Errorf("gagal baca CA cert: %w", err)
	}

	certPool := x509.NewCertPool()
	if !certPool.AppendCertsFromPEM(pemServerCA) {
		return nil, fmt.Errorf("gagal parse CA cert PEM")
	}

	cert, err := tls.LoadX509KeyPair(clientCert, clientKey)
	if err != nil {
		return nil, fmt.Errorf("gagal load client keypair: %w", err)
	}

	cfg := &tls.Config{
		Certificates: []tls.Certificate{cert},
		RootCAs:      certPool,
		// FIX: InsecureSkipVerify = false (default) — TLS stack verifikasi cert chain
		// FIX: ServerName dari env agar bisa di-override untuk deployment yang berbeda
		ServerName: serverName(),
		MinVersion: tls.VersionTLS13,
	}

	return credentials.NewTLS(cfg), nil
}

func serverName() string {
	if name := os.Getenv("GRPC_SERVER_NAME"); name != "" {
		return name
	}
	return "quantsync-ai-engine" // default SAN di sertifikat
}

// calcBackoff menghitung delay retry dengan exponential backoff + jitter.
func calcBackoff(attempt int) time.Duration {
	exp := math.Pow(backoffFactor, float64(attempt))
	delay := backoffBase * time.Duration(exp)
	if delay > backoffMax {
		delay = backoffMax
	}
	// Tambah jitter ±20%
	jitter := time.Duration(float64(delay) * backoffJitter * (rand.Float64()*2 - 1))
	return delay + jitter
}

// StartStreaming membuka koneksi streaming ke AI engine dan melakukan reconnect otomatis.
// Menerima ctx untuk graceful shutdown dari caller (main.go).
func (s *SignalClient) StartStreaming(ctx context.Context, address string) {
	attempt := 0

	for {
		// Cek context sebelum tiap retry
		select {
		case <-ctx.Done():
			log.Printf("[gRPC] Context cancelled. Stream listener stopped.")
			return
		default:
		}

		s.connected.Store(false)

		tt := utils.GetTripleTime()
		logHeader := fmt.Sprintf("[JKT:%s|NY:%s|LDN:%s]",
			tt.Jakarta.Format("15:04"),
			tt.NewYork.Format("15:04"),
			tt.London.Format("15:04"),
		)

		if attempt > 0 {
			delay := calcBackoff(attempt)
			log.Printf("%s Retry #%d: menunggu %s sebelum reconnect ke %s", logHeader, attempt, delay.Round(time.Millisecond), address)
			select {
			case <-time.After(delay):
			case <-ctx.Done():
				return
			}
		}

		log.Printf("%s Connecting to AI Engine gRPC: %s", logHeader, address)

		tlsCreds, err := loadTLSCredentials()
		if err != nil {
			log.Printf("%s [WARN] mTLS certs gagal dimuat: %v", logHeader, err)

			// Development fallback: coba insecure jika APP_ENV != production
			appEnv := os.Getenv("APP_ENV")
			if appEnv == "production" {
				log.Printf("%s [FATAL] Production mode — tidak bisa connect tanpa mTLS. Retry...", logHeader)
				attempt++
				continue
			}
			log.Printf("%s [WARN] Development mode — fallback ke insecure gRPC (tidak untuk production!)", logHeader)
			tlsCreds = nil
		}

		var dialOpts []grpc.DialOption
		if tlsCreds != nil {
			dialOpts = append(dialOpts, grpc.WithTransportCredentials(tlsCreds))
		} else {
			dialOpts = append(dialOpts, grpc.WithInsecure()) //nolint:staticcheck // development only
		}

		// Keepalive untuk deteksi koneksi mati lebih cepat
		dialOpts = append(dialOpts, grpc.WithKeepaliveParams(keepalive.ClientParameters{
			Time:                10 * time.Second,
			Timeout:             5 * time.Second,
			PermitWithoutStream: true,
		}))

		conn, err := grpc.NewClient(address, dialOpts...)
		if err != nil {
			log.Printf("%s Failed to connect gRPC: %v", logHeader, err)
			attempt++
			continue
		}

		client := pb.NewSignalServiceClient(conn)

		streamCtx, cancelStream := context.WithCancel(ctx)
		stream, err := client.StreamSignals(streamCtx, &pb.SignalRequest{Asset: "ALL"})
		if err != nil {
			log.Printf("%s Error opening stream: %v", logHeader, err)
			cancelStream()
			conn.Close()
			attempt++
			continue
		}

		log.Printf("%s ✅ Connected to AI Engine signal stream.", logHeader)
		s.connected.Store(true)
		attempt = 0 // reset backoff setelah berhasil connect

		s.recvLoop(ctx, stream)

		cancelStream()
		conn.Close()
		s.connected.Store(false)
		attempt++ // koneksi putus → mulai backoff lagi
	}
}

// recvLoop membaca signal dari stream hingga EOF, error, atau context cancelled.
func (s *SignalClient) recvLoop(ctx context.Context, stream pb.SignalService_StreamSignalsClient) {
	for {
		signal, err := stream.Recv()
		if err == io.EOF {
			log.Printf("[gRPC] Stream closed by server (EOF).")
			return
		}
		if err != nil {
			// Cek apakah ini karena context kita yang di-cancel (shutdown normal)
			select {
			case <-ctx.Done():
				log.Printf("[gRPC] Stream closed due to context cancellation.")
				return
			default:
				tt := utils.GetTripleTime()
				log.Printf("[JKT:%s] Stream error: %v", tt.Jakarta.Format("15:04:05"), err)
				return
			}
		}

		// Normalize timestamp
		if _, parseErr := time.Parse(time.RFC3339, signal.Timestamp); parseErr != nil {
			signal.Timestamp = time.Now().UTC().Format(time.RFC3339)
		}

		// Fan-out ke WebSocket clients
		s.hub.BroadcastSignal(signal)

		// Publish ke Redis untuk notifier
		if payload, marshalErr := json.Marshal(signal); marshalErr == nil {
			if pubErr := database.RedisClient.Publish(ctx, "signal_events", payload).Err(); pubErr != nil {
				log.Printf("[gRPC] Redis publish error: %v", pubErr)
			}
		}

		tt := utils.GetTripleTime()
		log.Printf("[JKT:%s] Signal: %s %s @ %.5f (prob=%.1f%% winrate=%.1f%%)",
			tt.Jakarta.Format("15:04:05"),
			signal.Asset,
			signal.TypeSignal,
			signal.Price,
			signal.ProbabilityPct,
			signal.WinratePct,
		)
	}
}
