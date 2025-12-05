#!/usr/bin/env bash
set -euo pipefail

# Non-interactive Hostinger setup script
# Usage (on the host):
#   export DB_HOST=localhost DB_PORT=5432 DB_NAME=u570718221_srbalgo DB_USER=u570718221_srbhandaryalgo DB_PASSWORD='...'
#   bash hostinger_setup_noninteractive.sh /home/u570718221/public_html/srb-algo
# The script will use either environment variables, or a .env file in the repo root.

DEPLOY_DIR=${1:-$HOME/public_html/srb-algo}
PYTHON=python3
REQUIREMENTS_FILE=requirements.txt

echo "[setup] Deploy dir: $DEPLOY_DIR"

# Ensure apt is available and we can install packages
SKIP_APT=false
if ! command -v apt-get >/dev/null 2>&1 || ! command -v sudo >/dev/null 2>&1; then
  echo "[warn] apt-get or sudo not available - skipping system package installs; continuing with venv/pip-only install." >&2
  SKIP_APT=true
else
  echo "[setup] Updating apt and installing packages"
  sudo apt-get update -y
  sudo apt-get install -y git $PYTHON-venv $PYTHON-pip build-essential libpq-dev postgresql-client || true
fi

# Clone or pull repository
if [ -d "$DEPLOY_DIR/.git" ]; then
  echo "[setup] Repo exists - pulling"
  cd "$DEPLOY_DIR"
  git pull --rebase || true
else
  echo "[setup] Repo not present. Attempting to clone from origin (must be configured on host)."
  cd $(dirname "$DEPLOY_DIR")
  git clone --depth=1 . "$DEPLOY_DIR" || echo "[warn] Please clone the repository manually into $DEPLOY_DIR";
fi

cd "$DEPLOY_DIR"

# Create venv
if [ ! -d "venv" ]; then
  echo "[setup] Creating Python virtualenv"
  $PYTHON -m venv venv
fi
. venv/bin/activate

# Install deps
if [ -f "$REQUIREMENTS_FILE" ]; then
  echo "[setup] Installing requirements from $REQUIREMENTS_FILE"
  pip install --upgrade pip
  pip install -r $REQUIREMENTS_FILE
else
  echo "[setup] requirements.txt missing; installing minimal runtime deps"
  pip install --upgrade pip setuptools
  pip install sqlalchemy psycopg2-binary python-dotenv
fi

# Prepare .env if not present
if [ ! -f .env ]; then
  echo "[setup] Creating .env from deploy/.env.example"
  if [ -f deploy/.env.example ]; then
    cp deploy/.env.example .env
  else
    cat > .env <<'EOF'
ENV=production
DB_HOST=localhost
DB_PORT=5432
DB_NAME=
DB_USER=
DB_PASSWORD=
EOF
  fi
  echo "[setup] Please edit .env with DB credentials or export DB_* env variables before continuing."
fi

# Prefer env vars if set
DB_HOST=${DB_HOST:-$(grep -E '^DB_HOST=' .env 2>/dev/null | cut -d'=' -f2- || echo '')}
DB_PORT=${DB_PORT:-$(grep -E '^DB_PORT=' .env 2>/dev/null | cut -d'=' -f2- || echo '5432')}
DB_NAME=${DB_NAME:-$(grep -E '^DB_NAME=' .env 2>/dev/null | cut -d'=' -f2- || echo '')}
DB_USER=${DB_USER:-$(grep -E '^DB_USER=' .env 2>/dev/null | cut -d'=' -f2- || echo '')}
DB_PASSWORD=${DB_PASSWORD:-$(grep -E '^DB_PASSWORD=' .env 2>/dev/null | cut -d'=' -f2- || echo '')}

if [ -z "$DB_NAME" ] || [ -z "$DB_USER" ] || [ -z "$DB_PASSWORD" ]; then
  echo "[warning] Database credentials incomplete. Set DB_NAME, DB_USER, DB_PASSWORD in env or .env and re-run the script. Exiting." >&2
  exit 1
fi

# Run DB table creation
echo "[setup] Running database table creation (SQLAlchemy models)"
export DB_HOST DB_PORT DB_NAME DB_USER DB_PASSWORD
python3 create_database_tables.py || echo "[warn] create_database_tables.py failed - please check DB connectivity and credentials"

# Prepare data folders
mkdir -p data/logs data/clean_regime_2025

# Create systemd unit (if sudo is available)
SERVICE_FILE="/etc/systemd/system/trading.service"
if sudo -n true 2>/dev/null; then
  echo "[setup] Creating systemd service file at $SERVICE_FILE"
  sudo tee $SERVICE_FILE > /dev/null <<EOF
[Unit]
Description=srb-algo trading engine
After=network.target

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=$DEPLOY_DIR
EnvironmentFile=$DEPLOY_DIR/.env
ExecStart=$DEPLOY_DIR/venv/bin/python3 $DEPLOY_DIR/backend/main.py
Restart=on-failure
RestartSec=10
StandardOutput=syslog
StandardError=syslog
SyslogIdentifier=srb-algo

[Install]
WantedBy=multi-user.target
EOF
  sudo systemctl daemon-reload || true
  sudo systemctl enable trading.service || true
  sudo systemctl start trading.service || true
  echo "[setup] Attempted to enable and start systemd service. Check 'sudo journalctl -u trading.service -f' for logs."
else
  echo "[setup] No sudo privileges; skipping systemd unit creation. You can run the service manually:" 
  echo "    . venv/bin/activate && python3 backend/main.py"
fi

# Run DB verification script
echo "[setup] Running DB verification: deploy/check_option_chain.py"
python3 deploy/check_option_chain.py || echo "[warn] DB verification script failed - check logs"

echo "[setup] Finished. If you want me to validate outputs, paste the logs or the 'python3 deploy/check_option_chain.py' output here." 
