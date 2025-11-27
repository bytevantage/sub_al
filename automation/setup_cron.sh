#!/bin/bash
################################################################################
# Setup Automated Training Pipeline - Cron Jobs
# 
# Daily: 8:00 AM IST (daily_pipeline.py)
# Weekly: Friday 6 PM & Sunday 10 PM (weekly_retrain.sh)
#
# Author: AI Systems Operator
# Last Modified: 2025-11-20
################################################################################

set -e

PROJECT_ROOT="/Users/srbhandary/Documents/Projects/srb-algo"
cd "$PROJECT_ROOT"

echo "================================================================================"
echo "SETTING UP AUTOMATED TRAINING PIPELINE"
echo "================================================================================"
echo ""

# Make scripts executable
echo "📝 Making scripts executable..."
chmod +x automation/daily_pipeline.py
chmod +x automation/weekly_retrain.sh
chmod +x meta_controller/sac_full_retrain.py
echo "✅ Scripts are now executable"
echo ""

# Create cron job entries
echo "📅 Creating cron job entries..."
echo ""

CRON_FILE="/tmp/trading_system_cron.txt"

cat > "$CRON_FILE" << 'EOF'
# ============================================================================
# AUTOMATED TRADING SYSTEM - TRAINING PIPELINE
# Managed by: AI Systems Operator
# ============================================================================

# Daily Pipeline - 8:00 AM IST every weekday (Mon-Fri)
# Runs: Data quality check, QuantumEdge incremental, SAC online update
0 8 * * 1-5 cd /Users/srbhandary/Documents/Projects/srb-algo && /usr/bin/python3 automation/daily_pipeline.py >> logs/daily_pipeline.log 2>&1

# Weekly Full SAC Retrain - Friday 6:00 PM IST
# Runs: Complete offline retrain on all historical data (20-40 min)
0 18 * * 5 cd /Users/srbhandary/Documents/Projects/srb-algo && /bin/bash automation/weekly_retrain.sh >> logs/weekly_retrain.log 2>&1

# Weekly Full SAC Retrain - Sunday 10:00 PM IST
# Runs: Complete offline retrain on all historical data (20-40 min)
0 22 * * 0 cd /Users/srbhandary/Documents/Projects/srb-algo && /bin/bash automation/weekly_retrain.sh >> logs/weekly_retrain.log 2>&1

# Weekly Summary Report - Sunday 11:00 PM IST (after retrain)
0 23 * * 0 cd /Users/srbhandary/Documents/Projects/srb-algo && /usr/bin/python3 monitoring/weekly_report.py >> logs/weekly_report.log 2>&1

# ============================================================================
EOF

echo "Cron schedule created:"
echo ""
cat "$CRON_FILE"
echo ""

# Install cron jobs
echo "================================================================================"
echo "INSTALLATION OPTIONS"
echo "================================================================================"
echo ""
echo "Choose installation method:"
echo ""
echo "  1) Automatic (add to current user's crontab)"
echo "  2) Manual (show commands to run)"
echo "  3) Skip (just create log directories)"
echo ""
read -p "Enter choice (1-3): " choice

case $choice in
    1)
        echo ""
        echo "📥 Installing cron jobs..."
        
        # Backup existing crontab
        crontab -l > /tmp/crontab_backup_$(date +%Y%m%d_%H%M%S).txt 2>/dev/null || true
        
        # Remove old trading system cron jobs if any
        crontab -l 2>/dev/null | grep -v "daily_pipeline.py" | grep -v "weekly_retrain.sh" | crontab - 2>/dev/null || true
        
        # Add new cron jobs
        (crontab -l 2>/dev/null; cat "$CRON_FILE") | crontab -
        
        echo "✅ Cron jobs installed successfully!"
        echo ""
        echo "Verify with:"
        echo "  crontab -l | grep -A 5 'AUTOMATED TRADING'"
        ;;
    2)
        echo ""
        echo "📋 Manual installation commands:"
        echo ""
        echo "# 1. Edit crontab:"
        echo "crontab -e"
        echo ""
        echo "# 2. Add these lines:"
        cat "$CRON_FILE"
        echo ""
        echo "# 3. Save and exit"
        ;;
    3)
        echo ""
        echo "⏭️  Skipping cron installation"
        ;;
    *)
        echo ""
        echo "❌ Invalid choice"
        exit 1
        ;;
esac

echo ""

# Create log directories
echo "📁 Creating log directories..."
mkdir -p logs
mkdir -p logs/backups
echo "✅ Log directories created"
echo ""

# Create initial model directory structure
echo "📁 Creating model directories..."
mkdir -p models
mkdir -p models/backups
echo "✅ Model directories created"
echo ""

# Test daily pipeline (dry run)
echo "================================================================================"
echo "TESTING DAILY PIPELINE (DRY RUN)"
echo "================================================================================"
echo ""
read -p "Run test? (y/n): " test_choice

if [ "$test_choice" = "y" ]; then
    echo ""
    echo "🧪 Running daily pipeline test..."
    python3 automation/daily_pipeline.py --dry-run 2>&1 | head -50
    echo ""
    echo "✅ Test complete (check output above)"
fi

echo ""
echo "================================================================================"
echo "SETUP COMPLETE"
echo "================================================================================"
echo ""
echo "📊 Summary:"
echo "   • Daily pipeline: 8:00 AM IST (Mon-Fri)"
echo "   • Weekly retrain: Friday 6 PM & Sunday 10 PM"
echo "   • Logs: logs/daily_pipeline.log, logs/weekly_retrain.log"
echo "   • Models: models/sac_prod_latest.pth (auto-updated)"
echo ""
echo "🎯 Next steps:"
echo "   1. Set environment variables:"
echo "      export TELEGRAM_BOT_TOKEN='your_token'"
echo "      export TELEGRAM_CHAT_ID='your_chat_id'"
echo ""
echo "   2. Test manually:"
echo "      python3 automation/daily_pipeline.py"
echo ""
echo "   3. Monitor logs:"
echo "      tail -f logs/daily_pipeline.log"
echo ""
echo "================================================================================"

exit 0
