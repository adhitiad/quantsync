# Send-MockSignal.ps1
# Prerequisite: winget install grpcurl

# Alamat gRPC Server (Python AI Engine)
$server = "localhost:50051"
$proto_path = "../../proto/signal.proto"

Write-Host "Triggering Mock Signal Request to Engine: $server" -ForegroundColor Cyan

# Contoh request untuk EUR/USD
$json_payload = '{"asset": "EUR/USD", "category": "forex"}'

# Menjalankan grpcurl
# Jika service menggunakan reflection, kita tidak butuh -proto
# Namun untuk keamanan dan kejelasan, kita sertakan path proto
try {
    Write-Host "Calling GetTradingSignal..." -ForegroundColor Gray
    & grpcurl -plaintext -import-path ../../proto -proto signal.proto -d "$json_payload" $server signal.SignalService/GetTradingSignal
    
    Write-Host "`n✅ Request completed!" -ForegroundColor Green
}
catch {
    Write-Error "Gagal menjalankan grpcurl. Pastikan sudah terinstal: winget install grpcurl"
}
