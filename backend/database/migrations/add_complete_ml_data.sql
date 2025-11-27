-- Migration: Add complete ML training data columns to trades table
-- Date: 2025-11-19
-- Purpose: Capture Greeks at exit, OI/Volume/Bid/Ask at entry and exit for ML training

-- Add Greeks at exit
ALTER TABLE trades ADD COLUMN IF NOT EXISTS delta_exit FLOAT;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS gamma_exit FLOAT;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS theta_exit FLOAT;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS vega_exit FLOAT;

-- Add VIX and PCR at entry (if not already present)
ALTER TABLE trades ADD COLUMN IF NOT EXISTS vix_entry FLOAT;

-- Add PCR at exit
ALTER TABLE trades ADD COLUMN IF NOT EXISTS pcr_exit FLOAT;

-- Add option chain data at entry
ALTER TABLE trades ADD COLUMN IF NOT EXISTS oi_entry BIGINT;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS volume_entry BIGINT;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS bid_entry FLOAT;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS ask_entry FLOAT;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS spread_entry FLOAT;

-- Add option chain data at exit
ALTER TABLE trades ADD COLUMN IF NOT EXISTS oi_exit BIGINT;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS volume_exit BIGINT;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS bid_exit FLOAT;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS ask_exit FLOAT;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS spread_exit FLOAT;

-- Add indexes for common ML queries
CREATE INDEX IF NOT EXISTS idx_trades_delta_entry ON trades(delta_entry) WHERE delta_entry IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_trades_iv_entry ON trades(iv_entry) WHERE iv_entry IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_trades_oi_entry ON trades(oi_entry) WHERE oi_entry IS NOT NULL;

-- Add comment for documentation
COMMENT ON COLUMN trades.delta_exit IS 'Delta Greek at trade exit - measures option price sensitivity';
COMMENT ON COLUMN trades.gamma_exit IS 'Gamma Greek at trade exit - measures delta change rate';
COMMENT ON COLUMN trades.theta_exit IS 'Theta Greek at trade exit - time decay';
COMMENT ON COLUMN trades.vega_exit IS 'Vega Greek at trade exit - volatility sensitivity';
COMMENT ON COLUMN trades.oi_entry IS 'Open Interest at entry - market participation';
COMMENT ON COLUMN trades.oi_exit IS 'Open Interest at exit - market participation change';
COMMENT ON COLUMN trades.volume_entry IS 'Trading volume at entry - liquidity indicator';
COMMENT ON COLUMN trades.volume_exit IS 'Trading volume at exit - liquidity indicator';
COMMENT ON COLUMN trades.spread_entry IS 'Bid-Ask spread % at entry - transaction cost';
COMMENT ON COLUMN trades.spread_exit IS 'Bid-Ask spread % at exit - transaction cost';

-- Verify columns were added
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'trades' 
AND column_name IN (
    'delta_exit', 'gamma_exit', 'theta_exit', 'vega_exit',
    'oi_entry', 'oi_exit', 'volume_entry', 'volume_exit',
    'bid_entry', 'bid_exit', 'ask_entry', 'ask_exit',
    'spread_entry', 'spread_exit', 'pcr_exit', 'vix_entry'
)
ORDER BY column_name;
