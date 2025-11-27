"""
Option Chain Data Analysis and Backtest
Analyzes saved option chain data with Greeks and simulates trading performance
"""

import json
import numpy as np
import pandas as pd
from datetime import datetime
from pathlib import Path
from collections import defaultdict

def load_option_chain_data(date_str="2025-11-19"):
    """Load and analyze option chain data for backtesting"""
    data_dir = Path("data/historical")

    # Try different file formats
    possible_files = [
        data_dir / f"{date_str}_db.json",
        data_dir / f"{date_str}.json"
    ]

    for file_path in possible_files:
        if file_path.exists():
            print(f"Loading data from: {file_path}")
            with open(file_path, 'r') as f:
                return json.load(f)

    raise FileNotFoundError(f"No historical data found for {date_str}")

def analyze_option_chain_data(raw_data):
    """Analyze option chain data and extract key metrics"""

    print("\n" + "="*80)
    print("OPTION CHAIN DATA ANALYSIS")
    print("="*80)

    snapshots = []
    strikes_data = defaultdict(list)

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
                'atm_strike': round(spot_price, -2),
                'calls': len(calls),
                'puts': len(puts),
                'total_options': len(calls) + len(puts),
                'call_oi': sum(opt.get('oi', 0) for opt in calls.values()),
                'put_oi': sum(opt.get('oi', 0) for opt in puts.values()),
                'total_oi': 0,
                'pcr': None,
                'atm_iv_call': None,
                'atm_iv_put': None,
                'avg_iv': None,
                'gamma_exposure': 0,
                'delta_exposure': 0
            }

            snapshot['total_oi'] = snapshot['call_oi'] + snapshot['put_oi']
            if snapshot['call_oi'] > 0:
                snapshot['pcr'] = snapshot['put_oi'] / snapshot['call_oi']

            # Analyze Greeks and IV
            iv_values = []
            for strike_str, option_data in calls.items():
                try:
                    strike = float(strike_str)
                    strikes_data[strike].append({
                        'type': 'call',
                        'timestamp': timestamp,
                        'ltp': option_data.get('ltp', 0),
                        'oi': option_data.get('oi', 0),
                        'iv': option_data.get('iv'),
                        'delta': option_data.get('delta'),
                        'gamma': option_data.get('gamma'),
                        'theta': option_data.get('theta'),
                        'vega': option_data.get('vega')
                    })

                    if option_data.get('iv'):
                        iv_values.append(option_data['iv'])

                    # Track ATM data
                    if abs(strike - snapshot['atm_strike']) <= 100:
                        if option_data.get('iv'):
                            snapshot['atm_iv_call'] = option_data['iv']

                    # Calculate gamma exposure (weighted by OI)
                    if option_data.get('gamma') and option_data.get('oi'):
                        snapshot['gamma_exposure'] += option_data['gamma'] * option_data['oi']

                except (ValueError, TypeError):
                    continue

            for strike_str, option_data in puts.items():
                try:
                    strike = float(strike_str)
                    strikes_data[strike].append({
                        'type': 'put',
                        'timestamp': timestamp,
                        'ltp': option_data.get('ltp', 0),
                        'oi': option_data.get('oi', 0),
                        'iv': option_data.get('iv'),
                        'delta': option_data.get('delta'),
                        'gamma': option_data.get('gamma'),
                        'theta': option_data.get('theta'),
                        'vega': option_data.get('vega')
                    })

                    if option_data.get('iv'):
                        iv_values.append(option_data['iv'])

                    # Track ATM data
                    if abs(strike - snapshot['atm_strike']) <= 100:
                        if option_data.get('iv'):
                            snapshot['atm_iv_put'] = option_data['iv']

                    # Calculate gamma exposure (weighted by OI)
                    if option_data.get('gamma') and option_data.get('oi'):
                        snapshot['gamma_exposure'] += option_data['gamma'] * option_data['oi']

                except (ValueError, TypeError):
                    continue

            if iv_values:
                snapshot['avg_iv'] = sum(iv_values) / len(iv_values)

            snapshots.append(snapshot)

        except Exception as e:
            print(f"Error processing {timestamp}: {e}")
            continue

    return snapshots, strikes_data

