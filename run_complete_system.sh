#!/bin/bash
# Master Control Script - Complete Trading System
# Manages all components: Data Quality, SAC, QuantumEdge v2, Paper Trading

clear
echo "================================================================================"
echo "COMPLETE ALGORITHMIC TRADING SYSTEM - MASTER CONTROL"
echo "================================================================================"
echo ""

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to check if service is running
check_service() {
    if ps aux | grep -q "[${1:0:1}]${1:1}"; then
        echo -e "${GREEN}✅ $2 is running${NC}"
        return 0
    else
        echo -e "${RED}❌ $2 is not running${NC}"
        return 1
    fi
}

# Function to display menu
show_menu() {
    echo ""
    echo "Choose an option:"
    echo ""
    echo "=== Data Quality ==="
    echo "  1) Check data quality status"
    echo "  2) Run full data audit"
    echo "  3) Apply quality fixes"
    echo ""
    echo "=== QuantumEdge v2 ==="
    echo "  4) Test feature extraction"
    echo "  5) Run demo training (10-15 min)"
    echo "  6) Run production training (2-4 hours)"
    echo "  7) Test inference (single prediction)"
    echo "  8) Start live prediction mode"
    echo "  9) Monitor ML performance"
    echo ""
    echo "=== SAC Meta-Controller ==="
    echo "  10) Check SAC status"
    echo "  11) Run SAC backtest"
    echo "  12) Monitor SAC system"
    echo ""
    echo "=== Strategy Management ==="
    echo "  13) Quick strategy analysis"
    echo "  14) View strategy autopsy report"
    echo "  15) Apply autopsy recommendations"
    echo ""
    echo "=== Paper Trading ==="
    echo "  16) Start unrestricted paper trading"
    echo "  17) Stop paper trading"
    echo "  18) View paper trading status"
    echo ""
    echo "=== System Status ==="
    echo "  19) Complete system health check"
    echo "  20) View all logs"
    echo ""
    echo "  0) Exit"
    echo ""
    echo -n "Enter choice: "
}

