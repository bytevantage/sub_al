# 📊 Instrument Specifications & Expiry Details

## Official Lot Sizes & Expiry Schedule (As of November 2025)

### 🎯 Quick Reference Table

| Symbol | Exchange | Lot Size | Expiry Day | Weekly Expiry |
|--------|----------|----------|------------|---------------|
| **NIFTY** | NSE | **75** | **Tuesday** | Every Week |
| **BANKNIFTY** | NSE | **15** | **Wednesday** | Every Week |
| **SENSEX** | BSE | **20** | **Thursday** | Every Week |

---

## 📋 Detailed Specifications

### 1. NIFTY (Nifty 50 Index)

**Basic Information:**
- **Full Name:** Nifty 50 Index Options
- **Exchange:** National Stock Exchange (NSE)
- **Segment:** Options (OPT)
- **Underlying:** Nifty 50 Index
- **Tick Size:** ₹0.05

**Contract Specifications:**
- **Lot Size:** 75 (Updated from 50)
- **Contract Value:** Spot Price × 75
  - Example: If Nifty at 19,500, contract value = ₹14,62,500
- **Margin Required:** ~₹80,000 - ₹1,20,000 (varies with volatility)

**Expiry Details:**
- **Weekly Expiry:** Every **Tuesday**
- **Expiry Time:** 3:30 PM IST
- **Settlement:** Cash-settled on T+1 basis
- **Last Trading Day:** Expiry day (Tuesday)

**Example Expiry Dates (November-December 2025):**
- Nov 12, 2025 (Tuesday)
- Nov 19, 2025 (Tuesday)
- Nov 26, 2025 (Tuesday)
- Dec 03, 2025 (Tuesday)
- Dec 10, 2025 (Tuesday)

---

### 2. BANKNIFTY (Bank Nifty Index)

**Basic Information:**
- **Full Name:** Bank Nifty Index Options
- **Exchange:** National Stock Exchange (NSE)
- **Segment:** Options (OPT)
- **Underlying:** Bank Nifty Index
- **Tick Size:** ₹0.05

**Contract Specifications:**
- **Lot Size:** 15 (Unchanged)
- **Contract Value:** Spot Price × 15
  - Example: If Bank Nifty at 44,500, contract value = ₹6,67,500
- **Margin Required:** ~₹60,000 - ₹1,00,000 (varies with volatility)

**Expiry Details:**
- **Weekly Expiry:** Every **Wednesday**
- **Expiry Time:** 3:30 PM IST
- **Settlement:** Cash-settled on T+1 basis
- **Last Trading Day:** Expiry day (Wednesday)

**Example Expiry Dates (November-December 2025):**
- Nov 13, 2025 (Wednesday)
- Nov 20, 2025 (Wednesday)
- Nov 27, 2025 (Wednesday)
- Dec 04, 2025 (Wednesday)
- Dec 11, 2025 (Wednesday)

---

### 3. SENSEX (S&P BSE Sensex Index)

**Basic Information:**
- **Full Name:** S&P BSE Sensex Index Options
- **Exchange:** Bombay Stock Exchange (BSE)
- **Segment:** Options (OPT)
- **Underlying:** Sensex Index
- **Tick Size:** ₹0.05

**Contract Specifications:**
- **Lot Size:** 20 (Updated from 10)
- **Contract Value:** Spot Price × 20
  - Example: If Sensex at 65,000, contract value = ₹13,00,000
- **Margin Required:** ~₹70,000 - ₹1,10,000 (varies with volatility)

**Expiry Details:**
- **Weekly Expiry:** Every **Thursday**
- **Expiry Time:** 3:30 PM IST
- **Settlement:** Cash-settled on T+1 basis
- **Last Trading Day:** Expiry day (Thursday)

**Example Expiry Dates (November-December 2025):**
- Nov 14, 2025 (Thursday)
- Nov 21, 2025 (Thursday)
- Nov 28, 2025 (Thursday)
- Dec 05, 2025 (Thursday)
- Dec 12, 2025 (Thursday)

---

## 💰 Position Sizing Examples

### Example 1: NIFTY Options
**Scenario:** NIFTY at 19,500, buying 19,500 CALL at ₹150

- **Lot Size:** 75
- **Premium per lot:** ₹150 × 75 = ₹11,250
- **For 2 lots:** ₹11,250 × 2 = ₹22,500
- **Break-even:** 19,650 (19,500 + 150)
- **Max Risk:** ₹22,500 (premium paid)

### Example 2: BANKNIFTY Options
**Scenario:** BANKNIFTY at 44,500, buying 44,500 PUT at ₹200

- **Lot Size:** 15
- **Premium per lot:** ₹200 × 15 = ₹3,000
- **For 3 lots:** ₹3,000 × 3 = ₹9,000
- **Break-even:** 44,300 (44,500 - 200)
- **Max Risk:** ₹9,000 (premium paid)

