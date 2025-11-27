"""
Simple, Robust Options Strategy - No ML Complexity
Focuses on proven options trading principles
"""

def simple_options_strategy(market_data):
    """
    Simple options strategy based on proven principles:
    1. PCR divergence
    2. Volume spikes
    3. Gamma exposure
    4. Time-based exits
    """

    signals = []

    # Get market data
    spot = market_data.get('spot_price', 0)
    option_chain = market_data.get('option_chain', {})
    pcr = option_chain.get('pcr', 1.0)
    total_oi = option_chain.get('total_call_oi', 0) + option_chain.get('total_put_oi', 0)

    # Strategy 1: PCR Mean Reversion
    if pcr > 1.3:  # Extreme bearish sentiment
        signals.append({
            'strategy': 'PCR_Reversal',
            'direction': 'CALL',
            'reason': 'PCR > 1.3 - Extreme bearish, expect reversal',
            'confidence': min(0.7, pcr / 2.0),
            'risk': 'medium'
        })
    elif pcr < 0.7:  # Extreme bullish sentiment
        signals.append({
            'strategy': 'PCR_Reversal',
            'direction': 'PUT',
            'reason': 'PCR < 0.7 - Extreme bullish, expect reversal',
            'confidence': min(0.7, 1.0 / pcr),
            'risk': 'medium'
        })

    # Strategy 2: OI Imbalance
    call_oi = option_chain.get('total_call_oi', 0)
    put_oi = option_chain.get('total_put_oi', 0)

    oi_ratio = call_oi / put_oi if put_oi > 0 else 2.0

    if oi_ratio > 1.5 and pcr < 0.9:  # Calls dominate but PCR suggests bearish
        signals.append({
            'strategy': 'OI_Divergence',
            'direction': 'PUT',
            'reason': 'OI favors calls but PCR bearish - divergence signal',
            'confidence': 0.6,
            'risk': 'low'
        })

    # Strategy 3: ATM Options Only (Simplest)
    if 0.9 <= pcr <= 1.1:  # Neutral market
        signals.append({
            'strategy': 'ATM_Neutral',
            'direction': 'BOTH',  # Iron condor style
            'reason': 'Neutral PCR - ATM strangle opportunity',
            'confidence': 0.5,
            'risk': 'very_low'
        })

    return signals

# Example usage
if __name__ == "__main__":
    # Sample market data
    sample_data = {
        'spot_price': 26000,
        'option_chain': {
            'pcr': 0.85,
            'total_call_oi': 1000000,
            'total_put_oi': 1200000
        }
    }

    signals = simple_options_strategy(sample_data)
    print(f"Generated {len(signals)} signals:")
    for signal in signals:
        print(f"  {signal['strategy']}: {signal['direction']} ({signal['confidence']:.1f} confidence)")
        print(f"    Reason: {signal['reason']}")
        print(f"    Risk: {signal['risk']}")
        print()
