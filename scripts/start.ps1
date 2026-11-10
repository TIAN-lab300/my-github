$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (!(Test-Path -LiteralPath '.venv/Scripts/python.exe')) { throw 'Install Python dependencies as described in README first.' }
$env:PYTHONPATH = Join-Path (Get-Location) 'backend'
& .venv/Scripts/python.exe -m alembic -c backend/alembic.ini upgrade head
if ($LASTEXITCODE -ne 0) { throw 'Database migration failed.' }
& .venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
