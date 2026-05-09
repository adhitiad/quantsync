# Run-LocalTest.ps1
# Orkestrator Utama QuantSync Local Testing Suite

Write-Host "--- QuantSync Local Orchestrator ---" -ForegroundColor Magenta

# 1. Start Python AI Engine (Server gRPC)
Write-Host "[1/3] Starting Python AI Engine..." -ForegroundColor Cyan
$pythonEngineTask = {
    cd f:\quantsync\quantsync-ai-engine
    python server.py
}
Start-Process powershell -ArgumentList "-NoExit", "-Command", $pythonEngineTask -WindowStyle Normal

# 2. Start Go Gateway (WebSocket Hub & gRPC Client)
Write-Host "[2/3] Starting Go Gateway..." -ForegroundColor Cyan
$goGatewayTask = {
    cd f:\quantsync\quantsync-gateway
    go run main.go
}
Start-Process powershell -ArgumentList "-NoExit", "-Command", $goGatewayTask -WindowStyle Normal

# Berikan waktu sejenak agar server siap
Start-Sleep -Seconds 5

# 3. Start WSS Listener
Write-Host "[3/3] Starting WebSocket Listener..." -ForegroundColor Cyan
$wssListenerTask = {
    cd f:\quantsync\scripts\test
    .\Listen-WebSocket.ps1
}
Start-Process powershell -ArgumentList "-NoExit", "-Command", $wssListenerTask -WindowStyle Normal

Write-Host "`n✅ All components triggered!" -ForegroundColor Green
Write-Host "Use Send-MockSignal.ps1 to trigger test signals manually." -ForegroundColor Yellow
