# Listen-WebSocket.ps1
# Digunakan untuk mendengarkan broadcast dari Go Gateway via WebSocket

$url = "ws://localhost:8443/ws"
Write-Host "Connecting to WebSocket: $url" -ForegroundColor Cyan

try {
    $ws = New-Object System.Net.WebSockets.ClientWebSocket
    $ct = New-Object System.Threading.CancellationTokenSource
    $task = $ws.ConnectAsync($url, $ct.Token)
    $task.Wait()

    Write-Host "✅ Connected to WebSocket Hub!" -ForegroundColor Green

    $buffer = New-Object byte[] 4096
    while ($ws.State -eq [System.Net.WebSockets.WebSocketState]::Open) {
        $segment = New-Object System.ArraySegment[byte] -ArgumentList @(,$buffer)
        $receiveTask = $ws.ReceiveAsync($segment, $ct.Token)
        $receiveTask.Wait()
        
        $result = $receiveTask.Result
        $message = [System.Text.Encoding]::UTF8.GetString($buffer, 0, $result.Count)
        
        if ($message.Trim()) {
            Write-Host "[SIGNAL RECEIVED] $(Get-Date -Format 'HH:mm:ss'): " -NoNewline -ForegroundColor Yellow
            Write-Host $message
        }
    }
}
catch {
    Write-Error "Failed to connect or connection lost: $_"
}
finally {
    if ($ws) { $ws.Dispose() }
}
