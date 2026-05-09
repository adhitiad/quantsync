package database

import (
	"context"
	"database/sql"
	"log"
	"os"
	"strings"

	_ "github.com/jackc/pgx/v5/stdlib"
	"github.com/quantsync/quantsync-gateway/internal/models"
	"gorm.io/driver/postgres"
	"gorm.io/gorm"
)

var (
	SQL *sql.DB
	DB  *gorm.DB
)

// InitSupabase initializes the Supabase Postgres connection.
func InitSupabase() {
	dsn := os.Getenv("DATABASE_URL")
	if dsn == "" {
		log.Fatal("Fatal Error: DATABASE_URL environment variable tidak ditemukan!")
	}
	dsn = ensureSSLMode(dsn)

	sqlDB, err := sql.Open("pgx", dsn)
	if err != nil {
		log.Fatalf("Gagal membuka koneksi ke Supabase: %v", err)
	}

	if err := sqlDB.Ping(); err != nil {
		log.Fatalf("Gagal melakukan ping ke Supabase: %v", err)
	}

	sqlDB.SetMaxOpenConns(50)
	sqlDB.SetMaxIdleConns(10)

	log.Println("[Database] Berhasil terhubung ke Supabase Postgres")
	SQL = sqlDB

	gormDB, err := gorm.Open(postgres.New(postgres.Config{
		Conn: sqlDB,
	}), &gorm.Config{})
	if err != nil {
		log.Fatalf("Gagal menginisialisasi GORM: %v", err)
	}
	DB = gormDB

	err = DB.AutoMigrate(
		&models.User{},
		&models.Subscription{},
		&models.SystemConfig{},
		&models.SignalHistory{},
		&models.MarketData{},
	)
	if err != nil {
		log.Printf("Gagal menjalankan migrasi: %v", err)
	}
}

func ensureSSLMode(dsn string) string {
	lowerDSN := strings.ToLower(dsn)
	if strings.Contains(lowerDSN, "sslmode=") {
		return dsn
	}
	if strings.Contains(dsn, "?") {
		return dsn + "&sslmode=require"
	}
	return dsn + "?sslmode=require"
}

// LoadConfigsFromDB loads database-backed settings into Redis.
func LoadConfigsFromDB() {
	if SQL == nil {
		log.Fatal("LoadConfigsFromDB dipanggil sebelum InitSupabase!")
	}

	rows, err := SQL.Query(`SELECT "key", "value" FROM system_configs`)
	if err != nil {
		log.Printf("Gagal mengambil configs dari DB: %v", err)
		return
	}
	defer rows.Close()

	ctx := context.Background()
	count := 0
	for rows.Next() {
		var key, value string
		if err := rows.Scan(&key, &value); err != nil {
			log.Printf("Gagal scan config row: %v", err)
			continue
		}

		err := RedisClient.Set(ctx, "config:"+key, value, 0).Err()
		if err != nil {
			log.Printf("Gagal menyimpan config %s ke Redis: %v", key, err)
		}
		count++
	}

	log.Printf("[Config] Berhasil memuat %d konfigurasi dari Supabase ke Redis", count)
}
