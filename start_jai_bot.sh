#!/bin/bash
# JAI CLUB BOT - Full Setup & Start
cd "$(dirname "$0")"

echo "=========================================="
echo "   🎰 JAI CLUB AUTO BOT - SETUP 🎰"
echo "=========================================="
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 not found!"
    echo "Installing..."
    pkg install python -y 2>/dev/null || apt install python3 -y 2>/dev/null
fi

# Install dependencies
echo "📦 Installing dependencies..."
pip3 install -r requirements.txt --break-system-packages 2>/dev/null || pip3 install -r requirements.txt

echo ""
echo "✅ Setup complete!"
echo ""
echo "🚀 Starting JAI CLUB BOT..."
echo "Press Ctrl+C to stop"
echo ""

python3 jai_full_bot.py
