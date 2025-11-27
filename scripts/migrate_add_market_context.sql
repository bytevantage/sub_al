-- Migration: Add market context fields to trades table
-- Date: November 20, 2025

-- Market Regime columns (at entry)
ALTER TABLE trades ADD COLUMN IF NOT EXISTS market_regime_entry VARCHAR(50);
ALTER TABLE trades ADD COLUMN IF NOT EXISTS regime_confidence FLOAT;

-- Time Context columns (at entry)
ALTER TABLE trades ADD COLUMN IF NOT EXISTS entry_hour INTEGER;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS entry_minute INTEGER;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS day_of_week VARCHAR(20);
ALTER TABLE trades ADD COLUMN IF NOT EXISTS is_expiry_day BOOLEAN;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS days_to_expiry INTEGER;

-- Market Regime columns (at exit)
ALTER TABLE trades ADD COLUMN IF NOT EXISTS market_regime_exit VARCHAR(50);

-- Time Context columns (at exit)
ALTER TABLE trades ADD COLUMN IF NOT EXISTS exit_hour INTEGER;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS exit_minute INTEGER;
