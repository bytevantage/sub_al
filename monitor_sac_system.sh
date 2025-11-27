#!/bin/bash
# SAC System Monitoring Dashboard
# Run this to get real-time status

clear
echo "================================================================================"
echo "SAC META-CONTROLLER - LIVE MONITORING DASHBOARD"
echo "================================================================================"
echo ""

# Check if paper trading is running
echo "📊 SYSTEM STATUS:"
echo "--------------------------------------------------------------------------------"
if ps aux | grep -q "[s]tart_sac_paper_trading.py"; then
    PID=$(ps aux | grep "[s]tart_sac_paper_trading.py" | awk '{print $2}')
    UPTIME=$(ps -p $PID -o etime= | xargs)
    echo "✅ Paper Trading: RUNNING (PID: $PID, Uptime: $UPTIME)"
else
    echo "❌ Paper Trading: STOPPED"
fi

# Check Docker services
echo ""
echo "🐳 DOCKER SERVICES:"
docker ps --format "table {{.Names}}\t{{.Status}}" | grep trading

echo ""
echo "📈 ACTIVE STRATEGIES (from config):"
echo "--------------------------------------------------------------------------------"
python3 -c "
import yaml
with open('config/config.yaml', 'r') as f:
    config = yaml.safe_load(f)
    strategies = config.get('strategies', {})
    active = [(name, cfg) for name, cfg in strategies.items() if cfg.get('enabled')]
    print(f'Total Active: {len(active)}')
    for name, cfg in active:
        alloc = cfg.get('allocation', 0)
        print(f'  ✅ {name}: {alloc*100:.0f}% allocation')
" 2>/dev/null || echo "  (Config parsing error)"

echo ""
echo "🧠 SAC META-CONTROLLER:"
echo "--------------------------------------------------------------------------------"
python3 -c "
import yaml
with open('config/config.yaml', 'r') as f:
    config = yaml.safe_load(f)
    sac = config.get('sac_meta_controller', {})
    enabled = sac.get('enabled', False)
    model = sac.get('model_path', 'N/A')
    interval = sac.get('update_interval_seconds', 0)
    print(f'Status: {\"✅ ENABLED\" if enabled else \"❌ DISABLED\"}')
    print(f'Model: {model}')
    print(f'Update Interval: {interval}s ({interval//60} minutes)')
" 2>/dev/null || echo "  (Config parsing error)"

echo ""
echo "🛡️  RISK CONTROLS:"
echo "--------------------------------------------------------------------------------"
python3 -c "
import yaml
with open('config/config.yaml', 'r') as f:
    config = yaml.safe_load(f)
    risk = config.get('risk_management', {})
    print(f'Daily Loss Limit: {risk.get(\"daily_loss_limit_pct\", 0)*100:.1f}%')
    print(f'Max Consecutive Losses: {risk.get(\"max_consecutive_losses\", 0)}')
    print(f'Max Leverage: {risk.get(\"max_portfolio_leverage\", 0):.1f}x')
    print(f'Cash Reserve: {risk.get(\"cash_reserve_pct\", 0)*100:.0f}%')
    print(f'Expiry Day Trading: {\"❌ DISABLED\" if not risk.get(\"expiry_day_trading\") else \"✅ ENABLED\"}')
" 2>/dev/null || echo "  (Config parsing error)"

echo ""
echo "📊 RECENT PERFORMANCE (Last 3 days from database):"
echo "--------------------------------------------------------------------------------"
docker exec trading_db psql -U trading_user -d trading_db -t -c "
SELECT 
    COUNT(*) as trades,
    SUM(CASE WHEN net_pnl > 0 THEN 1 ELSE 0 END) as wins,
    ROUND(AVG(CASE WHEN net_pnl > 0 THEN 1.0 ELSE 0.0 END) * 100, 1) as win_rate,
    ROUND(SUM(net_pnl), 2) as total_pnl
FROM trades 
WHERE status = 'CLOSED'
AND entry_time >= NOW() - INTERVAL '3 days';
" 2>/dev/null | awk '{print "  Trades: "$1" | Wins: "$2" | Win Rate: "$3"% | P&L: ₹"$4}'

echo ""
echo "⏰ TIME FILTERS:"
echo "--------------------------------------------------------------------------------"
python3 -c "
import yaml
with open('config/config.yaml', 'r') as f:
    config = yaml.safe_load(f)
    default = config.get('strategies', {}).get('default', {})
    filters = default.get('filters', {})
    tw = filters.get('time_window', {})
    if tw.get('enabled'):
        print(f'  ✅ Time Window: {tw.get(\"start_hour\")}:{tw.get(\"start_minute\"):02d}-{tw.get(\"end_hour\")}:{tw.get(\"end_minute\"):02d}')
    else:
        print('  ❌ Time Window: DISABLED')
    
    dow = filters.get('day_of_week', {})
    if dow.get('enabled'):
        days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']
        allowed = [days[i] for i in dow.get('allowed_days', [])]
        blocked = [days[i] for i in dow.get('blocked_days', [])]
        print(f'  ✅ Allowed Days: {\" \".join(allowed)}')
        if blocked:
            print(f'  ❌ Blocked Days: {\" \".join(blocked)}')
    else:
        print('  ❌ Day Filter: DISABLED')
" 2>/dev/null || echo "  (Config parsing error)"

echo ""
echo "================================================================================"
echo "Last Updated: $(date '+%Y-%m-%d %H:%M:%S')"
echo "================================================================================"
echo ""
echo "Commands:"
echo "  • View logs: tail -f data/logs/trading_system.log"
echo "  • Run analysis: python3 quick_strategy_analysis.py"
echo "  • Stop trading: kill -SIGINT \$(ps aux | grep '[s]tart_sac_paper' | awk '{print \$2}')"
echo ""
