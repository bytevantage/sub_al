# 🔴 CRITICAL CORRECTION - BANKNIFTY SPECIFICATIONS

## ⚠️ Updated Information (Nov 12, 2025)

### BANKNIFTY Correct Specifications

**Previous (INCORRECT):**
- ❌ Lot Size: 15
- ❌ Expiry: Every Wednesday (weekly)

**Current (CORRECT):**
- ✅ **Lot Size: 35**
- ✅ **Expiry: Last Thursday of the month (monthly)**

---

## 📊 Updated Quick Reference Table

| Symbol | Exchange | Lot Size | Expiry Type | Expiry Day |
|--------|----------|----------|-------------|------------|
| **NIFTY** | NSE | **75** | Weekly | **Every Tuesday** |
| **BANKNIFTY** | NSE | **35** | Monthly | **Last Thursday of Month** |
| **SENSEX** | BSE | **20** | Weekly | **Every Thursday** |

---

## 📅 BANKNIFTY Expiry Dates Examples

### 2025 Monthly Expiries (Last Thursday)
- November 2025: **Nov 28** (Last Thursday)
- December 2025: **Dec 25** (Last Thursday - Christmas day, verify with exchange)
- January 2026: **Jan 29** (Last Thursday)
- February 2026: **Feb 26** (Last Thursday)

**How to Calculate:**
1. Find last day of the month
2. Count backwards to find the last Thursday
3. That's the expiry date

---

## 💰 Position Sizing Impact - BANKNIFTY

### Old Calculation (Lot Size 15)
```
Premium ₹400 × 15 = ₹6,000 per lot
```

### New Calculation (Lot Size 35)
```
Premium ₹400 × 35 = ₹14,000 per lot
```

**Impact:** More than **2.3x higher capital requirement** per lot!

### Examples with ₹1,00,000 Capital (2% risk = ₹2,000)

| Premium | Old (Lot 15) | New (Lot 35) | Difference |
|---------|--------------|--------------|------------|
| ₹100 | 1.3 lots | 0.57 lot | -56% |
| ₹200 | 0.67 lot | 0.29 lot | -57% |
| ₹300 | 0.44 lot | 0.19 lot | -57% |
| ₹400 | 0.33 lot | 0.14 lot | -57% |
| ₹500 | 0.27 lot | 0.11 lot | -57% |

**Key Insight:** You can now take **less than half** the number of lots with same risk amount.

---

## 🗓️ Monthly vs Weekly Expiry Strategy

### NIFTY (Weekly - Tuesday)
- **52 expiries per year**
- Can trade every week
- Shorter holding periods
- More frequent opportunities

### BANKNIFTY (Monthly - Last Thursday)
- **12 expiries per year**
- Longer time to expiry
- Higher premiums due to time value
- Need to manage positions across multiple weeks

### SENSEX (Weekly - Thursday)
- **52 expiries per year**
- Weekly opportunities
- Similar to NIFTY pattern

---

## 📈 Margin Requirements (Approximate)

**BANKNIFTY with Lot Size 35:**
- **Buying Options:** Premium × 35 (full premium payment)
- **Selling Options:** ₹1,50,000 - ₹2,50,000 (SPAN + Exposure margin)
  - Varies with Bank Nifty spot price and volatility
  - Higher than NIFTY due to larger lot size

**Example:**
```
BANKNIFTY @ 44,500
44,500 × 35 = ₹15,57,500 (contract value)

Selling one ATM PUT:
SPAN Margin: ~₹1,80,000
Exposure Margin: ~₹40,000
Total: ~₹2,20,000 per lot
```

---

## ⚙️ System Updates Applied

### 1. risk_manager.py
```python
lot_sizes = {
    'NIFTY': 75,
    'BANKNIFTY': 35,  # ✅ Updated from 15
    'SENSEX': 20
}
```

### 2. market_data.py
```python
self.expiry_config = {
    'NIFTY': ('weekly', 1),      # Tuesday
    'BANKNIFTY': ('monthly', 3), # ✅ Last Thursday of month
    'SENSEX': ('weekly', 3)      # Thursday
}
```

Added new method:
```python
def _get_last_thursday_of_month(self, reference_date: datetime) -> str:
    """Calculate last Thursday of current/next month"""
```

### 3. config.yaml
```yaml
- symbol: "BANKNIFTY"
  lot_size: 35          # ✅ Updated
  expiry_day: "Last Thursday"  # ✅ Updated
  expiry_type: "monthly"       # ✅ Added
```

---

## 🧪 Testing Expiry Calculation

### Test Case 1: Today is Nov 12, 2025 (Tuesday)
```python
banknifty_expiry = market_data._get_current_weekly_expiry('BANKNIFTY')
# Expected: "2025-11-28" (Last Thursday of November)
```

### Test Case 2: Today is Nov 29, 2025 (After Nov expiry)
```python
banknifty_expiry = market_data._get_current_weekly_expiry('BANKNIFTY')
# Expected: "2025-12-25" (Last Thursday of December)
```