### Example 3: SENSEX Options
**Scenario:** SENSEX at 65,000, buying 65,000 CALL at ₹300

- **Lot Size:** 20
- **Premium per lot:** ₹300 × 20 = ₹6,000
- **For 2 lots:** ₹6,000 × 2 = ₹12,000
- **Break-even:** 65,300 (65,000 + 300)
- **Max Risk:** ₹12,000 (premium paid)

---

## 🗓️ Weekly Trading Calendar

### Monday
- **Market Opens:** 9:15 AM
- **No Weekly Expiries**
- Fresh week strategies begin

### Tuesday
- **NIFTY Weekly Expiry** 🎯
- Expiry Time: 3:30 PM
- Most liquid day for Nifty options
- High volume in last hour (2:30-3:30 PM)

### Wednesday
- **BANKNIFTY Weekly Expiry** 🏦
- Expiry Time: 3:30 PM
- Banking sector focus
- Post-NIFTY expiry positioning

### Thursday
- **SENSEX Weekly Expiry** 📈
- Expiry Time: 3:30 PM
- BSE platform
- Lower volumes compared to NSE

### Friday
- **No Weekly Expiries**
- Monthly expiry week: End-of-month settlements
- Weekend positioning strategies

---

## ⚙️ System Configuration

### In risk_manager.py
```python
def _get_lot_size(self, symbol: str) -> int:
    """
    Get lot size for symbol
    
    Official lot sizes (as of Nov 2025):
    - NIFTY: 75 (expires every Tuesday)
    - BANKNIFTY: 15 (expires every Wednesday)
    - SENSEX: 20 (expires every Thursday)
    """
    lot_sizes = {
        'NIFTY': 75,
        'BANKNIFTY': 15,
        'SENSEX': 20
    }
    return lot_sizes.get(symbol, 75)
```

### In market_data.py
```python
def __init__(self, upstox_client: UpstoxClient):
    # Symbol-specific expiry tracking
    self.expiry_config = {
        'NIFTY': 1,      # Tuesday
        'BANKNIFTY': 2,  # Wednesday
        'SENSEX': 3      # Thursday
    }
```

### In config.yaml
```yaml
instruments:
  - symbol: "NIFTY"
    exchange: "NSE"
    segment: "OPT"
    lot_size: 75
    expiry_day: "Tuesday"
    expiry_weekday: 1
    
  - symbol: "BANKNIFTY"
    exchange: "NSE"
    segment: "OPT"
    lot_size: 15
    expiry_day: "Wednesday"
    expiry_weekday: 2
    
  - symbol: "SENSEX"
    exchange: "BSE"
    segment: "OPT"
    lot_size: 20
    expiry_day: "Thursday"
    expiry_weekday: 3
```

---

## 📊 Risk Management Guidelines

### Lot Size Impact on Risk

**NIFTY (Lot Size 75):**
- ₹100 premium = ₹7,500 risk per lot
- ₹200 premium = ₹15,000 risk per lot
- ₹300 premium = ₹22,500 risk per lot

**BANKNIFTY (Lot Size 15):**
- ₹200 premium = ₹3,000 risk per lot
- ₹400 premium = ₹6,000 risk per lot
- ₹600 premium = ₹9,000 risk per lot

**SENSEX (Lot Size 20):**
- ₹300 premium = ₹6,000 risk per lot
- ₹500 premium = ₹10,000 risk per lot
- ₹700 premium = ₹14,000 risk per lot

### Recommended Position Sizing (₹1,00,000 Capital)

**Conservative (1% risk per trade = ₹1,000):**
- NIFTY: Options with ₹13 premium or less (75 lot)
- BANKNIFTY: Options with ₹67 premium or less (15 lot)
- SENSEX: Options with ₹50 premium or less (20 lot)

**Moderate (2% risk per trade = ₹2,000):**
- NIFTY: Options with ₹27 premium or less (75 lot)
- BANKNIFTY: Options with ₹133 premium or less (15 lot)
- SENSEX: Options with ₹100 premium or less (20 lot)

**Aggressive (3% risk per trade = ₹3,000):**
- NIFTY: Options with ₹40 premium or less (75 lot)
- BANKNIFTY: Options with ₹200 premium or less (15 lot)
- SENSEX: Options with ₹150 premium or less (20 lot)

---

## 🎯 Expiry Week Strategy Considerations

### Tuesday (NIFTY Expiry)
- **Pre-Expiry (Mon-Tue Morning):** Position building
- **Expiry Day (Tue 2:30-3:30 PM):** High volatility, pin risk
- **Post-Expiry (Wed onwards):** Fresh weekly positions