def simulate_option_trading(snapshots, strikes_data):
    """Simulate trading based on option chain analysis"""

    print("\n" + "="*80)
    print("OPTION TRADING SIMULATION")
    print("="*80)

    capital = 100000.0
    initial_capital = capital
    trades = []

    # Trading rules based on option chain analysis
    for i, snapshot in enumerate(snapshots):
        spot = snapshot['spot_price']
        atm_strike = snapshot['atm_strike']
        pcr = snapshot.get('pcr', 1.0)
        gamma_exp = snapshot.get('gamma_exposure', 0)
        avg_iv = snapshot.get('avg_iv', 15)

        # Strategy 1: PCR-based directional bias
        if pcr > 1.2:  # High PCR suggests bearish sentiment
            direction = "PUT"
            confidence = min(0.8, pcr / 2.0)
        elif pcr < 0.8:  # Low PCR suggests bullish sentiment
            direction = "CALL"
            confidence = min(0.8, 1.0 / pcr)
        else:
            direction = "NEUTRAL"
            confidence = 0.5

        # Strategy 2: Gamma exposure analysis
        gamma_signal = "HOLD"
        if gamma_exp > 10000:  # High gamma suggests potential pinning
            gamma_signal = "NEUTRAL"
        elif gamma_exp < -5000:  # Negative gamma suggests trending move
            gamma_signal = direction

        # Strategy 3: IV analysis
        iv_signal = "HOLD"
        if avg_iv > 18:  # High IV suggests buying opportunities
            iv_signal = direction
        elif avg_iv < 12:  # Low IV suggests selling opportunities
            iv_signal = "NEUTRAL"

        # Combined signal
        if direction != "NEUTRAL" and (gamma_signal == direction or iv_signal == direction):
            # Execute trade
            risk_amount = capital * 0.01  # 1% risk per trade
            option_price = spot * 0.008  # Rough option price estimate

            if option_price > 0:
                quantity = max(1, int(risk_amount / option_price))
                capital -= option_price * quantity

                trade = {
                    'timestamp': snapshot['timestamp'],
                    'direction': direction,
                    'entry_price': option_price,
                    'quantity': quantity,
                    'spot_at_entry': spot,
                    'pcr': pcr,
                    'gamma_exposure': gamma_exp,
                    'iv': avg_iv,
                    'strategy': 'PCR_Gamma_IV_Combined',
                    'confidence': confidence
                }

                trades.append(trade)

                if len(trades) % 5 == 0:
                    print(f"  Trade {len(trades)}: {direction} at ₹{option_price:.1f}, PCR={pcr:.2f}, IV={avg_iv:.1f}%")

        # Simulate position management (close after 3-5 snapshots)
        if i >= 3 and trades:
            # Close oldest position
            oldest_trade = trades[0]
            holding_period = i - [j for j, s in enumerate(snapshots) if s['timestamp'] == oldest_trade['timestamp']][0]

            if holding_period >= 3:
                # Simulate exit with realistic P&L
                exit_spot = spot * np.random.normal(1.0, 0.015)  # 1.5% volatility
                price_change = (exit_spot - oldest_trade['spot_at_entry']) / oldest_trade['spot_at_entry']

                # Direction-based P&L
                if oldest_trade['direction'] == "CALL":
                    pnl_multiplier = 1 + price_change * 5  # Calls benefit from upward moves
                else:  # PUT
                    pnl_multiplier = 1 - price_change * 5  # Puts benefit from downward moves

                # Add some noise and time decay
                pnl_multiplier *= np.random.normal(1.0, 0.1)
                pnl_multiplier *= (1 - 0.02 * holding_period / 60)  # Time decay

                exit_price = oldest_trade['entry_price'] * max(0.1, pnl_multiplier)  # Floor at 10% of entry
                pnl = (exit_price - oldest_trade['entry_price']) * oldest_trade['quantity']

                capital += exit_price * oldest_trade['quantity']

                oldest_trade.update({
                    'exit_price': exit_price,
                    'exit_spot': exit_spot,
                    'pnl': pnl,
                    'holding_period': holding_period
                })

                trades.remove(oldest_trade)

    # Close remaining positions at market close
    final_spot = snapshots[-1]['spot_price'] if snapshots else spot
    for trade in trades:
        exit_price = trade['entry_price'] * np.random.normal(1.02, 0.15)
        pnl = (exit_price - trade['entry_price']) * trade['quantity']
        capital += exit_price * trade['quantity']

        trade.update({
            'exit_price': exit_price,
            'exit_spot': final_spot,
            'pnl': pnl,
            'holding_period': 60  # Assume end of day
        })

    return capital, trades

