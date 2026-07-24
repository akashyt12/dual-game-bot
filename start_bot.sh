#!/bin/bash
# Jai Club Bot - Quick Start Script
# Usage: ./start_bot.sh

cd "$(dirname "$0")"

echo "=========================================="
echo "   JAI CLUB AUTO BET BOT - RUNNER"
echo "=========================================="
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "Python3 not found! Install: pkg install python"
    exit 1
fi

# Check dependencies
python3 -c "import requests, urllib3, PIL" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "Installing dependencies..."
    pip3 install requests urllib3 pillow
fi

# Check config
if [ ! -f "bot_config.json" ]; then
    echo "Config file not found!"
    echo "Creating default config..."
    cat > bot_config.json << 'EOF'
{
  "username": "",
  "password": "",
  "game": "1",
  "total_bet": 2,
  "multiplier": 2.0,
  "confidence": 55,
  "auto_restart": true,
  "max_restarts": 10
}
EOF
    echo "Edit bot_config.json with your credentials first!"
    nano bot_config.json
fi

# Check if config has credentials
USERNAME=$(python3 -c "import json; print(json.load(open('bot_config.json')).get('username',''))" 2>/dev/null)
if [ -z "$USERNAME" ]; then
    echo "Username not set in bot_config.json!"
    echo "Opening editor..."
    nano bot_config.json
fi

echo "Starting bot..."
echo "Press Ctrl+C to stop"
echo ""

python3 run_bot.py
