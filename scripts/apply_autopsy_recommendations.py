"""
Apply Strategy Autopsy Recommendations
Implements all recommended changes from the 2025 analysis
"""

import yaml
from pathlib import Path
from datetime import datetime

print("="*80)
print("APPLYING STRATEGY AUTOPSY RECOMMENDATIONS")
print("="*80)

# Load current config
config_path = Path('config/config.yaml')

if not config_path.exists():
    print(f"❌ Config file not found: {config_path}")
    exit(1)

with open(config_path, 'r') as f:
    config = yaml.safe_load(f)

print("\n📋 PHASE 1: KILL LOSING STRATEGIES")
print("-" * 80)

# Strategies to kill
kill_strategies = ['oi_change_patterns', 'pcr_analysis']

if 'strategies' not in config:
    config['strategies'] = {}

for strategy in kill_strategies:
    if strategy in config['strategies']:
        config['strategies'][strategy]['enabled'] = False
        config['strategies'][strategy]['allocation'] = 0.0
        print(f"  ❌ Killed: {strategy}")
    else:
        config['strategies'][strategy] = {
            'enabled': False,
            'allocation': 0.0,
            'reason': 'Killed due to severe underperformance (autopsy 2025)'
        }
        print(f"  ❌ Disabled: {strategy}")

print("\n📋 PHASE 2: OPTIMIZE DEFAULT STRATEGY")
print("-" * 80)

# Add filters to default strategy
if 'default' not in config['strategies']:
    config['strategies']['default'] = {}

config['strategies']['default'].update({
    'enabled': True,
    'allocation': 0.15,  # 15% - reduced from previous
    'filters': {
        'time_window': {
            'enabled': True,
            'start_hour': 9,
            'start_minute': 15,
            'end_hour': 10,
            'end_minute': 0,
            'reason': 'Only 09:15-10:00 window is profitable (+₹2,978 in backtest)'
        },
        'day_of_week': {
            'enabled': True,
            'allowed_days': [0, 1, 2],  # Mon, Tue, Wed only
            'blocked_days': [3],  # Thursday (expiry)
            'reason': 'Thursday expiry days lose ₹-133 per trade'
        },
        'preferred_days': [2],  # Wednesday
        'reason': 'Wednesday shows +₹2,414 P&L'
    }
})

print(f"  ⚠️  Optimized: default strategy")
print(f"     - Time filter: 09:15-10:00 ONLY")
print(f"     - Day filter: NO THURSDAYS")
print(f"     - Preferred: Wednesdays")
print(f"     - Allocation: 15%")

print("\n📋 PHASE 3: ACTIVATE HIGH-PERFORMANCE STRATEGIES")
print("-" * 80)

# Activate SAC meta-controller
config['sac_meta_controller'] = {
    'enabled': True,
    'model_path': 'models/sac_comprehensive_real.pth',
    'update_interval_seconds': 300,  # 5 minutes
    'max_allocation_per_group': 0.35,
    'min_allocation_per_group': 0.0,
    'risk_multiplier': 1.0,
    'reason': 'Demonstrated Sortino 14.62 in demo backtest'
}

print(f"  ✅ Activated: SAC Meta-Controller")
print(f"     - Decision interval: 5 minutes")
print(f"     - Max per group: 35%")

# Activate specific strategies
activate_strategies = {
    'quantum_edge': {
        'enabled': True,
        'allocation': 0.25,  # 25% - highest allocation
        'meta_group': 0,  # ML_PREDICTION
        'reason': 'Primary ML strategy with high confidence signals'
    },
    'gamma_scalping': {
        'enabled': True,
        'allocation': 0.15,
        'meta_group': 1,  # GREEKS_DELTA_NEUTRAL
        'reason': 'Greeks-based delta-neutral strategy'
    },
    'vwap_deviation': {
        'enabled': True,
        'allocation': 0.15,
        'meta_group': 3,  # MEAN_REVERSION
        'reason': 'Mean reversion on VWAP deviation'
    },
    'iv_rank_trading': {
        'enabled': True,
        'allocation': 0.15,
        'meta_group': 2,  # VOLATILITY_TRADING
        'reason': 'Volatility-based trading'
    }
}

for strategy, params in activate_strategies.items():
    config['strategies'][strategy] = params
    print(f"  ✅ Activated: {strategy} ({params['allocation']*100:.0f}% allocation)")

# Reserve cash
config['risk_management'] = config.get('risk_management', {})
config['risk_management'].update({
    'cash_reserve_pct': 0.15,  # 15% cash reserve
    'max_portfolio_leverage': 4.0,
    'daily_loss_limit_pct': 0.02,  # 2% daily loss limit
    'max_consecutive_losses': 10,  # Circuit breaker at 10 losses
    'per_trade_risk_pct': 0.005,  # 0.5% per trade
    'expiry_day_trading': False,  # Disable expiry day trading globally
    'reason': 'Enhanced risk controls based on autopsy findings'
})

print(f"  ✅ Updated: Risk Management")
print(f"     - Cash reserve: 15%")
print(f"     - Daily loss limit: 2%")
print(f"     - Max consecutive losses: 10")
print(f"     - Expiry day trading: DISABLED")

print("\n📋 PHASE 4: SAVE CONFIGURATION")
print("-" * 80)

# Backup old config
backup_path = f"config/config_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.yaml"
with open(config_path, 'r') as f:
    with open(backup_path, 'w') as b:
        b.write(f.read())

print(f"  💾 Backup saved: {backup_path}")

# Save new config
with open(config_path, 'w') as f:
    yaml.dump(config, f, default_flow_style=False, sort_keys=False)

print(f"  💾 Updated config: {config_path}")

print("\n" + "="*80)
print("✅ ALL RECOMMENDATIONS APPLIED SUCCESSFULLY!")
print("="*80)

print("\n📊 SUMMARY OF CHANGES:")
print(f"  ❌ Killed: 2 strategies (oi_change_patterns, pcr_analysis)")
print(f"  ⚠️  Optimized: 1 strategy (default with filters)")
print(f"  ✅ Activated: 4 new strategies + SAC meta-controller")
print(f"  🛡️  Enhanced: Risk management controls")

print("\n🚀 NEXT STEPS:")
print(f"  1. Restart trading system: docker-compose restart")
print(f"  2. Monitor dashboard for first 24 hours")
print(f"  3. Review P&L after 7 days")
print(f"  4. Run analysis again: python3 quick_strategy_analysis.py")

print("\n📈 EXPECTED IMPACT:")
print(f"  Current:  -₹1,766/day average")
print(f"  Target:   +₹200-300/day average")
print(f"  Swing:    +₹2,000/day improvement")

print("\n✓ Configuration updated and ready for deployment!")
print("="*80)
