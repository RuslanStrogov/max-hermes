#!/bin/bash
# MAX-Hermes Bridge setup script
# Run as root: sudo bash scripts/setup.sh

set -euo pipefail

PROJECT_DIR="/mnt/data/projects/max-hermes"
CONFIG_DIR="/etc/max-bridge"
LOG_DIR="/var/log/max-bridge"
SERVICE_USER="ruslan"

echo "============================================"
echo "  MAX-Hermes Bridge Setup"
echo "============================================"

# 1. Create directories
echo "[1/6] Creating directories..."
mkdir -p "$CONFIG_DIR" "$LOG_DIR"
chown "$SERVICE_USER:$SERVICE_USER" "$LOG_DIR"

# 2. Install Python dependencies
echo "[2/6] Installing Python dependencies..."
cd "$PROJECT_DIR"
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 3. Copy config
echo "[3/6] Setting up configuration..."
if [ ! -f "$CONFIG_DIR/.env" ]; then
    cp "$PROJECT_DIR/.env.example" "$CONFIG_DIR/.env"
    echo "  ⚠️  Edit $CONFIG_DIR/.env with your bot token and secrets!"
fi
chmod 600 "$CONFIG_DIR/.env"
chown "$SERVICE_USER:$SERVICE_USER" "$CONFIG_DIR/.env"

# 4. Install systemd service
echo "[4/6] Installing systemd service..."
cp "$PROJECT_DIR/systemd/max-bridge.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable max-bridge

# 5. Configure Hermes webhook
echo "[5/6] Configuring Hermes webhook..."
echo "  Make sure Hermes webhook adapter is enabled on port 8644"
echo "  Check: hermes gateway status"

# 6. Start service
echo "[6/6] Starting service..."
read -p "Start max-bridge now? [Y/n] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]] || [[ -z $REPLY ]]; then
    systemctl start max-bridge
    sleep 2
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
echo ""
