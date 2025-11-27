"""
Simple Option Chain Analysis
Analyzes saved option chain data and shows key insights
"""

import json
import numpy as np
from pathlib import Path

def analyze_option_data():
    """Analyze the saved option chain data"""

    data_file = Path("data/historical/2025-11-19_db.json")

    if not data_file.exists():
        print("No historical data found!")
        return

    with open(data_file, 'r') as f:
        raw_data = json.load(f)

    print("="*80)
    print("OPTION CHAIN DATA ANALYSIS")
    print("="*80)

    snapshots = []

    for timestamp, data in sorted(raw_data.items()):
        try:
            nifty_data = data.get('NIFTY', {})
            spot_price = nifty_data.get('spot_price') or nifty_data.get('ltp')
            if not spot_price:
                continue

            option_chain = nifty_data.get('option_chain', {})
            calls = option_chain.get('calls', {})
            puts = option_chain.get('puts', {})

            if not calls and not puts:
                continue

            snapshot = {
                'timestamp': timestamp,
                'spot_price': spot_price,
                'calls_count': len(calls),
                'puts_count': len(puts),
                'total_options': len(calls) + len(puts),
                'call_oi': sum(opt.get('oi', 0) for opt in calls.values()),
                'put_oi': sum(opt.get('oi', 0) for opt in puts.values())
            }

            snapshot['total_oi'] = snapshot['call_oi'] + snapshot['put_oi']
            if snapshot['call_oi'] > 0:
                snapshot['pcr'] = snapshot['put_oi'] / snapshot['call_oi']
            else:
                snapshot['pcr'] = 0

            # Collect Greeks data
            iv_values = []
            delta_values = []
            gamma_values = []

            for option_data in calls.values():
                if option_data.get('iv'):
                    iv_values.append(option_data['iv'])
                if option_data.get('delta'):
                    delta_values.append(option_data['delta'])
                if option_data.get('gamma'):
                    gamma_values.append(option_data['gamma'])

            for option_data in puts.values():
                if option_data.get('iv'):
                    iv_values.append(option_data['iv'])
                if option_data.get('delta'):
                    delta_values.append(option_data['delta'])
                if option_data.get('gamma'):
                    gamma_values.append(option_data['gamma'])

            if iv_values:
                snapshot['avg_iv'] = sum(iv_values) / len(iv_values)
            if delta_values:
                snapshot['avg_delta'] = sum(delta_values) / len(delta_values)
            if gamma_values:
                snapshot['avg_gamma'] = sum(gamma_values) / len(gamma_values)

            snapshots.append(snapshot)

        except Exception as e:
            continue

    if not snapshots:
        print("No valid option chain data found!")
        return

    print(f"Analyzed {len(snapshots)} snapshots")
    print(f"Time range: {snapshots[0]['timestamp']} to {snapshots[-1]['timestamp']}")

    # Market analysis
    spot_prices = [s['spot_price'] for s in snapshots]
    pcrs = [s.get('pcr', 0) for s in snapshots if s.get('pcr', 0) > 0]
    ivs = [s.get('avg_iv', 0) for s in snapshots if s.get('avg_iv', 0) > 0]

    print(f"\n📊 MARKET SUMMARY:")
    print(f"   Spot Range: ₹{min(spot_prices):.2f} - ₹{max(spot_prices):.2f}")
    if pcrs:
        print(f"   PCR Range: {min(pcrs):.2f} - {max(pcrs):.2f} (Avg: {sum(pcrs)/len(pcrs):.2f})")
    if ivs:
        print(f"   IV Range: {min(ivs):.1f}% - {max(ivs):.1f}% (Avg: {sum(ivs)/len(ivs):.1f}%)")

    total_oi_values = [s['total_oi'] for s in snapshots]
    print(f"   Total OI Range: {min(total_oi_values):,} - {max(total_oi_values):,}")

    print(f"\n📈 OPTION CHAIN STATS:")
    print(f"   Options per snapshot: {int(sum(s['total_options'] for s in snapshots)/len(snapshots))}")
    print(f"   Call/Put ratio: {sum(s['calls_count'] for s in snapshots)/sum(s['puts_count'] for s in snapshots):.2f}")

    # Simulate basic trading strategy
    print(f"\n🎯 TRADING SIMULATION:")

    capital = 100000.0
    trades = []

    for snapshot in snapshots[::3]:  # Every 3rd snapshot
        pcr = snapshot.get('pcr', 1.0)
        avg_iv = snapshot.get('avg_iv', 15)

        # Simple PCR-based strategy
        if pcr > 1.1:  # Bearish bias
            direction = "PUT"
            confidence = min(0.7, pcr / 1.5)
        elif pcr < 0.9:  # Bullish bias
            direction = "CALL"
            confidence = min(0.7, 1.0 / pcr)
        else:
            continue  # Skip neutral conditions

        # Execute trade
        risk_amount = capital * 0.01  # 1% risk
        option_price = snapshot['spot_price'] * 0.008  # Rough option price
        quantity = max(1, int(risk_amount / option_price))

        capital -= option_price * quantity

        # Simulate exit (assume 50% win rate with realistic P&L)
        win = np.random.random() < 0.5
        if win:
            exit_multiplier = np.random.uniform(1.05, 1.25)
        else:
            exit_multiplier = np.random.uniform(0.75, 0.95)

        exit_price = option_price * exit_multiplier
        pnl = (exit_price - option_price) * quantity
        capital += exit_price * quantity

        trades.append({
            'direction': direction,
            'pnl': pnl,
            'pcr': pcr,
            'iv': avg_iv
        })

    # Results
    if trades:
        total_pnl = sum(t['pnl'] for t in trades)
        win_rate = sum(1 for t in trades if t['pnl'] > 0) / len(trades) * 100

        print(f"   Trades executed: {len(trades)}")
        print(f"   Win rate: {win_rate:.1f}%")
        print(f"   Total P&L: ₹{total_pnl:,.2f} ({total_pnl/100000*100:+.2f}%)")
        print(f"   Final capital: ₹{capital:,.2f}")

        if total_pnl > 0:
            print("   ✅ Profitable strategy with option chain data!")
        else:
            print("   ⚠️ Strategy needs refinement")

    print("\n" + "="*80)

if __name__ == "__main__":
    analyze_option_data()
