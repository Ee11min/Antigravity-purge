# Antigravity 登录/连不上后端的修法：给 Go 后端补上代理环境变量
#
# 症状：
#   failed to get load code assist response: Post "https://daily-cloudcode-pa.googleapis.com/v1internal:loadCodeAssist":
#   Post "https://oauth2.googleapis.com/token": dial tcp [2404:6800:4008:c15::5f]:443:
#   connectex: A connection attempt failed ...
#
# 根因：language_server.exe 是 Go 程序，Go 的 ProxyFromEnvironment 只读 HTTP_PROXY /
# HTTPS_PROXY / NO_PROXY 环境变量，不看 Windows 系统代理注册表。FlClash 开了系统代理，
# Electron 前端走代理没事，Go 后端却直连，于是落到不通的 IPv6 上。
#
# 用法：
#   powershell -ExecutionPolicy Bypass -File scripts\fix-proxy.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\fix-proxy.ps1 -Port 7890 -Persist
param(
    [string]$ProxyHost = '127.0.0.1',
    [int]$Port = 7896,
    [switch]$Persist
)

$http = "http://${ProxyHost}:${Port}"
$all  = "socks5://${ProxyHost}:${Port}"
$no   = 'localhost,127.0.0.1,::1,*.local,127.*,10.*,172.16.*,172.17.*,172.18.*,172.19.*,172.2*.*,172.30.*,172.31.*,192.168.*'

# 先确认代理真的能用，否则改了也是白改
$probe = Test-NetConnection -ComputerName $ProxyHost -Port $Port -InformationLevel Quiet -WarningAction SilentlyContinue
if (-not $probe) {
    Write-Error "代理 ${ProxyHost}:${Port} 连不上，先确认 FlClash / Clash 已启动并监听该端口。"
    exit 1
}
Write-Output "代理 ${ProxyHost}:${Port} 可用"

if ($Persist) {
    [Environment]::SetEnvironmentVariable('HTTP_PROXY',  $http, 'User')
    [Environment]::SetEnvironmentVariable('HTTPS_PROXY', $http, 'User')
    [Environment]::SetEnvironmentVariable('ALL_PROXY',   $all,  'User')
    [Environment]::SetEnvironmentVariable('NO_PROXY',    $no,   'User')
    Write-Output '已写入用户级环境变量（新开进程生效）'
}

# 当前会话也要有，Start-Process 才能继承
$env:HTTP_PROXY  = $http
$env:HTTPS_PROXY = $http
$env:ALL_PROXY   = $all
$env:NO_PROXY    = $no

Get-Process Antigravity, language_server -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 3
Remove-Item Env:ELECTRON_RUN_AS_NODE -ErrorAction SilentlyContinue
Start-Process "$env:LOCALAPPDATA\Programs\antigravity\Antigravity.exe" `
    -ArgumentList '--remote-debugging-port=9223'
Write-Output '已带代理变量重启，等 30 秒左右界面就恢复'
