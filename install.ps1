# Project LabForge: Automated Quickstart Setup for Windows
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " ⚡ Project LabForge: Automated Environment Setup" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Check Python
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    Write-Host "[ERROR] Python is not installed or not in PATH." -ForegroundColor Red
    Write-Host "Install Python 3.10+ from https://www.python.org/ or via: winget install Python.Python.3.12" -ForegroundColor Yellow
    exit 1
}
Write-Host "✔ Python detected: $(python --version)" -ForegroundColor Green

# 2. Check LibreOffice
$sofficePath = "C:\Program Files\LibreOffice\program\soffice.exe"
$sofficeCmd = Get-Command soffice -ErrorAction SilentlyContinue
if (-not (Test-Path $sofficePath) -and -not $sofficeCmd) {
    Write-Host "[WARNING] LibreOffice not found. PDF conversion requires LibreOffice." -ForegroundColor Yellow
    Write-Host "Installing LibreOffice via winget..." -ForegroundColor Cyan
    winget install --id TheDocumentFoundation.LibreOffice -e --accept-source-agreements --accept-package-agreements
} else {
    Write-Host "✔ LibreOffice detected (ready for headless PDF compilation)." -ForegroundColor Green
}

# 3. Virtual Environment & Dependencies
if (-not (Test-Path ".venv")) {
    Write-Host "Creating Python virtual environment (.venv)..." -ForegroundColor Cyan
    python -m venv .venv
}

Write-Host "Installing dependencies..." -ForegroundColor Cyan
& .venv\Scripts\pip.exe install --upgrade pip -q
& .venv\Scripts\pip.exe install -r requirements.txt -q
Write-Host "✔ Python dependencies installed successfully." -ForegroundColor Green

# 4. Initialize Input / Output Folders
if (-not (Test-Path "input")) {
    New-Item -ItemType Directory -Path "input" -Force | Out-Null
}
if (-not (Test-Path "output")) {
    New-Item -ItemType Directory -Path "output" -Force | Out-Null
}

Write-Host "`n==========================================================" -ForegroundColor Green
Write-Host " 🎉 Setup Complete! How to use LabForge:" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "1. Create folders in 'input/' for each lab (e.g. input/lab 1, input/lab 2)."
Write-Host "2. Drop your teacher's .docx template and raw screenshots into each folder."
Write-Host "3. Run your AI Agent with the prompt in PROMPT.md, or run:" -ForegroundColor Cyan
Write-Host "   .venv\Scripts\python.exe scripts/inspect_record.py --scan" -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Green
