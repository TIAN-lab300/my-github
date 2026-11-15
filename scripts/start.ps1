param([int]$Port = 8000, [switch]$Check)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath $pythonPath)) { throw 'Missing .venv. See RUNNING.md.' }
$env:PYTHONUTF8 = '1'
$arguments = @((Join-Path $PSScriptRoot 'run.py'), '--port', $Port)
if ($Check) { $arguments += '--check' }
& $pythonPath @arguments
if ($LASTEXITCODE -ne 0) { throw "Startup failed: $LASTEXITCODE" }

