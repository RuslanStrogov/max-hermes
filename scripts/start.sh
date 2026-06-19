#!/bin/bash
# Quick start script for MAX-Hermes Bridge

set -euo pipefail

PROJECT_DIR="/mnt/data/projects/max-hermes"
cd "$PROJECT_DIR"

echo "============================================"
echo "  MAX-Hermes Bridge — Quick Start"
echo "============================================"
echo ""

# Check .env exists
if [ ! -f .env ]; then
    echo "❌ .env not found! Copy .env.example and edit:"
    echo "   cp .env.example .env"
    echo "   nano .env"
    exit 1
fi

# Check venv
if [ ! -d "venv" ]; then
    echo "[1/4] Creating virtual environment..."
    python3 -m venv venv
fi

echo "[2/4] Installing dependencies..."
source venv/bin/activate
pip install -q -r requirements.txt

echo "[3/4] Testing MAX API connection..."
MAX_TOKEN=$(grep MAX_BOT_TOKEN .env | cut -d= -f2)
BOT_INFO=$(curl -s "https://platform-api.max.ru/me" -H "Authorization: $MAX_TOKEN" 2>/dev/null)

if echo "$BOT_INFO" | grep -q "user_id"; then
    BOT_NAME=$(echo "$BOT_INFO" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('name','?'))" 2>/dev/null)
    BOT_USERNAME=$(echo "$BOT_INFO" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('username','?'))" 2>/dev/null)
    echo "  ✅ Connected to MAX: $BOT_NAME (@$BOT_USERNAME)"
else
    echo "  ❌ Cannot connect to MAX API"
    echo "  Response: $BOT_INFO"
    echo ""
    echo "  Check your MAX_BOT_TOKEN in .env"
    exit 1
fi

echo "[4/4] Starting bridge..."
echo ""
echo "  Press Ctrl+C to stop"
echo ""

python -m src.main