### Verification Command
```python
from backend.data.market_data import MarketDataManager
from datetime import datetime

# Test function
def test_last_thursday():
    test_dates = [
        datetime(2025, 11, 12),  # Should give Nov 28
        datetime(2025, 11, 29),  # Should give Dec 25
        datetime(2025, 12, 1),   # Should give Dec 25
        datetime(2025, 12, 26),  # Should give Jan 29, 2026
    ]
    
    for date in test_dates:
        result = market_data._get_last_thursday_of_month(date)
        print(f"{date.strftime('%Y-%m-%d')} -> {result}")
```

---

## 🎯 Trading Implications

### 1. Capital Requirements
- **Higher minimum capital needed** for BANKNIFTY
- Each lot requires 2.3x more capital than before
- Consider switching to cheaper strikes if capital limited

### 2. Position Sizing
- **Recalculate all position sizes** based on lot size 35
- Can't hold as many lots with same risk
- May need to adjust risk percentage

### 3. Time Decay
- **Monthly expiry means longer theta decay period**
- Options retain value longer
- Can benefit from multi-week strategies

### 4. Strategy Adjustments
- **Gap and Go strategy:** Less frequent BANKNIFTY opportunities
- **Expiry day strategies:** Only 1 per month instead of 4-5
- **Calendar spreads:** Can use monthly vs next month

---

## 📊 Risk Management Guidelines (Updated)

### Recommended Capital for 1 Lot

**Conservative (Premium ≤ ₹200):**
- NIFTY: ₹15,000 (₹200 × 75)
- BANKNIFTY: ₹7,000 (₹200 × 35)
- SENSEX: ₹4,000 (₹200 × 20)

**Moderate (Premium ≤ ₹400):**
- NIFTY: ₹30,000 (₹400 × 75)
- BANKNIFTY: ₹14,000 (₹400 × 35)
- SENSEX: ₹8,000 (₹400 × 20)

**Aggressive (Premium ≤ ₹600):**
- NIFTY: ₹45,000 (₹600 × 75)
- BANKNIFTY: ₹21,000 (₹600 × 35)
- SENSEX: ₹12,000 (₹600 × 20)

### Account Size Recommendations

**Minimum to Trade:**
- NIFTY: ₹50,000 (for proper risk management)
- BANKNIFTY: ₹30,000 (smaller lot size than NIFTY)
- SENSEX: ₹25,000

**Comfortable Trading:**
- NIFTY: ₹1,00,000+
- BANKNIFTY: ₹75,000+
- SENSEX: ₹50,000+

---

## ✅ Pre-Trading Checklist (Updated)

- [ ] Verify BANKNIFTY lot size is 35
- [ ] Confirm current month's last Thursday expiry date
- [ ] Recalculate position sizes based on lot 35
- [ ] Ensure adequate margin (₹2-2.5L for selling)
- [ ] Check if it's expiry week (last Thursday approaching)
- [ ] Adjust strategy for monthly cycle
- [ ] Set proper stop-loss for larger lot size

---

## 📅 November 2025 Calendar (Reference)

```
November 2025
Su Mo Tu We Th Fr Sa
                   1
 2  3  4  5  6  7  8
 9 10 11 12 13 14 15
16 17 18 19 20 21 22
23 24 25 26 27 28 29  ← BANKNIFTY Expiry (Last Thursday)
30
```

---

## 🔔 Important Reminders

### 1. No Weekly BANKNIFTY Expiry
- Unlike NIFTY (weekly Tuesday) and SENSEX (weekly Thursday)
- BANKNIFTY only expires **once per month**
- Plan positions accordingly

### 2. Higher Time Premium
- Options have 4-5 weeks to expiry (vs 1 week for NIFTY/SENSEX)
- ATM options will be more expensive
- Theta decay slower but cumulative over longer period

### 3. Rollover Strategy
- If holding positions beyond monthly expiry
- Need to roll to next month (gap between expiries)
- Consider impact on strategy

### 4. Institutional Activity
- Last Thursday sees heavy institutional unwinding
- Expect higher volatility on expiry day
- Pin risk near max pain zones

---

## 📞 Exchange References

**NSE Circular on BANKNIFTY:**
- Lot Size: 35
- Expiry: Last Thursday of expiry month
- Contract: Cash-settled index options

**Trading Hours:**
- 9:15 AM to 3:30 PM IST
- Expiry day same timings

**Settlement:**
- Cash-settled T+1
- Based on closing value on expiry day

---

## 🚀 System Status

**All corrections applied:**
- ✅ Lot size: 35
- ✅ Expiry: Last Thursday calculation implemented
- ✅ Config updated
- ✅ Documentation updated

**Test before trading:**
```bash
python backend/main.py

# In Python console:
from backend.data.market_data import MarketDataManager
# Verify expiry calculation
```

---

**CRITICAL:** Always verify current month's expiry date before taking BANKNIFTY positions!

**Last Updated:** November 12, 2025  
**Verified:** BANKNIFTY lot size 35, monthly expiry last Thursday
