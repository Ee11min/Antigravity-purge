Get-Process Antigravity -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 3
$env:HTTP_PROXY='http://127.0.0.1:7896'; $env:HTTPS_PROXY=$env:HTTP_PROXY
$env:ALL_PROXY='socks5://127.0.0.1:7896'
$env:NO_PROXY='localhost,127.0.0.1,::1,*.local,127.*'
Remove-Item Env:ELECTRON_RUN_AS_NODE -ErrorAction SilentlyContinue
Start-Process "$env:LOCALAPPDATA\Programs\antigravity\Antigravity.exe" -ArgumentList '--remote-debugging-port=9223'
