# Run server with output logging
Write-Host "Starting CleanCodeAgent Server with Logging..." -ForegroundColor Green

cd "$PSScriptRoot\src\localize_agent"

# Run server and save all output to file
python server.py 2>&1 | Tee-Object -FilePath "server_logs.txt"

pause
