#!/bin/bash
# Setup script for trading engine monitoring

PROJECT_DIR="/Users/srbhandary/Documents/Projects/srb-algo"
CRON_FILE="$HOME/.crontab_backup_$(date +%Y%m%d_%H%M%S)"

echo "Setting up trading engine monitoring..."

# Backup existing crontab
crontab -l > "$CRON_FILE" 2>/dev/null || touch "$CRON_FILE"

# Add cron job to start health monitor at system boot and restart if needed
(crontab -l 2>/dev/null; echo "@reboot cd $PROJECT_DIR && python3 health_monitor.py >> data/logs/health_monitor.log 2>&1 &") | crontab -

# Add cron job to check health monitor every 5 minutes and restart if needed
(crontab -l 2>/dev/null; echo "*/5 * * * * cd $PROJECT_DIR && pgrep -f health_monitor.py > /dev/null || (python3 health_monitor.py >> data/logs/health_monitor.log 2>&1 &)") | crontab -

echo "✅ Cron jobs added:"
echo "  - Health monitor will start at system reboot"
echo "  - Health monitor will be checked every 5 minutes"
echo ""
echo "Current crontab:"
crontab -l
echo ""
echo "Backup saved to: $CRON_FILE"
echo ""
echo "To restore backup: crontab $CRON_FILE"
