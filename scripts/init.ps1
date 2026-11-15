param([switch]$Demo)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$env:PYTHONUTF8 = '1'
$env:PYTHONPATH = Join-Path $projectRoot 'backend'
if (!$env:ZHIXING_DATA) { $env:ZHIXING_DATA = Join-Path $projectRoot 'backend/data' }
$action = 'init'
if ($Demo) { $action = 'demo' }
& (Join-Path $projectRoot '.venv\Scripts\python.exe') -m app.cli $action
if ($LASTEXITCODE -ne 0) { throw 'Initialization failed.' }
