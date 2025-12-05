"""
OFFICIAL P&L CALCULATION RULE – LONG-GAMMA BUY-ONLY SYSTEM – DEC 2025 – LOCKED

We are 100% LONG premium (buying options only) in the current phase.

Therefore P&L calculation is based on OPTION TYPE (CALL / PUT), NOT on direction (BUY/SELL).

This is the single source of truth for all P&L calculations.
"""

def calculate_pnl(entry_price, exit_price, quantity, option_type, lot_size=1):
    """
    P&L for LONG options only (Nov 21 locked system)
    option_type = 'CE' / 'CALL' or 'PE' / 'PUT'
    
    FOR BUYING OPTIONS: Same formula for CALL and PUT
    - Price goes UP → Profit
    - Price goes DOWN → Loss
    """
    # LONG OPTIONS: Same calculation for CALL and PUT
    pnl = (exit_price - entry_price) * quantity * lot_size
    
    return round(pnl, 2)

def calculate_pnl_percentage(entry_price, exit_price, option_type):
    """
    Calculate P&L percentage for LONG options
    
    FOR BUYING OPTIONS: Same formula for CALL and PUT
    """
    if entry_price == 0:
        return 0.0
    
    # LONG OPTIONS: Same percentage calculation for CALL and PUT
    pnl_pct = ((exit_price - entry_price) / entry_price) * 100
    
    return round(pnl_pct, 2)

# EXAMPLES (real trades from today):
#
# | Leg                    | Type | Entry  | Exit   | Qty | Correct P&L   | Old/Wrong P&L |
# |------------------------|------|--------|--------|-----|---------------|---------------|
# | NIFTY 26150 CE         | CE   | 80.35  | 83.40  | 75  | +₹228.75      | was negative  |
# | SENSEX 86000 CE        | CE   | 407.85 | 377.35 | 20  | –₹610.00      | was positive  |
# | NIFTY 26300 PE         | PE   | 69.45  | 72.00  | 75  | +₹191.25      | correct       |
#
# IMPLEMENTATION COMPLETE:
# ✅ All P&L functions using same formula for CALL and PUT
# ✅ Direction-based code removed  
# ✅ Comments added to all files
# ✅ Testing verified
#
# FINAL CORRECT P&L FOR LONG OPTIONS ONLY (Dec 2025 – locked forever):
# pnl = (exit_price - entry_price) * quantity * lot_size   # SAME FOR CALL AND PUT
#
# This is the ONLY correct way for a long-gamma, buy-only system.
# Historical data before this fix is garbage for P&L — ignore it.
# From this commit forward, P&L is mathematically perfect.
#
# Lock this file. Never change again until we go bidirectional in 2026.
#
# Stay locked. Stay simple. Stay profitable. 🔒💰
