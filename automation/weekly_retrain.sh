#!/bin/bash
################################################################################
# WEEKLY SAC FULL RETRAIN - Systems Operator
# 
# Runs: Friday 6 PM IST & Sunday 10 PM IST
# Duration: 20-40 minutes
# Output: models/sac_prod_latest.pth + versioned backup
#
# Author: AI Systems Operator
# Last Modified: 2025-11-20
################################################################################

set -e  # Exit on error

echo "================================================================================"
echo "SAC FULL OFFLINE RETRAIN - WEEKLY"
echo "================================================================================"
echo "Started: $(date '+%Y-%m-%d %H:%M:%S IST')"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ROOT="/Users/srbhandary/Documents/Projects/srb-algo"
cd "$PROJECT_ROOT"

MODEL_DIR="models"
BACKUP_DIR="models/backups"
TIMESTAMP=$(date '+%Y%m%d')
DAY_OF_WEEK=$(date '+%A')

echo "📊 Configuration:"
echo "   Project: $PROJECT_ROOT"
echo "   Day: $DAY_OF_WEEK"
echo "   Timestamp: $TIMESTAMP"
echo ""

# Verify this should run today
if [[ "$DAY_OF_WEEK" != "Friday" && "$DAY_OF_WEEK" != "Sunday" ]]; then
    echo -e "${YELLOW}⚠️  WARNING: Not a scheduled retrain day (Friday/Sunday)${NC}"
    echo "   Current day: $DAY_OF_WEEK"
    echo "   Exiting..."
    exit 0
fi

echo -e "${GREEN}✅ Confirmed: This is a full retrain day ($DAY_OF_WEEK)${NC}"
echo ""

################################################################################
# STEP 1: Backup current model
################################################################################
echo "================================================================================"
echo "STEP 1: BACKUP CURRENT MODEL"
echo "================================================================================"

mkdir -p "$BACKUP_DIR"

if [ -f "$MODEL_DIR/sac_prod_latest.pth" ]; then
    BACKUP_PATH="$BACKUP_DIR/sac_${TIMESTAMP}_pre_retrain.pth"
    cp "$MODEL_DIR/sac_prod_latest.pth" "$BACKUP_PATH"
    echo -e "${GREEN}✅ Backed up current model to: $BACKUP_PATH${NC}"
else
    echo -e "${YELLOW}⚠️  No existing model found - first time retrain${NC}"
fi

echo ""

################################################################################
# STEP 2: Run full offline retrain
################################################################################
echo "================================================================================"
echo "STEP 2: FULL OFFLINE RETRAIN"
echo "================================================================================"
echo "⏱️  Expected duration: 20-40 minutes"
echo "📊 Training on all historical data (2024-present)"
echo ""

RETRAIN_START=$(date +%s)

# Run Python retrain script
python3 meta_controller/sac_full_retrain.py \
    --start-date "2024-11-01" \
    --end-date "$(date '+%Y-%m-%d')" \
    --output "$MODEL_DIR/sac_prod_latest.pth" \
    --versioned-backup "$MODEL_DIR/sac_${TIMESTAMP}.pth"

RETRAIN_EXIT_CODE=$?
RETRAIN_END=$(date +%s)
RETRAIN_DURATION=$((RETRAIN_END - RETRAIN_START))

echo ""

