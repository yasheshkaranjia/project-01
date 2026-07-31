#!/data/data/com.termux/files/usr/bin/bash
set -e

REPO_URL="https://github.com/yasheshkaranjia/project-01.git"
REPO_DIR="$HOME/project-01"

echo "=================================="
echo " Termux AI Bot — Installer"
echo "=================================="

echo "Setting up storage access..."
termux-setup-storage

echo "Updating packages..."
yes | pkg update
yes | pkg upgrade

echo "Installing dependencies..."
yes | pkg install git python gum jq -y

echo "Installing pip dependencies..."
pip install requests

if [ -d "$REPO_DIR/.git" ]; then
    echo "Repo already exists, pulling latest..."
    cd "$REPO_DIR"
    git pull
else
    echo "Cloning repo..."
    git clone "$REPO_URL" "$REPO_DIR"
    cd "$REPO_DIR"
fi

chmod +x termux-ai.sh install.sh 2>/dev/null || true

echo ""
echo "=================================="
echo "Installation complete!"
echo "Launching Termux AI Bot..."
echo "=================================="
echo ""

exec bash "$REPO_DIR/termux-ai.sh"
