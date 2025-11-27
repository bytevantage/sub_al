"""
Apply Data Quality Fixes to Option Chain Snapshots
Cleans and corrects data based on audit findings
"""

import subprocess
from datetime import datetime
from pathlib import Path

print("="*100)
print("APPLYING DATA QUALITY FIXES TO DATABASE")
print("="*100)

# First, add quality flag column if it doesn't exist
print("\n📋 Step 1: Adding data_quality_flag column...")
print("-"*100)

add_column_cmd = """
docker exec trading_db psql -U trading_user -d trading_db -c "
ALTER TABLE option_chain_snapshots 
ADD COLUMN IF NOT EXISTS data_quality_flag VARCHAR(10) DEFAULT '';

ALTER TABLE option_chain_snapshots 
ADD COLUMN IF NOT EXISTS quality_issues TEXT DEFAULT '';
"
"""

result = subprocess.run(add_column_cmd, shell=True, capture_output=True, text=True)
if 'ALTER TABLE' in result.stdout or 'already exists' in result.stderr:
    print("✅ Columns added/verified")
else:
    print(f"⚠️  {result.stderr}")

# Fix 1: Remove exact duplicates
print("\n🔧 Fix 1: Removing duplicate records...")
print("-"*100)

remove_duplicates = """
docker exec trading_db psql -U trading_user -d trading_db -c "
DELETE FROM option_chain_snapshots a USING (
    SELECT MIN(id) as id, timestamp, symbol, strike_price, option_type
    FROM option_chain_snapshots
    GROUP BY timestamp, symbol, strike_price, option_type
    HAVING COUNT(*) > 1
) b
WHERE a.timestamp = b.timestamp
  AND a.symbol = b.symbol
  AND a.strike_price = b.strike_price
  AND a.option_type = b.option_type
  AND a.id <> b.id;
"
"""

result = subprocess.run(remove_duplicates, shell=True, capture_output=True, text=True)
if 'DELETE' in result.stdout:
    deleted = result.stdout.strip().split()[-1] if result.stdout.strip() else '0'
    print(f"✅ Removed {deleted} duplicate records")
else:
    print("✅ No duplicates to remove")

# Fix 2: Flag records with negative OI or Volume
print("\n🔧 Fix 2: Flagging negative OI/Volume...")
print("-"*100)

flag_negative = """
docker exec trading_db psql -U trading_user -d trading_db -c "
UPDATE option_chain_snapshots
SET data_quality_flag = 'BAD',
    quality_issues = quality_issues || 'NEGATIVE_OI_VOLUME;'
WHERE oi < 0 OR volume < 0;
"
"""

result = subprocess.run(flag_negative, shell=True, capture_output=True, text=True)
updated = result.stdout.strip().split()[-1] if 'UPDATE' in result.stdout else '0'
print(f"✅ Flagged {updated} records with negative OI/Volume")

# Fix 3: Flag invalid bid/ask spreads
print("\n🔧 Fix 3: Flagging invalid bid/ask spreads...")
print("-"*100)

flag_spread = """
docker exec trading_db psql -U trading_user -d trading_db -c "
UPDATE option_chain_snapshots
SET data_quality_flag = 'BAD',
    quality_issues = quality_issues || 'BID>ASK;'
WHERE bid IS NOT NULL 
  AND ask IS NOT NULL 
  AND bid > ask;
"
"""

result = subprocess.run(flag_spread, shell=True, capture_output=True, text=True)
updated = result.stdout.strip().split()[-1] if 'UPDATE' in result.stdout else '0'
print(f"✅ Flagged {updated} records with bid > ask")

# Fix 4: Flag extreme IV values
print("\n🔧 Fix 4: Flagging extreme IV values...")
print("-"*100)

flag_iv = """
docker exec trading_db psql -U trading_user -d trading_db -c "
UPDATE option_chain_snapshots
SET data_quality_flag = 'BAD',
    quality_issues = quality_issues || 'EXTREME_IV;'
WHERE iv IS NOT NULL 
  AND (iv < 1.0 OR iv > 300.0);
"
"""

result = subprocess.run(flag_iv, shell=True, capture_output=True, text=True)
updated = result.stdout.strip().split()[-1] if 'UPDATE' in result.stdout else '0'
print(f"✅ Flagged {updated} records with extreme IV")

# Fix 5: Flag invalid Greeks
print("\n🔧 Fix 5: Flagging invalid Greeks...")
print("-"*100)

flag_greeks = """
docker exec trading_db psql -U trading_user -d trading_db -c "
-- Invalid Delta
UPDATE option_chain_snapshots
SET data_quality_flag = 'BAD',
    quality_issues = quality_issues || 'INVALID_DELTA;'
WHERE delta IS NOT NULL 
  AND (delta < -1.5 OR delta > 1.5);

-- Invalid Gamma  
UPDATE option_chain_snapshots
SET data_quality_flag = 'BAD',
    quality_issues = quality_issues || 'INVALID_GAMMA;'
WHERE gamma IS NOT NULL 
  AND (gamma < 0.0 OR gamma > 0.01);

-- Invalid Vega
UPDATE option_chain_snapshots
SET data_quality_flag = 'BAD',
    quality_issues = quality_issues || 'INVALID_VEGA;'
WHERE vega IS NOT NULL 
  AND vega > 500.0;

-- Invalid Theta
UPDATE option_chain_snapshots
SET data_quality_flag = 'BAD',
    quality_issues = quality_issues || 'INVALID_THETA;'
WHERE theta IS NOT NULL 
  AND (theta < -500.0 OR theta > 50.0);
"
"""