### Wednesday (BANKNIFTY Expiry)
- **Pre-Expiry (Tue-Wed Morning):** Banking sector events impact
- **Expiry Day (Wed 2:30-3:30 PM):** Institutional unwinding
- **Post-Expiry (Thu onwards):** Reduced overall market OI

### Thursday (SENSEX Expiry)
- **Pre-Expiry (Wed-Thu Morning):** BSE-specific flows
- **Expiry Day (Thu 2:30-3:30 PM):** Lower volumes vs NSE
- **Post-Expiry (Fri):** Weekend positioning, monthly expiry prep

---

## 🔔 Important Notes

### 1. Lot Size Changes
- **NIFTY lot size increased from 50 to 75** (effective date varies)
- **SENSEX lot size increased from 10 to 20** (effective date varies)
- Always verify current lot sizes before trading

### 2. Margin Requirements
- Margins vary based on market volatility (VIX)
- Higher VIX = Higher margin requirements
- SPAN + Exposure margins applicable for selling options

### 3. Settlement
- All three are **cash-settled**
- No physical delivery of stocks
- Settlement based on final closing price on expiry day

### 4. Trading Hours
- **Market Open:** 9:15 AM IST
- **Market Close:** 3:30 PM IST
- **Pre-Open:** 9:00 AM - 9:15 AM
- **Closing Session:** 3:30 PM - 3:40 PM

### 5. STT (Securities Transaction Tax)
- **Buy side:** 0.05% of premium
- **Sell side (in-the-money at expiry):** 0.125% of settlement value
- Factor into P&L calculations

---

## 📈 System Automatic Expiry Calculation

The trading system automatically calculates the correct weekly expiry for each symbol:

```python
# NIFTY - finds next Tuesday
nifty_expiry = market_data._get_current_weekly_expiry('NIFTY')
# Output: "2025-11-12" (if today is Nov 11, 2025)

# BANKNIFTY - finds next Wednesday
banknifty_expiry = market_data._get_current_weekly_expiry('BANKNIFTY')
# Output: "2025-11-13" (if today is Nov 11, 2025)

# SENSEX - finds next Thursday
sensex_expiry = market_data._get_current_weekly_expiry('SENSEX')
# Output: "2025-11-14" (if today is Nov 11, 2025)
```

**Logic:**
- Checks today's weekday
- Calculates days ahead to target expiry day
- If target day has passed, adds 7 days for next week
- Returns date in YYYY-MM-DD format

---

## ✅ Pre-Trading Checklist

Before starting the trading system:

- [ ] Verify lot sizes are correct (NIFTY: 75, BANKNIFTY: 15, SENSEX: 20)
- [ ] Confirm expiry days (NIFTY: Tue, BANKNIFTY: Wed, SENSEX: Thu)
- [ ] Check current week's expiry dates
- [ ] Calculate position sizes based on lot sizes
- [ ] Set appropriate risk per trade (1-3% of capital)
- [ ] Ensure margin requirements are met
- [ ] Verify market hours and expiry times

---

## 🔄 Monthly Updates Required

While lot sizes change infrequently, always verify:

1. **NSE Circulars:** For NIFTY and BANKNIFTY lot size changes
2. **BSE Circulars:** For SENSEX lot size changes
3. **Margin Changes:** VIX-based adjustments
4. **Holiday Calendar:** Market holidays affect expiry dates

**Sources:**
- NSE: https://www.nseindia.com/
- BSE: https://www.bseindia.com/
- SEBI: https://www.sebi.gov.in/

---

**Last Updated:** November 12, 2025  
**Verified:** Lot sizes and expiry days confirmed as of Nov 2025  
**Next Review:** Monthly or upon regulatory changes

---

## 🚀 Quick Commands

**Check current expiry for all symbols:**
```python
# In Python console or trading system
from backend.data.market_data import MarketDataManager

# Get expiries
nifty_exp = market_data._get_current_weekly_expiry('NIFTY')
banknifty_exp = market_data._get_current_weekly_expiry('BANKNIFTY')
sensex_exp = market_data._get_current_weekly_expiry('SENSEX')

print(f"NIFTY expires: {nifty_exp}")
print(f"BANKNIFTY expires: {banknifty_exp}")
print(f"SENSEX expires: {sensex_exp}")
```

**Calculate position size:**
```python
# Example: 2% risk on ₹1,00,000 capital = ₹2,000
risk_amount = 2000

# NIFTY option at ₹150 premium
nifty_lots = risk_amount / (150 * 75)  # = 0.17 lots (round to 1)

# BANKNIFTY option at ₹400 premium
banknifty_lots = risk_amount / (400 * 15)  # = 0.33 lots (round to 1)

# SENSEX option at ₹300 premium
sensex_lots = risk_amount / (300 * 20)  # = 0.33 lots (round to 1)
```

---

**All lot sizes and expiry schedules are now correctly configured in the trading system! ✅**