# Main loop
while true; do
    show_menu
    read choice
    
    case $choice in
        1)
            echo ""
            echo "=== Data Quality Status ==="
            ./data_quality/summary_report.sh
            echo ""
            read -p "Press Enter to continue..."
            ;;
        2)
            echo ""
            echo "=== Running Full Data Audit ==="
            python3 data_quality/check_and_clean.py
            echo ""
            read -p "Press Enter to continue..."
            ;;
        3)
            echo ""
            echo "=== Applying Quality Fixes ==="
            python3 data_quality/apply_fixes.py
            echo ""
            read -p "Press Enter to continue..."
            ;;
        4)
            echo ""
            echo "=== Testing Feature Extraction ==="
            cd training/quantum_edge_v2 && python3 test_features.py
            cd ../..
            echo ""
            read -p "Press Enter to continue..."
            ;;
        5)
            echo ""
            echo "=== Running Demo Training (10-15 minutes) ==="
            cd training/quantum_edge_v2 && python3 train_demo.py
            cd ../..
            echo ""
            read -p "Press Enter to continue..."
            ;;
        6)
            echo ""
            echo -e "${YELLOW}⚠️  WARNING: This will take 2-4 hours!${NC}"
            echo -n "Continue? (y/n): "
            read confirm
            if [ "$confirm" = "y" ]; then
                echo ""
                echo "=== Running Production Training ==="
                cd training/quantum_edge_v2 && python3 train.py
                cd ../..
            fi
            echo ""
            read -p "Press Enter to continue..."
            ;;
        7)
            echo ""
            echo "=== Testing Inference ==="
            cd training/quantum_edge_v2 && python3 inference.py --mode single --symbol NIFTY
            cd ../..
            echo ""
            read -p "Press Enter to continue..."
            ;;
        8)
            echo ""
            echo "=== Starting Live Prediction Mode ==="
            echo "Press Ctrl+C to stop"
            cd training/quantum_edge_v2 && python3 inference.py --mode live --symbol NIFTY --interval 300
            cd ../..
            ;;
        9)
            echo ""
            echo "=== Monitoring ML Performance ==="
            cd training/quantum_edge_v2 && python3 monitor_performance.py
            cd ../..
            echo ""
            read -p "Press Enter to continue..."
            ;;
        10)
            echo ""
            echo "=== SAC Meta-Controller Status ==="
            ./monitor_sac_system.sh
            echo ""
            read -p "Press Enter to continue..."
            ;;
        11)
            echo ""
            echo "=== Running SAC Backtest ==="
            python3 comprehensive_real_backtest.py
            echo ""
            read -p "Press Enter to continue..."
            ;;
        12)
            echo ""
            echo "=== SAC System Monitor ==="
            ./monitor_sac_system.sh
            echo ""
            read -p "Press Enter to continue..."
            ;;
        13)
            echo ""
            echo "=== Quick Strategy Analysis ==="
            python3 quick_strategy_analysis.py
            echo ""
            read -p "Press Enter to continue..."
            ;;
        14)
            echo ""
            echo "=== Strategy Autopsy Report ==="
            cat reports/STRATEGY_AUTOPSY_EXECUTIVE_SUMMARY.md | less
            ;;
        15)
            echo ""
            echo "=== Applying Autopsy Recommendations ==="
            python3 scripts/apply_autopsy_recommendations.py
            echo ""
            read -p "Press Enter to continue..."
            ;;
        16)
            echo ""
            echo "=== Starting Unrestricted Paper Trading ==="
            echo "Press Ctrl+C to stop"
            python3 start_sac_paper_trading.py --capital 5000000
            ;;
        17)
            echo ""
            echo "=== Stopping Paper Trading ==="
            PID=$(ps aux | grep '[s]tart_sac_paper_trading' | awk '{print $2}')
            if [ ! -z "$PID" ]; then
                kill -SIGINT $PID
                echo -e "${GREEN}✅ Paper trading stopped (PID: $PID)${NC}"
            else
                echo -e "${RED}❌ Paper trading not running${NC}"
            fi
            echo ""
            read -p "Press Enter to continue..."
            ;;
        18)
            echo ""
            echo "=== Paper Trading Status ==="
            check_service "start_sac_paper_trading" "Paper Trading"
            if ps aux | grep -q "[s]tart_sac_paper_trading"; then
                PID=$(ps aux | grep '[s]tart_sac_paper_trading' | awk '{print $2}')
                UPTIME=$(ps -p $PID -o etime= | xargs)
                echo "  PID: $PID"
                echo "  Uptime: $UPTIME"
            fi
            echo ""
            read -p "Press Enter to continue..."
            ;;
        19)
            echo ""
            echo "=== Complete System Health Check ==="
            echo ""
            echo "📊 Docker Services:"
            docker ps --format "table {{.Names}}\t{{.Status}}" | grep trading
            echo ""
            echo "📊 Python Services:"
            check_service "start_sac_paper_trading" "Paper Trading"
            check_service "inference.py" "QuantumEdge v2 Live Inference"
            echo ""
            echo "📊 Database:"
            docker exec trading_db psql -U trading_user -d trading_db -c "SELECT COUNT(*) as total, COUNT(*) FILTER (WHERE data_quality_flag='CLEAN') as clean FROM option_chain_snapshots;" 2>/dev/null
            echo ""
            echo "📊 Models:"
            if [ -f "models/quantum_edge_v2.pt" ]; then
                echo -e "${GREEN}✅ QuantumEdge v2 (production)${NC}"
            else
                echo -e "${YELLOW}⚠️  QuantumEdge v2 (not trained yet)${NC}"
            fi
            if [ -f "models/quantum_edge_v2_demo.pt" ]; then
                echo -e "${GREEN}✅ QuantumEdge v2 Demo${NC}"
            fi
            if [ -f "models/sac_comprehensive_real.pth" ]; then
                echo -e "${GREEN}✅ SAC Meta-Controller${NC}"
            fi
            echo ""
            read -p "Press Enter to continue..."
            ;;
        20)
            echo ""
            echo "=== All Logs ==="
            echo ""
            echo "Choose log:"
            echo "1) Trading System Log"
            echo "2) Data Quality Logs"
            echo "3) Recent Audit Summary"
            echo ""
            echo -n "Enter choice: "
            read log_choice
            
            case $log_choice in
                1)
                    tail -100 data/logs/trading_system.log 2>/dev/null || echo "Log file not found"
                    ;;
                2)
                    ls -lh data_quality/logs/
                    ;;
                3)
                    cat data_quality/logs/audit_summary_*.txt | tail -1
                    ;;
            esac
            echo ""
            read -p "Press Enter to continue..."
            ;;
        0)
            echo ""
            echo "Exiting..."
            exit 0
            ;;
        *)
            echo ""
            echo -e "${RED}Invalid choice. Please try again.${NC}"
            sleep 2
            ;;
    esac
    
    clear
    echo "================================================================================"
    echo "COMPLETE ALGORITHMIC TRADING SYSTEM - MASTER CONTROL"
    echo "================================================================================"
done
