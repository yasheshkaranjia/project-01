#!/data/data/com.termux/files/usr/bin/bash
set -e

echo "=================================="
echo " project-01 — Termux AI Bot Setup"
echo "=================================="

echo "Setting up storage access..."
termux-setup-storage

echo "Updating packages..."
yes | pkg update
yes | pkg upgrade

echo "Installing Python..."
yes | pkg install python

echo "Installing pip dependencies..."
pip install --upgrade pip
pip install requests

echo ""
echo "=================================="
echo "Installation complete!"
echo ""
echo "Next steps:"
echo "1. Get an API key from https://console.anthropic.com"
echo "2. Set it as an environment variable:"
echo "   export ANTHROPIC_API_KEY=\"sk-ant-your-real-key-here\""
echo "   (add that line to ~/.bashrc to make it permanent)"
echo "3. Run the bot:"
echo "   python aibot.py \"your request here\""
echo "=================================="
