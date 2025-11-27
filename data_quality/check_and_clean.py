"""
Data Quality Audit and Cleaning for Option Chain Snapshots
Identifies and fixes common data quality issues in Indian broker data
"""

import pandas as pd
import numpy as np
from datetime import datetime, time, timedelta
import subprocess
from pathlib import Path
from collections import defaultdict

print("="*100)
print("OPTION CHAIN DATA QUALITY AUDIT & CLEANING")
print("="*100)

# Configuration
MARKET_OPEN = time(9, 15)
MARKET_CLOSE = time(15, 30)
BAR_INTERVAL_MINUTES = 5

# Quality thresholds (IV is stored as percentage, not decimal)
THRESHOLDS = {
    'iv_min': 1.0,  # 1% (stored as 1.0, not 0.01)
    'iv_max': 300.0,   # 300% (stored as 300.0, not 3.0)
    'delta_min': -1.5,
    'delta_max': 1.5,
    'gamma_min': 0.0,
    'gamma_max': 0.01,  # Adjusted for actual data scale
    'vega_min': 0.0,
    'vega_max': 500.0,
    'theta_min': -500.0,
    'theta_max': 50.0,
    'oi_min': 0,
    'volume_min': 0,
    'price_min': 0.05,  # Min option price
}

# Issue tracking
issues = defaultdict(list)
stats = {
    'total_records': 0,
    'missing_bars': 0,
    'duplicate_timestamps': 0,
    'negative_oi_volume': 0,
    'bid_ask_invalid': 0,
    'extreme_iv': 0,
    'invalid_greeks': 0,
    'price_outside_spread': 0,
    'records_flagged': 0,
    'records_fixed': 0
}

print("\n📊 Step 1: Exporting data from database...")
print("-"*100)

# Export all data
export_cmd = """
docker exec trading_db psql -U trading_user -d trading_db -t -A -F"," -c "
SELECT 
    id,
    timestamp,
    symbol,
    strike_price,
    option_type,
    expiry,
    ltp,
    bid,
    ask,
    volume,
    oi,
    oi_change,
    delta,
    gamma,
    theta,
    vega,
    iv,
    spot_price
FROM option_chain_snapshots
ORDER BY timestamp, symbol, strike_price, option_type;
" > /tmp/option_data_full.csv
"""

result = subprocess.run(export_cmd, shell=True, capture_output=True, text=True)
if result.returncode != 0:
    print(f"❌ Export failed: {result.stderr}")
    exit(1)

print("✅ Data exported to /tmp/option_data_full.csv")

print("\n📊 Step 2: Loading and analyzing data...")
print("-"*100)

# Load data
df = pd.read_csv('/tmp/option_data_full.csv', names=[
    'id', 'timestamp', 'symbol', 'strike', 'option_type', 'expiry',
    'ltp', 'bid', 'ask', 'volume', 'oi', 'oi_change',
    'delta', 'gamma', 'theta', 'vega', 'iv', 'spot'
])

df['timestamp'] = pd.to_datetime(df['timestamp'])
df['expiry'] = pd.to_datetime(df['expiry'], format='mixed', errors='coerce')

