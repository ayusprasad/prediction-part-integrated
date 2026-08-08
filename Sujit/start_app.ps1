param(
    [string]$BindHost = "127.0.0.1",
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "The project virtual environment was not found at $Python. Create it first with: python -m venv .venv"
}

Set-Location -LiteralPath $ProjectRoot
Write-Host "Starting Port Land RAG at http://${BindHost}:${Port}" -ForegroundColor Cyan
Write-Host "Keep this terminal open while using the application." -ForegroundColor Yellow

& $Python -m uvicorn app.api_server:app --host $BindHost --port $Port
exit $LASTEXITCODE
