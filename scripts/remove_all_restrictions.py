"""
Remove All Trading Restrictions for Paper Trading
Enables full day trading, all week, unlimited trades, no risk limits
"""

import yaml
from pathlib import Path
from datetime import datetime

print("="*80)
print("REMOVING ALL TRADING RESTRICTIONS - UNRESTRICTED PAPER TRADING")
print("="*80)

config_path = Path('config/config.yaml')

with open(config_path, 'r') as f:
    config = yaml.safe_load(f)

print("\n📋 REMOVING ALL RESTRICTIONS:")
print("-" * 80)

# Backup current config
backup_path = f"config/config_backup_unrestricted_{datetime.now().strftime('%Y%m%d_%H%M%S')}.yaml"
with open(config_path, 'r') as f:
    with open(backup_path, 'w') as b:
        b.write(f.read())
print(f"  💾 Backup saved: {backup_path}")

# 1. Remove ALL filters from default strategy
if 'strategies' in config and 'default' in config['strategies']:
    if 'filters' in config['strategies']['default']:
        # Disable time window - TRADE ALL DAY
        if 'time_window' in config['strategies']['default']['filters']:
            config['strategies']['default']['filters']['time_window']['enabled'] = False
            print("  ✅ Disabled: Time window filter (NOW TRADES ALL DAY 24/7)")
        
        # Disable day of week filters - TRADE ALL DAYS
        if 'day_of_week' in config['strategies']['default']['filters']:
            config['strategies']['default']['filters']['day_of_week']['enabled'] = False
            config['strategies']['default']['filters']['day_of_week']['allowed_days'] = [0, 1, 2, 3, 4, 5, 6]  # All days
            config['strategies']['default']['filters']['day_of_week']['blocked_days'] = []  # No blocked days
            print("  ✅ Disabled: Day filter (NOW TRADES ALL WEEKDAYS INCLUDING THURSDAY)")
        
        # Remove preferred days
        if 'preferred_days' in config['strategies']['default']['filters']:
            del config['strategies']['default']['filters']['preferred_days']
            print("  ✅ Removed: Preferred days restriction")

# 2. Remove ALL risk management limits
if 'risk_management' not in config:
    config['risk_management'] = {}

config['risk_management'].update({
    'expiry_day_trading': True,  # ENABLE expiry day trading
    'daily_loss_limit_pct': 1.0,  # 100% - NO LIMIT
    'max_consecutive_losses': 999999,  # ESSENTIALLY UNLIMITED
    'per_trade_risk_pct': 1.0,  # 100% - NO LIMIT
    'max_portfolio_leverage': 10.0,  # Increased from 4x to 10x
    'cash_reserve_pct': 0.0,  # NO CASH RESERVE - use all capital
    'max_positions': 9999,  # UNLIMITED positions
    'max_trades_per_day': 9999,  # UNLIMITED trades per day
    'max_trades_per_hour': 9999,  # UNLIMITED trades per hour
    'reason': 'UNRESTRICTED PAPER TRADING - NO LIMITS FOR TESTING'
})

print("  ✅ Removed: Daily loss limit (was 2%, now 100% - no limit)")
print("  ✅ Removed: Consecutive loss limit (was 10, now unlimited)")
print("  ✅ Removed: Per-trade risk limit (was 0.5%, now 100% - no limit)")
print("  ✅ Removed: Cash reserve requirement (was 15%, now 0%)")
print("  ✅ Increased: Max leverage (4x → 10x)")
print("  ✅ Enabled: Expiry day trading (was disabled)")
print("  ✅ Removed: Max positions limit")
print("  ✅ Removed: Max trades per day limit")
print("  ✅ Removed: Max trades per hour limit")

# 3. Update SAC meta-controller to be more aggressive
if 'sac_meta_controller' in config:
    config['sac_meta_controller']['risk_multiplier'] = 2.0  # Double the aggression
    config['sac_meta_controller']['max_allocation_per_group'] = 1.0  # Can allocate 100% to one group
    print("  ✅ Increased: SAC risk multiplier (1.0 → 2.0)")
    print("  ✅ Increased: SAC max allocation per group (35% → 100%)")

# Save updated config
with open(config_path, 'w') as f:
    yaml.dump(config, f, default_flow_style=False, sort_keys=False)

print("\n" + "="*80)
print("✅ ALL RESTRICTIONS REMOVED!")
print("="*80)

print("\n📊 NEW CONFIGURATION:")
print("  • Trading Hours: ALL DAY (24/7 if data available)")
print("  • Trading Days: ALL DAYS (Mon-Sun, including Thursday expiry)")
print("  • Daily Loss Limit: NONE (100%)")
print("  • Consecutive Loss Limit: NONE (unlimited)")
print("  • Per-Trade Risk: NONE (100%)")
print("  • Max Positions: UNLIMITED")
print("  • Max Trades/Day: UNLIMITED")
print("  • Max Leverage: 10x")
print("  • Cash Reserve: 0%")
print("  • Expiry Day Trading: ENABLED")

print("\n⚠️  WARNING: This is UNRESTRICTED mode for testing only!")
print("   Use only for paper trading. Re-enable limits before live trading.")

print("\n🚀 NEXT STEPS:")
print("  1. Restart paper trading: kill current process")
print("  2. Start unrestricted: python3 start_sac_paper_trading.py --capital 5000000")
print("  3. Monitor: ./monitor_sac_system.sh")

print("\n💾 Config saved: config/config.yaml")
print(f"💾 Backup saved: {backup_path}")
print("="*80)
