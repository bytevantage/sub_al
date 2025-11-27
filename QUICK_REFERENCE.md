# 📋 QUICK REFERENCE CARD

## 🎯 Lot Sizes & Expiry (Correct as of Nov 2025)

```
┌─────────────┬──────────┬─────────────────┬─────────────┐
│   SYMBOL    │ LOT SIZE │     EXPIRY      │   EXAMPLE   │
├─────────────┼──────────┼─────────────────┼─────────────┤
│   NIFTY     │    75    │ TUESDAY (Weekly)│ Nov 12, 19  │
│  BANKNIFTY  │    35    │LAST THU (Monthly│ Nov 28 only │
│   SENSEX    │    20    │THURSDAY (Weekly)│ Nov 14, 21  │
└─────────────┴──────────┴─────────────────┴─────────────┘
```

## 💰 Position Size Quick Calculator

**₹1,00,000 Capital | 2% Risk = ₹2,000**

| Premium | NIFTY (75) | BANKNIFTY (35) | SENSEX (20) |
|---------|------------|----------------|-------------|
| ₹50     | 0.5 lot    | 1.1 lots       | 2.0 lots    |
| ₹100    | 0.27 lot   | 0.57 lot       | 1.0 lot     |
| ₹150    | 0.18 lot   | 0.38 lot       | 0.67 lot    |
| ₹200    | 0.13 lot   | 0.29 lot       | 0.5 lot     |
| ₹300    | 0.09 lot   | 0.19 lot       | 0.33 lot    |

*Round up to nearest whole lot for actual trade*

## 📅 This Week's Expiries (Nov 11-15, 2025)

```
Mon Nov 11: Market opens, no expiries
Tue Nov 12: NIFTY expires 3:30 PM ⚠️
Wed Nov 13: Regular trading
Thu Nov 14: SENSEX expires 3:30 PM ⚠️
Fri Nov 15: Regular trading

BANKNIFTY: Nov 28 (Last Thursday) ⚠️
```

## 🔢 Quick Calculations

### Contract Values (at current levels)
- **NIFTY** @ 19,500: 19,500 × 75 = **₹14,62,500**
- **BANKNIFTY** @ 44,500: 44,500 × 35 = **₹15,57,500**
- **SENSEX** @ 65,000: 65,000 × 20 = **₹13,00,000**

### Premium Risk per Lot
- **NIFTY**: Premium × 75 = Risk
- **BANKNIFTY**: Premium × 35 = Risk
- **SENSEX**: Premium × 20 = Risk

### Examples
```
NIFTY ₹150 premium = ₹150 × 75 = ₹11,250 risk
BANKNIFTY ₹400 premium = ₹400 × 35 = ₹14,000 risk
SENSEX ₹300 premium = ₹300 × 20 = ₹6,000 risk
```

## 🔧 System Files Updated

✅ `backend/execution/risk_manager.py` - Lot sizes
✅ `backend/data/market_data.py` - Expiry logic
✅ `config/config.yaml` - Configuration
✅ `INSTRUMENT_SPECIFICATIONS.md` - Full guide

## 🚀 Start Command

```bash
python backend/main.py
```

## 📊 All 20 Strategies Active

**Tier 1 (80-85):** Order Flow, OI Analysis, Institutional  
**Tier 2 (70-79):** PCR, Gap&Go, Hidden OI, Greeks, IV Skew  
**Tier 3 (60-69):** Iron Condor, VIX, Max Pain, Cross-Asset  
**Tier 4 (50-59):** Support/Resistance, Multi-Leg Arbitrage

## 📈 Trade History Available

**7 API Endpoints:**
- GET `/api/trades/history` - All trades
- GET `/api/trades/statistics` - Stats
- GET `/api/trades/export/csv` - Excel export
- GET `/api/trades/{trade_id}` - Details
- And 3 more...

**Swagger UI:** `http://localhost:8000/docs`

## ⚠️ Pre-Trade Checklist

- [ ] Verify lot sizes (NIFTY: 75, BANKNIFTY: 35, SENSEX: 20)
- [ ] Check this week's expiry dates (NIFTY: Tue, SENSEX: Thu)
- [ ] BANKNIFTY: Verify last Thursday of month
- [ ] Calculate position sizes
- [ ] Ensure adequate margin
- [ ] Start in paper mode first
- [ ] Test all 20 strategies
- [ ] Monitor console logs

## 📚 Documentation

| File | Purpose |
|------|---------|
| FINAL_UPDATE_SUMMARY.md | This update |
| INSTRUMENT_SPECIFICATIONS.md | Complete guide |
| QUICK_START_TESTING.md | Testing steps |
| API_DOCUMENTATION.md | All endpoints |
| PROJECT_COMPLETION_SUMMARY.md | Full overview |

## 🎯 Everything Complete!

✅ All 20 strategies  
✅ Trade history system  
✅ Correct lot sizes (75, 35, 20)  
✅ Correct expiries (Tue weekly, Last Thu monthly, Thu weekly)  
✅ Full documentation  

**Ready to trade! 🚀**

---

⚠️ **CRITICAL:** BANKNIFTY lot size 35, expires LAST THURSDAY of month (monthly, not weekly!)

*Print this card and keep it handy for trading hours*