def main():
    try:
        # Load and analyze data
        raw_data = load_option_chain_data("2025-11-19")
        snapshots, strikes_data = analyze_option_chain_data(raw_data)

        if not snapshots:
            print("No option chain data found!")
            return

        print(f"\n✓ Analyzed {len(snapshots)} snapshots with {len(strikes_data)} unique strikes")

        # Show market summary
        spot_prices = [s['spot_price'] for s in snapshots]
        pcrs = [s['pcr'] for s in snapshots if s['pcr']]
        ivs = [s['avg_iv'] for s in snapshots if s['avg_iv']]

        print("\n📊 Market Summary:")
        print(f"   Spot Range: ₹{min(spot_prices):.2f} - ₹{max(spot_prices):.2f}")
        print(f"   PCR Range: {min(pcrs):.2f} - {max(pcrs):.2f}" if pcrs else "   PCR: N/A")
        print(f"   IV Range: {min(ivs):.2f}% - {max(ivs):.2f}%" if ivs else "   IV: N/A")
        print(f"   Total OI Range: {min(s['total_oi'] for s in snapshots):,} - {max(s['total_oi'] for s in snapshots):,}")

        # Run trading simulation
        final_capital, trades = simulate_option_trading(snapshots, strikes_data)

        # Results
        total_pnl = final_capital - 100000.0
        total_return_pct = (total_pnl / 100000.0) * 100

        winning_trades = [t for t in trades if t['pnl'] > 0]
        win_rate = (len(winning_trades) / len(trades)) * 100 if trades else 0

        print("\n" + "="*80)
        print("📊 TRADING RESULTS - Option Chain Analysis")
        print("="*80)

        print("\n💰 Performance:")
        print(f"   Starting Capital: ₹100,000.00")
        print(f"   Final Capital: ₹{final_capital:,.2f}")
        print(f"   Total P&L: ₹{total_pnl:,.2f} ({total_return_pct:+.2f}%)")

        print("\n📈 Trading Statistics:")
        print(f"   Total Trades: {len(trades)}")
        print(f"   Win Rate: {win_rate:.1f}%")
        if winning_trades:
            avg_win = sum(t['pnl'] for t in winning_trades) / len(winning_trades)
            avg_loss = sum(t['pnl'] for t in trades if t['pnl'] <= 0) / len([t for t in trades if t['pnl'] <= 0]) if any(t['pnl'] <= 0 for t in trades) else 0
            print(f"   Average Win: ₹{avg_win:,.2f}")
            print(f"   Average Loss: ₹{avg_loss:,.2f}")
            print(f"   Profit Factor: {abs(sum(t['pnl'] for t in winning_trades) / sum(t['pnl'] for t in trades if t['pnl'] < 0)) if any(t['pnl'] < 0 for t in trades) else float('inf'):.2f}")

        print("
🎯 Strategy Insights:")
        print("   Based on PCR, Gamma Exposure, and IV analysis")
        print("   PCR > 1.2: Bearish bias")
        print("   PCR < 0.8: Bullish bias")
        print("   High Gamma: Potential pinning behavior")
        print("   High IV: Buying opportunities")

        print("
✅ Conclusion:")
        if total_return_pct > 0.5:
            print("   🎉 Option chain analysis shows profitable opportunities!")
        elif total_return_pct > -0.5:
            print("   🤔 Option strategies broke even - requires refinement")
        else:
            print("   😞 Option strategies showed losses - needs strategy review")

        print("="*80)

    except Exception as e:
        print(f"Error in analysis: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
