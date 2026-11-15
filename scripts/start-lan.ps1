param([ValidateRange(1024,65535)][int]$Port=8001)
$ErrorActionPreference='Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$python=Join-Path (Get-Location) '.venv/Scripts/python.exe'
if (!(Test-Path -LiteralPath $python)) { throw '请先安装项目依赖。' }
if (!(Test-Path -LiteralPath 'frontend/dist/index.html')) { throw '请先运行 npm --prefix frontend run build。' }
if (Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue) { throw "端口 $Port 已被占用，请关闭原服务或通过 -Port 指定其他端口。" }
$addresses=@(Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -ne '127.0.0.1' -and $_.IPAddress -notlike '169.254.*' -and $_.AddressState -eq 'Preferred' } | Select-Object -ExpandProperty IPAddress -Unique)
if (!$addresses.Count) { throw '没有找到局域网地址，请先连接Wi-Fi或有线网络。' }
$env:ZHIXING_ALLOWED_HOSTS=$addresses -join ','
$env:PYTHONPATH=Join-Path (Get-Location) 'backend'
Write-Host '局域网服务器启动；使用现有数据库和附件，不自动迁移或重置数据。'
Write-Host "本机：http://127.0.0.1:$Port/"
foreach($address in $addresses){ Write-Host "其他电脑访问：http://${address}:$Port/" }
Write-Host '两台电脑需在同一局域网；Windows防火墙如询问，请仅允许专用网络。'
Write-Host '窗口需保持打开，按Ctrl+C停止。若出现多个地址，选择正在使用的Wi-Fi或以太网地址。'
& $python -m uvicorn app.main:app --host 0.0.0.0 --port $Port
