# Telex Bootstrap Script for Windows (PowerShell)
# Sets up the complete local development environment with zero Docker requirement.

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "               Telex Contributor Bootstrap                " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Check Python version
Write-Host "`n[1/6] Checking Python installation..." -ForegroundColor Yellow
$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Error "Python is not installed or not in PATH. Please install Python 3.10+."
    exit 1
}
Write-Host "Found $pythonVersion" -ForegroundColor Green

# 2. Check Node & npm
Write-Host "`n[2/6] Checking Node.js and npm..." -ForegroundColor Yellow
$nodeVersion = node --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Error "Node.js is not installed or not in PATH. Please install Node.js 18+."
    exit 1
}
Write-Host "Found Node $nodeVersion" -ForegroundColor Green

# 3. Environment configuration (.env)
Write-Host "`n[3/6] Setting up environment variables (.env)..." -ForegroundColor Yellow
$envPath = Join-Path $PSScriptRoot "..\.env"
$envExamplePath = Join-Path $PSScriptRoot "..\.env.example"

if (-not (Test-Path $envPath)) {
    Write-Host "Creating .env from .env.example with secure random secrets..."
    $content = Get-Content $envExamplePath -Raw

    # Generate secure keys via Python
    $keygenScript = @"
import secrets
from cryptography.fernet import Fernet
print(f"{secrets.token_urlsafe(32)}|{Fernet.generate_key().decode()}")
"@
    $keys = python -c $keygenScript
    $secretParts = $keys.Split('|')
    $jwtSecret = $secretParts[0].Trim()
    $encKey = $secretParts[1].Trim()

    $content = $content -replace "NEXTAUTH_SECRET=.*", "NEXTAUTH_SECRET=$jwtSecret"
    $content = $content -replace "TELEX_ENCRYPTION_KEY=.*", "TELEX_ENCRYPTION_KEY=$encKey"
    $content = $content -replace "DATABASE_URL=.*", "DATABASE_URL=sqlite+aiosqlite:///telex.db"

    Set-Content -Path $envPath -Value $content -Encoding utf8
    Write-Host "Generated .env configured for local zero-Docker SQLite." -ForegroundColor Green
} else {
    Write-Host ".env already exists. Preserving existing configuration." -ForegroundColor Green
}

# 4. Install Python dependencies
Write-Host "`n[4/6] Installing Python dependencies..." -ForegroundColor Yellow
python -m pip install --upgrade pip
python -m pip install -r (Join-Path $PSScriptRoot "..\apps\api\requirements.txt")
python -m pip install -e (Join-Path $PSScriptRoot "..\packages\telex-core")
Write-Host "Python dependencies installed successfully." -ForegroundColor Green

# 5. Install Node dependencies
Write-Host "`n[5/6] Installing Node dependencies..." -ForegroundColor Yellow
$webDir = Join-Path $PSScriptRoot "..\apps\web"
Push-Location $webDir
try {
    npm install
    Write-Host "Node dependencies installed successfully." -ForegroundColor Green
} finally {
    Pop-Location
}

# 6. Initialize database and verify test suite
Write-Host "`n[6/6] Initializing database and running test suite..." -ForegroundColor Yellow
python (Join-Path $PSScriptRoot "seed_demo.py") --sqlite

Write-Host "`nRunning test verification..." -ForegroundColor Yellow
python -m pytest (Join-Path $PSScriptRoot "..\packages\telex-core\tests")
if ($LASTEXITCODE -eq 0) {
    Write-Host "Core verification tests passed!" -ForegroundColor Green
} else {
    Write-Warning "Some tests failed. Please review the output above."
}

Write-Host "`n==========================================================" -ForegroundColor Cyan
Write-Host "  Telex development environment ready! Run 'npm run dev'  " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan
