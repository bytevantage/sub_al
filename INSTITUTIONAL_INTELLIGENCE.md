# Institutional Intelligence Feature

## Overview
Added real-time institutional activity analysis and actionable trading suggestions to NIFTY and SENSEX option cards based on OI changes, PCR, and VIX levels.

## Implementation Date
November 14, 2025

## Features Added

### 1. **Backend Analysis Engine** (`backend/api/watchlist.py`)

#### OI Change Analysis
- Calculates total Call OI changes and Put OI changes
- Compares magnitude and direction of both
- Identifies institutional patterns:
  - **Heavy Call Writing**: Call OI increases significantly → Resistance expected
  - **Heavy Put Writing**: Put OI increases significantly → Support expected
  - **Call Unwinding**: Call OI decreases → Bullish momentum
  - **Put Unwinding**: Put OI decreases → Bearish momentum
  - **Balanced OI**: Both increasing → Consolidation expected
  - **Both Unwinding**: Low conviction → High volatility

#### Smart Suggestions
Combines OI analysis with PCR to provide context-aware recommendations:
- "Buy Calls" when Put writing is strong
- "Buy Puts" when Call writing is heavy
- "Exit positions" when unwinding detected
- "Wait for clarity" on mixed signals
- "Range-bound strategies" during consolidation

#### Enhanced Sentiment Analysis
- **PCR > 1.2**: Bullish (Put buyers dominating)
- **PCR < 0.8**: Bearish (Call buyers dominating)
- **PCR 0.8-1.2**: Neutral (balanced)

#### VIX Guidance
- **VIX > 20**: "SELL premium (Straddles/Strangles)"
- **VIX < 12 + Bullish**: "BUY CE (Call options cheap), expect volatility spike & upside"
- **VIX < 12 + Bearish**: "BUY PE (Put options cheap), expect volatility spike & downside"
- **VIX < 12 + Neutral**: "BUY Straddle/Strangle (both CE+PE cheap), expect big move"
- **VIX 12-20 + Bullish**: "Directional BUY CE preferred (calls have edge)"
- **VIX 12-20 + Bearish**: "Directional BUY PE preferred (puts have edge)"
- **VIX 12-20 + Neutral**: "Range-bound strategies or wait for direction"

### 2. **Frontend Display** (`frontend/dashboard/dashboard.js` & `index.html`)

#### New UI Component: Institutional Intelligence Panel
Located under NIFTY and SENSEX option cards, displays:

1. **Market Sentiment**
   - Current sentiment (Bullish/Bearish/Neutral) with color coding
   - PCR value
   
2. **Institutional Activity**
   - Plain English description of what institutions are doing
   - Call OI change in lakhs (with color: red if increasing, green if decreasing)
   - Put OI change in lakhs (with color: green if increasing, red if decreasing)

3. **Trading Action**
   - Specific actionable suggestion
   - Examples:
     - "💡 Consider: Buy Calls or exit Put positions"
     - "💡 Strong Buy: Consider buying Calls aggressively"
     - "⚠️ Caution: Stay light or hedge existing positions"

4. **Volatility Status**
   - VIX interpretation with strategy advice

#### Styling
- Clean card-based layout
- Color-coded sentiment (green=bullish, red=bearish, yellow=neutral)
- Emoji indicators for quick visual scanning
- Responsive design

## API Response Structure

### New Fields in `market_context`
```json
{
  "market_context": {
    "spot_price": 25910.05,
    "pcr": 0.80,
    "sentiment": "Bearish",
    "sentiment_reason": "PCR 0.80 - Call buyers outnumber Put buyers",
    "vix": 11.94,
    "vix_status": "Low volatility - BUY options (cheap premium)",
    "total_call_oi": 196577625,
    "total_put_oi": 156719175,
    "total_call_oi_change": 73695825,
    "total_put_oi_change": 26766600,
    "institutional_activity": "📈 Heavy Call writing - Institutions expect resistance/sideways",
    "trading_suggestion": "⚠️ Mixed signals - Wait for clarity. PCR suggests bearish but Call OI rising"
  }
}
```

## Example Analysis Scenarios

### Scenario 1: Heavy Call Writing + Bearish PCR
- **Call OI**: +7.36 Cr (significant increase)
- **Put OI**: +2.67 Cr (moderate increase)
- **PCR**: 0.80 (Bearish)
- **Analysis**: "Mixed signals - Wait for clarity"
- **Reason**: Call writing suggests resistance, but low PCR indicates selling pressure

### Scenario 2: Put Writing + Bullish PCR
- **Call OI**: +1.2 Cr
- **Put OI**: +4.5 Cr (heavy)
- **PCR**: 1.35 (Bullish)
- **Analysis**: "Consider: Sell OTM Puts or Buy Calls on bounce"
- **Reason**: Strong Put writing indicates institutional support expectation

### Scenario 3: Both Unwinding
- **Call OI**: -2.1 Cr
- **Put OI**: -1.8 Cr
- **Analysis**: "Both sides unwinding - Low conviction, expect volatility"
- **Suggestion**: "⚠️ Caution: Stay light or hedge existing positions"

## Files Modified

### Backend
- `backend/api/watchlist.py` (lines 92-170, 185-195, 350-365)
  - Added OI change calculation
  - Implemented institutional activity analysis
  - Enhanced sentiment logic
  - Added trading suggestion engine

### Frontend
- `frontend/dashboard/dashboard.js`
  - Added `displayInstitutionalIntelligence()` function (after line 1730)
  - Modified `updateWatchlist()` to call intelligence display
  
- `frontend/dashboard/style.css`
  - Added `.institutional-intelligence` styles (after line 953)
  - Styling for intel sections, activity, suggestions

- `frontend/dashboard/index.html`
  - Updated version to v3.2

## Testing

### API Test Commands
```bash
# Test NIFTY
curl -s 'http://localhost:8000/api/watchlist/recommended-strikes?symbol=NIFTY' | \
  python3 -c "import sys, json; d=json.load(sys.stdin); mc=d['market_context']; \
  print(f'Activity: {mc[\"institutional_activity\"]}'); \
  print(f'Suggestion: {mc[\"trading_suggestion\"]}')"

# Test SENSEX
curl -s 'http://localhost:8000/api/watchlist/recommended-strikes?symbol=SENSEX' | \
  python3 -c "import sys, json; d=json.load(sys.stdin); mc=d['market_context']; \
  print(f'Activity: {mc[\"institutional_activity\"]}'); \
  print(f'Suggestion: {mc[\"trading_suggestion\"]}')"
```

### Current Market Example (Nov 14, 2025 - 6:25 PM IST)
**NIFTY**:
- Sentiment: Bearish (PCR 0.80)
- Call OI Change: +737 L
- Put OI Change: +267.7 L
- Activity: Heavy Call writing - Institutions expect resistance/sideways
- Suggestion: Mixed signals - Wait for clarity
- VIX: 11.94 (Low)
- **Volatility Strategy**: "BUY PE (Put options cheap), expect volatility spike & downside"

**SENSEX**:
- Sentiment: Bearish (PCR 0.74)
- Call OI Change: +66 L
- Put OI Change: +42 L
- Activity: Heavy Call writing - Institutions expect resistance/sideways
- Suggestion: Mixed signals - Wait for clarity
- VIX: 11.94 (Low)
- **Volatility Strategy**: "BUY PE (Put options cheap), expect volatility spike & downside"

## Benefits

1. **Actionable Intelligence**: Clear trading suggestions instead of raw numbers
2. **Context Awareness**: Combines multiple indicators (OI, PCR, VIX) for holistic view
3. **Plain English**: No jargon - explains what institutions are doing
4. **Real-time Updates**: Refreshes every 30 seconds with watchlist data
5. **Visual Clarity**: Color-coded indicators for quick scanning
6. **Risk Management**: Warns on mixed signals and low conviction periods

## User Decision Support

### When to Buy Calls
- Put OI building (institutions writing Puts = support expected)
- Call OI unwinding (shorts covering)
- PCR > 1.2 (bullish sentiment)
- VIX < 12 (cheap options)

### When to Buy Puts
- Call OI building (institutions writing Calls = resistance expected)
- Put OI unwinding (protection being removed)
- PCR < 0.8 (bearish sentiment)
- VIX < 12 (cheap options)

### When to Exit
- Mixed signals (OI and PCR conflicting)
- Both OI unwinding (low conviction)
- Opposite of your position building

### When to Wait
- No significant OI changes
- Balanced OI buildup (consolidation)
- Very high VIX (premium too expensive to buy)

## Dashboard Version
**v3.3** - Enhanced VIX Guidance with CE/PE Recommendations

## Version History
- **v3.3** (Nov 14, 2025): Enhanced VIX guidance - specific CE/PE recommendations based on sentiment
- **v3.2** (Nov 14, 2025): Initial institutional intelligence release
- **v3.1** (Nov 14, 2025): Layout reorganization (Risk Metrics + Open Positions)
- **v3.0** (Nov 14, 2025): PCR bug fix
- **v2.9** (Nov 14, 2025): Timezone fixes (IST support)
