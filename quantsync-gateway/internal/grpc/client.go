package grpc

import (
	"context"
	"crypto/tls"
	"crypto/x509"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"os"
	"sync/atomic"
	"time"

	"github.com/quantsync/quantsync-gateway/internal/database"
	"github.com/quantsync/quantsync-gateway/internal/utils"
	"github.com/quantsync/quantsync-gateway/internal/ws"
	pb "github.com/quantsync/quantsync-gateway/proto/signal"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials"
)

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

func loadTLSCredentials() (credentials.TransportCredentials, error) {
	// Memuat CA certificate
	pemServerCA, err := os.ReadFile("certs/ca.crt")
	if err != nil {
		return nil, err
	}

	certPool := x509.NewCertPool()
	if !certPool.AppendCertsFromPEM(pemServerCA) {
		return nil, fmt.Errorf("failed to add server CA's certificate")
	}

	// Memuat client certificate dan private key
	clientCert, err := tls.LoadX509KeyPair("certs/client.crt", "certs/client.key")
	if err != nil {
		return nil, err
	}

	config := &tls.Config{
		Certificates:       []tls.Certificate{clientCert},
		RootCAs:            certPool,
		InsecureSkipVerify: true, // Kita akan verifikasi manual untuk melewati error legacy Common Name
		ServerName:         "localhost",
		VerifyPeerCertificate: func(rawCerts [][]byte, verifiedChains [][]*x509.Certificate) error {
			for _, rawCert := range rawCerts {
				cert, err := x509.ParseCertificate(rawCert)
				if err != nil {
					return fmt.Errorf("failed to parse certificate: %v", err)
				}
				opts := x509.VerifyOptions{
					Roots: certPool,
				}
				_, err = cert.Verify(opts)
				if err != nil {
					return fmt.Errorf("failed to verify certificate chain: %v", err)
				}
			}
			return nil
		},
	}

	return credentials.NewTLS(config), nil
}

func (s *SignalClient) StartStreaming(address string) {
	for {
		s.connected.Store(false)

		tt := utils.GetTripleTime()
		logHeader := fmt.Sprintf("[JKT: %s | NY: %s | LDN: %s]",
			tt.Jakarta.Format("15:04"),
			tt.NewYork.Format("15:04"),
			tt.London.Format("15:04"))

		log.Printf("%s Connecting to AI Engine gRPC at %s (mTLS)...", logHeader, address)

		tlsCreds, err := loadTLSCredentials()
		if err != nil {
			log.Printf("%s Fatal: Gagal memuat mTLS certs: %v", logHeader, err)
			time.Sleep(10 * time.Second)
			continue
		}

		conn, err := grpc.NewClient(address, grpc.WithTransportCredentials(tlsCreds))
		if err != nil {
			log.Printf("%s Failed to connect to gRPC: %v. Retrying...", logHeader, err)
			time.Sleep(5 * time.Second)
			continue
		}

		client := pb.NewSignalServiceClient(conn)
		stream, err := client.StreamSignals(context.Background(), &pb.SignalRequest{
			Asset: "ALL",
		})
		if err != nil {
			log.Printf("%s Error opening stream: %v", logHeader, err)
			conn.Close()
			time.Sleep(5 * time.Second)
			continue
		}

		log.Printf("%s Successfully connected to AI Engine signal stream.", logHeader)
		s.connected.Store(true)

		for {
			signal, err := stream.Recv()
			if err == io.EOF {
				break
			}
			if err != nil {
				tt_err := utils.GetTripleTime()
				log.Printf("[JKT: %s] Error receiving from stream: %v", tt_err.Jakarta.Format("15:04:05"), err)
				break
			}

			// Parse original UTC timestamp
			_, err = time.Parse(time.RFC3339, signal.Timestamp)
			if err != nil {
				signal.Timestamp = time.Now().UTC().Format(time.RFC3339)
			}

			// Distribute signal to WebSocket Hub
			s.hub.BroadcastSignal(signal)

			// Publish to Redis for Notifier Worker
			payload, _ := json.Marshal(signal)
			database.RedisClient.Publish(context.Background(), "signal_events", payload)

			tt_rx := utils.GetTripleTime()
			log.Printf("[JKT: %s] Received signal: %s %s @ %.5f (Winrate: %.1f%%)",
				tt_rx.Jakarta.Format("15:04:05"), signal.Asset, signal.TypeSignal, signal.Price, signal.WinratePct)
		}

		s.connected.Store(false)
		conn.Close()
		time.Sleep(2 * time.Second)
	}
}