if [ $RETRAIN_EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✅ Full retrain completed successfully${NC}"
    echo "   Duration: $((RETRAIN_DURATION / 60)) minutes $((RETRAIN_DURATION % 60)) seconds"
else
    echo -e "${RED}❌ RETRAIN FAILED with exit code $RETRAIN_EXIT_CODE${NC}"
    
    # Send critical alert
    python3 -c "
from monitoring.alerts import TelegramAlerts
alerts = TelegramAlerts()
alerts.send_critical(
    '🚨 SAC WEEKLY RETRAIN FAILED\n\n'
    'Exit code: $RETRAIN_EXIT_CODE\n'
    'Day: $DAY_OF_WEEK\n'
    'Time: $(date)\n\n'
    'Check logs immediately!'
)
"
    exit 1
fi

echo ""

################################################################################
# STEP 3: Verify new model
################################################################################
echo "================================================================================"
echo "STEP 3: VERIFY NEW MODEL"
echo "================================================================================"

if [ -f "$MODEL_DIR/sac_prod_latest.pth" ]; then
    MODEL_SIZE=$(stat -f%z "$MODEL_DIR/sac_prod_latest.pth" 2>/dev/null || stat -c%s "$MODEL_DIR/sac_prod_latest.pth")
    echo -e "${GREEN}✅ New model saved: sac_prod_latest.pth${NC}"
    echo "   Size: $((MODEL_SIZE / 1024)) KB"
else
    echo -e "${RED}❌ ERROR: New model not found!${NC}"
    exit 1
fi

if [ -f "$MODEL_DIR/sac_${TIMESTAMP}.pth" ]; then
    echo -e "${GREEN}✅ Versioned backup: sac_${TIMESTAMP}.pth${NC}"
else
    echo -e "${YELLOW}⚠️  WARNING: Versioned backup not found${NC}"
fi

echo ""

################################################################################
# STEP 4: Quick validation
################################################################################
echo "================================================================================"
echo "STEP 4: QUICK VALIDATION"
echo "================================================================================"

python3 -c "
import sys
sys.path.insert(0, '$PROJECT_ROOT')
from meta_controller.sac_agent import SACAgent
import torch

try:
    # Load new model
    agent = SACAgent(state_dim=35, action_dim=9)
    agent.load('$MODEL_DIR/sac_prod_latest.pth')
    
    # Quick sanity check
    dummy_state = torch.randn(1, 35)
    action = agent.select_action(dummy_state, deterministic=True)
    
    print('✅ Model loads correctly')
    print(f'   Action output shape: {action.shape}')
    print(f'   Action range: [{action.min():.3f}, {action.max():.3f}]')
    
except Exception as e:
    print(f'❌ Validation failed: {e}')
    sys.exit(1)
"

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ MODEL VALIDATION FAILED${NC}"
    echo "   Restoring backup..."
    
    if [ -f "$BACKUP_DIR/sac_${TIMESTAMP}_pre_retrain.pth" ]; then
        cp "$BACKUP_DIR/sac_${TIMESTAMP}_pre_retrain.pth" "$MODEL_DIR/sac_prod_latest.pth"
        echo -e "${GREEN}✅ Backup restored${NC}"
    fi
    
    exit 1
fi

echo ""

################################################################################
# STEP 5: Cleanup old backups (keep last 8 weeks)
################################################################################
echo "================================================================================"
echo "STEP 5: CLEANUP OLD BACKUPS"
echo "================================================================================"

BACKUP_COUNT=$(ls -1 "$BACKUP_DIR"/sac_*.pth 2>/dev/null | wc -l)
echo "Current backups: $BACKUP_COUNT"

if [ $BACKUP_COUNT -gt 8 ]; then
    echo "Removing old backups (keeping most recent 8)..."
    ls -1t "$BACKUP_DIR"/sac_*.pth | tail -n +9 | xargs rm -f
    NEW_COUNT=$(ls -1 "$BACKUP_DIR"/sac_*.pth 2>/dev/null | wc -l)
    echo -e "${GREEN}✅ Cleaned up. Now $NEW_COUNT backups${NC}"
else
    echo "No cleanup needed"
fi

echo ""

################################################################################
# STEP 6: Send Telegram notification
################################################################################
echo "================================================================================"
echo "STEP 6: SEND NOTIFICATION"
echo "================================================================================"

python3 -c "
from monitoring.alerts import TelegramAlerts
from datetime import datetime

alerts = TelegramAlerts()

report = f'''
✅ SAC FULLY RETRAINED - NEW VERSION

{'='*40}

📅 Date: $TIMESTAMP
📆 Day: $DAY_OF_WEEK  
⏱️  Duration: $((RETRAIN_DURATION / 60))m $((RETRAIN_DURATION % 60))s

📊 Model Details:
  • File: sac_prod_latest.pth
  • Backup: sac_${TIMESTAMP}.pth
  • Size: $((MODEL_SIZE / 1024)) KB

🎯 Next Full Retrain:
  • Friday 6 PM IST OR
  • Sunday 10 PM IST

{'='*40}

System ready for next trading session.
'''

alerts.send_success(report)
print('✅ Telegram notification sent')
"

echo ""

################################################################################
# COMPLETION
################################################################################
echo "================================================================================"
echo "SAC WEEKLY RETRAIN COMPLETE"
echo "================================================================================"
echo "Finished: $(date '+%Y-%m-%d %H:%M:%S IST')"
echo "Duration: $((RETRAIN_DURATION / 60)) minutes $((RETRAIN_DURATION % 60)) seconds"
echo ""
echo -e "${GREEN}✅ All steps completed successfully${NC}"
echo ""
echo "📊 Summary:"
echo "   • Model: sac_prod_latest.pth (updated)"
echo "   • Backup: sac_${TIMESTAMP}.pth"
echo "   • Training data: 2024-present"
echo "   • Next retrain: Next Friday/Sunday"
echo ""
echo "================================================================================"

exit 0
