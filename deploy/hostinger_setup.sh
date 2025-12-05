#!/usr/bin/env bash
set -euo pipefail

# Hostinger setup script (no-root user assumed)
# Usage on Hostinger server (run as the user you will use to run the app):
#   chmod +x hostinger_setup.sh
#   ./hostinger_setup.sh /path/to/deploy

DEPLOY_DIR=${1:-$HOME/public_html/srb-algo}
PYTHON=python3

echo "1. Update system packages (skipped if sudo/apt unavailable)"
if command -v apt-get >/dev/null 2>&1 && command -v sudo >/dev/null 2>&1; then
  echo "Updating packages (requires sudo)..."
  sudo apt-get update && sudo apt-get upgrade -y

  echo "2. Install runtime dependencies"
  sudo apt-get install -y git $PYTHON-venv $PYTHON-pip build-essential libpq-dev postgresql-client
else
  echo "Warning: sudo or apt-get not available. Skipping system package installs. Proceeding with venv/pip-only install."
fi

echo "3. Clone repository (or pull if exists)"
if [ -d "$DEPLOY_DIR/.git" ]; then
  echo "Repository exists — pulling latest"
  cd "$DEPLOY_DIR"
  git pull --rebase
else
  git clone --depth=1 https://github.com/your-org/your-repo.git "$DEPLOY_DIR" || {
    echo "Please clone your repo into $DEPLOY_DIR manually (private repo)";
    exit 1;
  }
fi

cd "$DEPLOY_DIR"

echo "4. Create Python virtualenv"
$PYTHON -m venv venv
. venv/bin/activate

echo "5. Install Python dependencies"
if [ -f requirements.txt ]; then
  pip install --upgrade pip
  pip install -r requirements.txt
else
  echo "requirements.txt not found — attempting to install minimal runtime requirements"
  pip install --upgrade pip setuptools
  pip install sqlalchemy psycopg2-binary python-dotenv
fi

echo "6. Create env file from example (edit with your DB/secret values)"
if [ ! -f .env ]; then
  cp deploy/.env.example .env
  echo "Created .env from deploy/.env.example — edit it with your secrets now."
fi

echo "7. Run DB migrations / create tables"
# The project uses SQLAlchemy models; create tables if needed
python3 create_database_tables.py || echo "create_database_tables.py run failed — check DB connectivity and credentials"

echo "8. Create logs and data directories"
mkdir -p data/logs data/clean_regime_2025

if command -v sudo >/dev/null 2>&1 && sudo -n true 2>/dev/null; then
  echo "9. (Optional) Setup systemd service (requires sudo)"
  sudo cp deploy/trading.service /etc/systemd/system/trading.service
  sudo systemctl daemon-reload
  sudo systemctl enable trading.service
  sudo systemctl start trading.service
else
  echo "9. (Optional) Setup systemd service skipped (no sudo). To install manually, run the commands printed in deploy/trading.service with sudo from an account with privileges."
fi

echo "Setup script finished. Edit .env and then start the service or run the app manually using the venv:"
echo "  . venv/bin/activate && python3 backend/main.py"

exit 0
