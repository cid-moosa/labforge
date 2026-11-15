#!/usr/bin/env bash
# Project LabForge: Automated Quickstart Setup for Linux / macOS

set -e

echo "=========================================================="
echo " ⚡ Project LabForge: Automated Environment Setup"
echo "=========================================================="

# 1. Check Python
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 is not installed."
    echo "Install Python 3.10+ via your package manager (e.g. sudo apt install python3 python3-venv python3-pip)."
    exit 1
fi
echo "✔ Python detected: $(python3 --version)"

# 2. Check LibreOffice
if ! command -v soffice &> /dev/null && ! command -v libreoffice &> /dev/null; then
    echo "[WARNING] LibreOffice not found. PDF conversion requires LibreOffice."
    if command -v apt-get &> /dev/null; then
        echo "Installing LibreOffice via apt..."
        sudo apt-get update && sudo apt-get install -y libreoffice
    fi
else
    echo "✔ LibreOffice detected."
fi

# 3. Virtual Environment
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment (.venv)..."
    python3 -m venv .venv
fi

echo "Installing dependencies..."
.venv/bin/pip install --upgrade pip -q
.venv/bin/pip install -r requirements.txt -q
echo "✔ Dependencies installed successfully."

# 4. Initialize Directories
mkdir -p input output

echo ""
echo "=========================================================="
echo " 🎉 Setup Complete! How to use LabForge:"
echo "=========================================================="
echo "1. Create folders in 'input/' for each lab (e.g. input/lab 1, input/lab 2)."
echo "2. Drop your teacher's .docx template and raw screenshots into each folder."
echo "3. Run your AI Agent with the prompt in PROMPT.md, or run:"
echo "   .venv/bin/python scripts/inspect_record.py --scan"
echo "=========================================================="