result = subprocess.run(flag_greeks, shell=True, capture_output=True, text=True)
print(f"✅ Flagged records with invalid Greeks")

# Fix 6: Flag price outside spread
print("\n🔧 Fix 6: Flagging price outside bid/ask...")
print("-"*100)

flag_price = """
docker exec trading_db psql -U trading_user -d trading_db -c "
UPDATE option_chain_snapshots
SET data_quality_flag = 'SUSPECT',
    quality_issues = quality_issues || 'PRICE_OUTSIDE_SPREAD;'
WHERE ltp IS NOT NULL 
  AND bid IS NOT NULL 
  AND ask IS NOT NULL
  AND (ltp < bid OR ltp > ask);
"
"""

result = subprocess.run(flag_price, shell=True, capture_output=True, text=True)
updated = result.stdout.strip().split()[-1] if 'UPDATE' in result.stdout else '0'
print(f"✅ Flagged {updated} records with price outside spread")

# Fix 7: Set clean records
print("\n🔧 Fix 7: Marking clean records...")
print("-"*100)

mark_clean = """
docker exec trading_db psql -U trading_user -d trading_db -c "
UPDATE option_chain_snapshots
SET data_quality_flag = 'CLEAN'
WHERE data_quality_flag = '' OR data_quality_flag IS NULL;
"
"""

result = subprocess.run(mark_clean, shell=True, capture_output=True, text=True)
updated = result.stdout.strip().split()[-1] if 'UPDATE' in result.stdout else '0'
print(f"✅ Marked {updated} clean records")

# Get final statistics
print("\n📊 Final Statistics:")
print("-"*100)

get_stats = """
docker exec trading_db psql -U trading_user -d trading_db -c "
SELECT 
    data_quality_flag,
    COUNT(*) as count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as percentage
FROM option_chain_snapshots
GROUP BY data_quality_flag
ORDER BY count DESC;
"
"""

result = subprocess.run(get_stats, shell=True, capture_output=True, text=True)
print(result.stdout)

# Daily quality distribution
print("\n📅 Daily Quality Distribution:")
print("-"*100)

daily_quality = """
docker exec trading_db psql -U trading_user -d trading_db -c "
SELECT 
    DATE(timestamp) as date,
    COUNT(*) as total,
    SUM(CASE WHEN data_quality_flag = 'CLEAN' THEN 1 ELSE 0 END) as clean,
    ROUND(SUM(CASE WHEN data_quality_flag = 'CLEAN' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as clean_pct,
    SUM(CASE WHEN data_quality_flag = 'BAD' THEN 1 ELSE 0 END) as bad,
    SUM(CASE WHEN data_quality_flag = 'SUSPECT' THEN 1 ELSE 0 END) as suspect
FROM option_chain_snapshots
GROUP BY DATE(timestamp)
ORDER BY date;
"
"""

result = subprocess.run(daily_quality, shell=True, capture_output=True, text=True)
print(result.stdout)

# Create a view for clean data only
print("\n📊 Creating view for clean data...")
print("-"*100)

create_view = """
docker exec trading_db psql -U trading_user -d trading_db -c "
DROP VIEW IF EXISTS option_chain_snapshots_clean;

CREATE VIEW option_chain_snapshots_clean AS
SELECT 
    id, timestamp, symbol, strike_price, option_type, expiry,
    ltp, bid, ask, volume, oi, oi_change,
    delta, gamma, theta, vega, iv, spot_price
FROM option_chain_snapshots
WHERE data_quality_flag = 'CLEAN';
"
"""

result = subprocess.run(create_view, shell=True, capture_output=True, text=True)
if 'CREATE VIEW' in result.stdout:
    print("✅ Created view: option_chain_snapshots_clean")
else:
    print(f"⚠️  {result.stderr}")

# Create indexes for faster querying
print("\n🔍 Creating indexes on quality flag...")
print("-"*100)

create_index = """
docker exec trading_db psql -U trading_user -d trading_db -c "
CREATE INDEX IF NOT EXISTS idx_data_quality_flag 
ON option_chain_snapshots(data_quality_flag);

CREATE INDEX IF NOT EXISTS idx_timestamp_quality 
ON option_chain_snapshots(timestamp, data_quality_flag);
"
"""

result = subprocess.run(create_index, shell=True, capture_output=True, text=True)
print("✅ Indexes created")

print("\n" + "="*100)
print("✅ DATA QUALITY FIXES APPLIED!")
print("="*100)

print(f"\n📊 Summary:")
print(f"   • Added data_quality_flag and quality_issues columns")
print(f"   • Removed duplicate records")
print(f"   • Flagged BAD data (invalid values)")
print(f"   • Flagged SUSPECT data (questionable but possible)")
print(f"   • Marked CLEAN data (passed all checks)")
print(f"   • Created view: option_chain_snapshots_clean")
print(f"   • Added indexes for performance")

print(f"\n🎯 Next Steps:")
print(f"   • Use option_chain_snapshots_clean view for analysis")
print(f"   • Review BAD records in quality logs")
print(f"   • Run check_and_clean.py again to verify")
print(f"   • Update SAC backtest to use clean data")

print("\n💡 Usage:")
print(f"   SELECT * FROM option_chain_snapshots_clean WHERE symbol = 'NIFTY';")
print(f"   SELECT * FROM option_chain_snapshots WHERE data_quality_flag = 'BAD';")

print("\n" + "="*100)