stats['total_records'] = len(df)
print(f"✅ Loaded {len(df):,} records")
print(f"   Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
print(f"   Symbols: {df['symbol'].unique()}")

# Add quality flag column
df['data_quality_flag'] = ''
df['quality_issues'] = ''

print("\n📊 Step 3: Running quality checks...")
print("-"*100)

# ============================================================================
# CHECK 1: Missing 5-minute bars during market hours
# ============================================================================
print("\n🔍 CHECK 1: Missing 5-minute bars")
print("-"*50)

def check_missing_bars(df):
    """Identify missing 5-minute bars during market hours"""
    missing_bars = []
    
    # Group by date and symbol
    for (date, symbol), group in df.groupby([df['timestamp'].dt.date, 'symbol']):
        # Get all timestamps for this date
        timestamps = sorted(group['timestamp'].unique())
        
        # Expected timestamps during market hours
        expected = []
        start_dt = pd.Timestamp.combine(date, MARKET_OPEN)
        end_dt = pd.Timestamp.combine(date, MARKET_CLOSE)
        
        current = start_dt
        while current <= end_dt:
            expected.append(current)
            current += timedelta(minutes=BAR_INTERVAL_MINUTES)
        
        # Find missing
        timestamps_set = set(timestamps)
        for exp_ts in expected:
            if exp_ts not in timestamps_set:
                missing_bars.append({
                    'timestamp': exp_ts,
                    'symbol': symbol,
                    'date': date
                })
                issues['missing_bars'].append(f"{exp_ts} | {symbol}")
    
    stats['missing_bars'] = len(missing_bars)
    return missing_bars

missing_bars = check_missing_bars(df)
print(f"   Found {stats['missing_bars']:,} missing 5-minute bars")

# ============================================================================
# CHECK 2: Duplicate timestamps
# ============================================================================
print("\n🔍 CHECK 2: Duplicate timestamps")
print("-"*50)

duplicates = df[df.duplicated(subset=['timestamp', 'symbol', 'strike', 'option_type'], keep=False)]
stats['duplicate_timestamps'] = len(duplicates)

if len(duplicates) > 0:
    print(f"   ⚠️  Found {len(duplicates):,} duplicate records")
    for _, dup in duplicates.head(10).iterrows():
        issues['duplicates'].append(f"{dup['timestamp']} | {dup['symbol']} | {dup['strike']} {dup['option_type']}")
        df.loc[dup.name, 'quality_issues'] += 'DUPLICATE;'
else:
    print(f"   ✅ No duplicates found")

# ============================================================================
# CHECK 3: Zero or negative OI/Volume
# ============================================================================
print("\n🔍 CHECK 3: Zero or negative OI/Volume")
print("-"*50)

negative_oi = df[df['oi'] < THRESHOLDS['oi_min']]
negative_volume = df[df['volume'] < THRESHOLDS['volume_min']]

stats['negative_oi_volume'] = len(negative_oi) + len(negative_volume)
print(f"   Negative OI: {len(negative_oi):,}")
print(f"   Negative Volume: {len(negative_volume):,}")

for idx in negative_oi.index:
    issues['negative_oi'].append(f"{df.loc[idx, 'timestamp']} | {df.loc[idx, 'symbol']} | OI={df.loc[idx, 'oi']}")
    df.loc[idx, 'quality_issues'] += 'NEGATIVE_OI;'
    df.loc[idx, 'data_quality_flag'] = 'BAD'

for idx in negative_volume.index:
    issues['negative_volume'].append(f"{df.loc[idx, 'timestamp']} | {df.loc[idx, 'symbol']} | Volume={df.loc[idx, 'volume']}")
    df.loc[idx, 'quality_issues'] += 'NEGATIVE_VOLUME;'

# ============================================================================
# CHECK 4: Bid > Ask
# ============================================================================
print("\n🔍 CHECK 4: Bid > Ask spreads")
print("-"*50)

invalid_spread = df[(df['bid'].notna()) & (df['ask'].notna()) & (df['bid'] > df['ask'])]
stats['bid_ask_invalid'] = len(invalid_spread)
print(f"   Found {len(invalid_spread):,} invalid bid/ask spreads")

for idx in invalid_spread.index:
    issues['invalid_spread'].append(
        f"{df.loc[idx, 'timestamp']} | {df.loc[idx, 'symbol']} | "
        f"Bid={df.loc[idx, 'bid']:.2f} > Ask={df.loc[idx, 'ask']:.2f}"
    )
    df.loc[idx, 'quality_issues'] += 'BID>ASK;'
    df.loc[idx, 'data_quality_flag'] = 'BAD'

# ============================================================================
# CHECK 5: Last price outside bid/ask
# ============================================================================
print("\n🔍 CHECK 5: Last price outside bid/ask spread")
print("-"*50)

price_outside = df[
    (df['ltp'].notna()) & (df['bid'].notna()) & (df['ask'].notna()) &
    ((df['ltp'] < df['bid']) | (df['ltp'] > df['ask']))
]
stats['price_outside_spread'] = len(price_outside)
print(f"   Found {len(price_outside):,} prices outside bid/ask")

for idx in price_outside.head(100).index:  # Log first 100
    issues['price_outside'].append(
        f"{df.loc[idx, 'timestamp']} | {df.loc[idx, 'symbol']} | "
        f"LTP={df.loc[idx, 'ltp']:.2f} not in [{df.loc[idx, 'bid']:.2f}, {df.loc[idx, 'ask']:.2f}]"
    )
    df.loc[idx, 'quality_issues'] += 'PRICE_OUTSIDE_SPREAD;'
    df.loc[idx, 'data_quality_flag'] = 'SUSPECT'

# ============================================================================
# CHECK 6: Extreme IV values
# ============================================================================
print("\n🔍 CHECK 6: Extreme Implied Volatility")
print("-"*50)

extreme_iv_low = df[(df['iv'].notna()) & (df['iv'] < THRESHOLDS['iv_min'])]
extreme_iv_high = df[(df['iv'].notna()) & (df['iv'] > THRESHOLDS['iv_max'])]

stats['extreme_iv'] = len(extreme_iv_low) + len(extreme_iv_high)
print(f"   IV < {THRESHOLDS['iv_min']*100}%: {len(extreme_iv_low):,}")
print(f"   IV > {THRESHOLDS['iv_max']*100}%: {len(extreme_iv_high):,}")

for idx in extreme_iv_low.index:
    issues['extreme_iv_low'].append(f"{df.loc[idx, 'timestamp']} | {df.loc[idx, 'symbol']} | IV={df.loc[idx, 'iv']*100:.1f}%")
    df.loc[idx, 'quality_issues'] += 'EXTREME_IV_LOW;'
    df.loc[idx, 'data_quality_flag'] = 'BAD'

for idx in extreme_iv_high.index:
    issues['extreme_iv_high'].append(f"{df.loc[idx, 'timestamp']} | {df.loc[idx, 'symbol']} | IV={df.loc[idx, 'iv']*100:.1f}%")
    df.loc[idx, 'quality_issues'] += 'EXTREME_IV_HIGH;'
    df.loc[idx, 'data_quality_flag'] = 'BAD'

# ============================================================================
# CHECK 7: Invalid Greeks
# ============================================================================
print("\n🔍 CHECK 7: Invalid Greeks")
print("-"*50)

# Delta outside [-1.5, 1.5]
invalid_delta = df[
    (df['delta'].notna()) &
    ((df['delta'] < THRESHOLDS['delta_min']) | (df['delta'] > THRESHOLDS['delta_max']))
]

# Gamma outside reasonable range
invalid_gamma = df[
    (df['gamma'].notna()) &
    ((df['gamma'] < THRESHOLDS['gamma_min']) | (df['gamma'] > THRESHOLDS['gamma_max']))
]

# Vega > 500
invalid_vega = df[(df['vega'].notna()) & (df['vega'] > THRESHOLDS['vega_max'])]

# Theta outside reasonable range
invalid_theta = df[
    (df['theta'].notna()) &
    ((df['theta'] < THRESHOLDS['theta_min']) | (df['theta'] > THRESHOLDS['theta_max']))
]

stats['invalid_greeks'] = len(invalid_delta) + len(invalid_gamma) + len(invalid_vega) + len(invalid_theta)
print(f"   Invalid Delta: {len(invalid_delta):,}")
print(f"   Invalid Gamma: {len(invalid_gamma):,}")
print(f"   Invalid Vega: {len(invalid_vega):,}")
print(f"   Invalid Theta: {len(invalid_theta):,}")

for idx in invalid_delta.head(50).index:
    issues['invalid_delta'].append(f"{df.loc[idx, 'timestamp']} | {df.loc[idx, 'symbol']} | Delta={df.loc[idx, 'delta']:.3f}")
    df.loc[idx, 'quality_issues'] += 'INVALID_DELTA;'
    df.loc[idx, 'data_quality_flag'] = 'BAD'

for idx in invalid_gamma.head(50).index:
    issues['invalid_gamma'].append(f"{df.loc[idx, 'timestamp']} | {df.loc[idx, 'symbol']} | Gamma={df.loc[idx, 'gamma']:.3f}")
    df.loc[idx, 'quality_issues'] += 'INVALID_GAMMA;'
    df.loc[idx, 'data_quality_flag'] = 'BAD'

for idx in invalid_vega.head(50).index:
    issues['invalid_vega'].append(f"{df.loc[idx, 'timestamp']} | {df.loc[idx, 'symbol']} | Vega={df.loc[idx, 'vega']:.2f}")
    df.loc[idx, 'quality_issues'] += 'INVALID_VEGA;'
    df.loc[idx, 'data_quality_flag'] = 'BAD'

for idx in invalid_theta.head(50).index:
    issues['invalid_theta'].append(f"{df.loc[idx, 'timestamp']} | {df.loc[idx, 'symbol']} | Theta={df.loc[idx, 'theta']:.2f}")
    df.loc[idx, 'quality_issues'] += 'INVALID_THETA;'
    df.loc[idx, 'data_quality_flag'] = 'BAD'

# ============================================================================
# STATISTICS & REPORTING
# ============================================================================
print("\n" + "="*100)
print("AUDIT SUMMARY")
print("="*100)

stats['records_flagged'] = len(df[df['data_quality_flag'] != ''])

print(f"\n📊 Overall Statistics:")
print(f"   Total Records: {stats['total_records']:,}")
print(f"   Records Flagged: {stats['records_flagged']:,} ({stats['records_flagged']/stats['total_records']*100:.2f}%)")
print(f"   Clean Records: {stats['total_records'] - stats['records_flagged']:,} ({(stats['total_records'] - stats['records_flagged'])/stats['total_records']*100:.2f}%)")

print(f"\n🔍 Issues Found:")
print(f"   Missing 5-min bars: {stats['missing_bars']:,}")
print(f"   Duplicate timestamps: {stats['duplicate_timestamps']:,}")
print(f"   Negative OI/Volume: {stats['negative_oi_volume']:,}")
print(f"   Invalid bid/ask spreads: {stats['bid_ask_invalid']:,}")
print(f"   Price outside spread: {stats['price_outside_spread']:,}")
print(f"   Extreme IV: {stats['extreme_iv']:,}")
print(f"   Invalid Greeks: {stats['invalid_greeks']:,}")

# Daily quality report
print(f"\n📅 Daily Data Quality:")
print("-"*100)

daily_quality = df.groupby(df['timestamp'].dt.date).agg({
    'id': 'count',
    'data_quality_flag': lambda x: (x == '').sum()
}).reset_index()
daily_quality.columns = ['date', 'total_records', 'clean_records']
daily_quality['quality_pct'] = (daily_quality['clean_records'] / daily_quality['total_records'] * 100).round(2)
daily_quality = daily_quality.sort_values('date')

print(daily_quality.to_string(index=False))

# ============================================================================
# SAVE DETAILED LOGS
# ============================================================================
print(f"\n💾 Saving detailed issue logs...")
print("-"*100)

log_dir = Path('data_quality/logs')
log_dir.mkdir(parents=True, exist_ok=True)

timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')

# Save all issues
for issue_type, issue_list in issues.items():
    if issue_list:
        log_file = log_dir / f"{issue_type}_{timestamp_str}.log"
        with open(log_file, 'w') as f:
            f.write(f"# {issue_type.upper()} - {len(issue_list)} issues\n")
            f.write(f"# Generated: {datetime.now()}\n\n")
            for issue in issue_list:
                f.write(f"{issue}\n")
        print(f"   ✅ {log_file.name}: {len(issue_list):,} issues")

# Save daily quality report
quality_report_file = log_dir / f"daily_quality_report_{timestamp_str}.csv"
daily_quality.to_csv(quality_report_file, index=False)
print(f"   ✅ {quality_report_file.name}")

# Save summary
summary_file = log_dir / f"audit_summary_{timestamp_str}.txt"
with open(summary_file, 'w') as f:
    f.write("="*100 + "\n")
    f.write("OPTION CHAIN DATA QUALITY AUDIT SUMMARY\n")
    f.write("="*100 + "\n\n")
    f.write(f"Generated: {datetime.now()}\n")
    f.write(f"Date Range: {df['timestamp'].min()} to {df['timestamp'].max()}\n\n")
    
    f.write("STATISTICS:\n")
    f.write("-"*50 + "\n")
    for key, value in stats.items():
        f.write(f"{key}: {value:,}\n")
    
    f.write("\nDAILY QUALITY:\n")
    f.write("-"*50 + "\n")
    f.write(daily_quality.to_string(index=False))

print(f"   ✅ {summary_file.name}")

# ============================================================================
# EXPORT FLAGGED DATA FOR REVIEW
# ============================================================================
print(f"\n💾 Exporting flagged records...")
print("-"*100)

flagged_df = df[df['data_quality_flag'] != ''][['id', 'timestamp', 'symbol', 'strike', 'option_type', 
                                                   'data_quality_flag', 'quality_issues']]
flagged_file = log_dir / f"flagged_records_{timestamp_str}.csv"
flagged_df.to_csv(flagged_file, index=False)
print(f"   ✅ Exported {len(flagged_df):,} flagged records to {flagged_file.name}")

print("\n" + "="*100)
print("✅ AUDIT COMPLETE!")
print("="*100)
print(f"\n📁 All logs saved to: data_quality/logs/")
print(f"\n📊 Key Findings:")
print(f"   • Data Quality: {(stats['total_records'] - stats['records_flagged'])/stats['total_records']*100:.1f}% clean")
print(f"   • Main Issues: {max(stats.items(), key=lambda x: x[1] if x[0] != 'total_records' else 0)}")
print(f"   • Records to review: {stats['records_flagged']:,}")

print(f"\n🔧 Next Steps:")
print(f"   1. Review flagged records: data_quality/logs/flagged_records_{timestamp_str}.csv")
print(f"   2. Check detailed logs for each issue type")
print(f"   3. Run data_quality/apply_fixes.py to clean the database")
print(f"   4. Re-run this audit to verify fixes")

print("\n" + "="*100)
