package database

import (
	"context"
	"crypto/tls"
	"database/sql"
	"log"
	"os"
	"strings"

	mysql_driver "github.com/go-sql-driver/mysql"
	"github.com/quantsync/quantsync-gateway/internal/models"
	"gorm.io/driver/mysql"
	"gorm.io/gorm"
)

var (
	SQL *sql.DB
	DB  *gorm.DB
)

// InitTiDB menginisialisasi koneksi aman ke TiDB Cloud
func InitTiDB() {
	// 2. Ambil DSN dari Environment Variable
	dsn := os.Getenv("TIDB_DSN")
	if dsn == "" {
		log.Fatal("Fatal Error: TIDB_DSN environment variable tidak ditemukan!")
	}

	// 3. Pastikan parseTime=true ada di DSN untuk membaca DATETIME sebagai time.Time
	if !strings.Contains(dsn, "parseTime=true") {
		if strings.Contains(dsn, "?") {
			dsn += "&parseTime=true"
		} else {
			dsn += "?parseTime=true"
		}
	}

	// 4. Ekstrak host untuk TLS ServerName
	host := "gateway01.us-east-1.prod.aws.tidbcloud.com"
	if strings.Contains(dsn, "tcp(") {
		host = strings.Split(strings.Split(dsn, "tcp(")[1], ":")[0]
	}

	// 1. Registrasi konfigurasi TLS khusus untuk TiDB Serverless
	err := mysql_driver.RegisterTLSConfig("tidb", &tls.Config{
		MinVersion: tls.VersionTLS12,
		ServerName: host,
	})
	if err != nil {
		log.Fatalf("Gagal meregistrasi TLS config: %v", err)
	}

	// 4. Inisialisasi Database quantsync jika belum ada
	ensureDatabaseExists(dsn)

	// 4. Buka koneksi database utama
	sqlDB, err := sql.Open("mysql", dsn)
	if err != nil {
		log.Fatalf("Gagal membuka koneksi ke TiDB: %v", err)
	}

	// 5. Test Ping
	if err := sqlDB.Ping(); err != nil {
		log.Fatalf("Gagal melakukan ping ke TiDB Cloud: %v", err)
	}

	// 6. Connection Pooling Optimization
	sqlDB.SetMaxOpenConns(50)
	sqlDB.SetMaxIdleConns(10)

	log.Println("✅ [Database] Berhasil terhubung ke TiDB Cloud (Orojackson)")
	SQL = sqlDB

	// 7. Inisialisasi GORM
	gormDB, err := gorm.Open(mysql.New(mysql.Config{
		Conn: sqlDB,
	}), &gorm.Config{})
	if err != nil {
		log.Fatalf("Gagal menginisialisasi GORM: %v", err)
	}
	DB = gormDB

	// 8. Auto Migration (GORM akan menyesuaikan skema jika ada perubahan model)
	err = DB.AutoMigrate(
		&models.User{},
		&models.Subscription{},
		&models.SystemConfig{},
		&models.SignalHistory{},
		&models.MarketData{},
	)
	if err != nil {
		log.Printf("⚠️ Gagal menjalankan migrasi: %v", err)
	}
}

func ensureDatabaseExists(dsn string) {
	parts := strings.Split(dsn, "/")
	if len(parts) < 2 {
		return
	}

	hostPart := parts[0]
	queryPart := ""
	if strings.Contains(parts[1], "?") {
		queryPart = "?" + strings.Split(parts[1], "?")[1]
	}

	baseDSN := hostPart + "/test" + queryPart

	tmpDB, err := sql.Open("mysql", baseDSN)
	if err != nil {
		log.Printf("Warning: Gagal membuka koneksi awal untuk cek database: %v", err)
		return
	}
	defer tmpDB.Close()

	_, err = tmpDB.Exec("CREATE DATABASE IF NOT EXISTS quantsync;")
	if err != nil {
		log.Printf("Warning: Gagal membuat database quantsync: %v", err)
	} else {
		log.Println("🛠️ [Database] Verifikasi database 'quantsync' selesai.")
	}
}

// LoadConfigsFromDB menarik kredensial dari TiDB dan menyimpannya ke Redis/Memory
func LoadConfigsFromDB() {
	if SQL == nil {
		log.Fatal("LoadConfigsFromDB dipanggil sebelum InitTiDB!")
	}

	// Menggunakan kolom 'key' dan 'value' sesuai skema Python
	rows, err := SQL.Query("SELECT `key`, `value` FROM system_configs")
	if err != nil {
		log.Printf("⚠️ Gagal mengambil configs dari DB: %v", err)
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

	log.Printf("🚀 [Config] Berhasil memuat %d konfigurasi dari TiDB ke Redis", count)
}

