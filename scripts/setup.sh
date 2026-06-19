#!/bin/bash
# MAX-Hermes Bridge setup script
# Usage: sudo bash scripts/setup.sh [user] [project_dir]
# Default: user=max-bridge, project_dir=/opt/max-hermes

set -euo pipefail

SERVICE_USER="${1:-max-bridge}"
PROJECT_DIR="${2:-/opt/max-hermes}"
CONFIG_DIR="/etc/max-bridge"
LOG_DIR="/var/log/max-bridge"

echo "============================================"
echo "  MAX-Hermes Bridge Setup"
echo "============================================"
echo "  User:    $SERVICE_USER"
echo "  Project: $PROJECT_DIR"
echo ""

# 1. Create user if needed
if ! id "$SERVICE_USER" &>/dev/null; then
    echo "[1/7] Creating user $SERVICE_USER..."
    useradd -r -m -s /bin/bash "$SERVICE_USER"
else
    echo "[1/7] User $SERVICE_USER already exists"
fi

# 2. Create directories
echo "[2/7] Creating directories..."
mkdir -p "$CONFIG_DIR" "$LOG_DIR" "$PROJECT_DIR"
chown "$SERVICE_USER:$SERVICE_USER" "$LOG_DIR" "$PROJECT_DIR"

# 3. Copy project files
echo "[3/7] Copying project files..."
if [ -d ".git" ]; then
    # Running from project dir — copy everything
    cp -r src systemd scripts requirements.txt .env.example "$PROJECT_DIR/"
    chown -R "$SERVICE_USER:$SERVICE_USER" "$PROJECT_DIR"
fi

# 4. Install Python dependencies
echo "[4/7] Installing Python dependencies..."
cd "$PROJECT_DIR"
sudo -u "$SERVICE_USER" python3 -m venv venv
sudo -u "$SERVICE_USER" venv/bin/pip install --upgrade pip
sudo -u "$SERVICE_USER" venv/bin/pip install -r requirements.txt

# 5. Copy config
echo "[5/7] Setting up configuration..."
if [ ! -f "$CONFIG_DIR/.env" ]; then
    cp "$PROJECT_DIR/.env.example" "$CONFIG_DIR/.env"
    chmod 600 "$CONFIG_DIR/.env"
    chown "$SERVICE_USER:$SERVICE_USER" "$CONFIG_DIR/.env"
    echo "  ⚠️  Edit $CONFIG_DIR/.env with your bot token!"
else
    echo "  Config already exists, skipping"
fi

# 6. Install systemd service
echo "[6/7] Installing systemd service..."
sed "s|/opt/max-hermes|$PROJECT_DIR|g; s|User=max-bridge|User=$SERVICE_USER|g" \
    "$PROJECT_DIR/systemd/max-bridge.service" > /etc/systemd/system/max-bridge.service
systemctl daemon-reload
systemctl enable max-bridge

# 7. Start service
echo "[7/7] Starting service..."
read -p "Start max-bridge now? [Y/n] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]] || [[ -z $REPLY ]]; then
    systemctl start max-bridge
    sleep 3
    systemctl status max-bridge --no-pager
fi

echo ""
echo "============================================"
echo "  Setup complete!"
echo "============================================"
echo ""
echo "Next steps:"
echo "  1. Edit $CONFIG_DIR/.env with your bot token"
echo "  2. Restart: sudo systemctl restart max-bridge"
echo "  3. Check logs: sudo journalctl -u max-bridge -f"
echo "  4. Register webhook in MAX (see README.md)"
