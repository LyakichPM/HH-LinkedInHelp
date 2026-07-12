<#
.SYNOPSIS
    hh-agent setup script for Windows (PowerShell)

.DESCRIPTION
    Creates config.local.json from example, installs Python dependencies,
    and installs Playwright Chromium.

.USAGE
    .\setup.ps1
#>

param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host "=== hh-agent setup ===" -ForegroundColor Cyan

# Create config if not exists
$configExample = "config\config.example.json"
$configLocal = "config.local.json"

if (-not (Test-Path $configLocal)) {
    if (Test-Path $configExample) {
        Copy-Item $configExample $configLocal -Force
        Write-Host "Created config.local.json — edit it with your tokens" -ForegroundColor Green
    } else {
        Write-Host "Error: config.example.json not found" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "config.local.json already exists" -ForegroundColor Yellow
}

# Install Python dependencies
Write-Host "`nInstalling Python dependencies..." -ForegroundColor Cyan
try {
    pip install -e .
    Write-Host "Dependencies installed" -ForegroundColor Green
} catch {
    Write-Host "Warning: 'pip install -e .' failed, trying manual install..." -ForegroundColor Yellow
    pip install playwright requests pyyaml python-dotenv
}

# Install Playwright + Chromium
Write-Host "`nInstalling Playwright Chromium..." -ForegroundColor Cyan
try {
    python -m playwright install chromium
    Write-Host "Playwright Chromium installed" -ForegroundColor Green
} catch {
    Write-Host "Warning: 'python -m playwright install chromium' failed. Try running it manually." -ForegroundColor Yellow
}

Write-Host "`n=== Done ===" -ForegroundColor Cyan
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Edit config.local.json with your Telegram token, proxy" -ForegroundColor White
Write-Host "  2. Run: hh auth login   (to save hh.ru cookies)" -ForegroundColor White
Write-Host "  3. Run: hh search 'product manager igaming'   (test)" -ForegroundColor White