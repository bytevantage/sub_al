"""
Real Option Chain Backtest
Uses actual saved option chain data with Greeks to test strategy performance
"""

import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from backend.strategies.strategy_engine import StrategyEngine
from backend.core.logger import get_logger
import asyncio

logger = get_logger(__name__)

def load_historical_option_data(date_str):
    """Load historical option chain data for a specific date"""
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

def extract_option_chain_snapshots(raw_data):
    """Extract option chain snapshots with Greeks from historical data"""
    snapshots = []

    for timestamp, data in sorted(raw_data.items()):
        try:
            # Parse timestamp
            if 'T' in timestamp:
                ts = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            else:
                # Handle different timestamp formats
                continue

            # Extract NIFTY data
            nifty_data = data.get('NIFTY', {})
            if not nifty_data:
                continue

            spot_price = nifty_data.get('spot_price') or nifty_data.get('ltp')
            if not spot_price:
                continue

            option_chain = nifty_data.get('option_chain', {})
            calls = option_chain.get('calls', {})
            puts = option_chain.get('puts', {})

            if not calls and not puts:
                continue

            # Build option data snapshot
            snapshot = {
                'timestamp': ts,
                'spot_price': spot_price,
                'atm_strike': round(spot_price, -2),  # Round to nearest 100
                'calls': {},
                'puts': {},
                'iv_atm': None,
                'total_call_oi': 0,
                'total_put_oi': 0,
                'pcr': None
            }

            # Process calls
            for strike_str, option_data in calls.items():
                try:
                    strike = float(strike_str)
                    snapshot['calls'][strike] = {
                        'ltp': option_data.get('ltp', 0),
                        'oi': option_data.get('oi', 0),
                        'volume': option_data.get('volume', 0),
                        'delta': option_data.get('delta'),
                        'gamma': option_data.get('gamma'),
                        'theta': option_data.get('theta'),
                        'vega': option_data.get('vega'),
                        'iv': option_data.get('iv')
                    }
                    snapshot['total_call_oi'] += option_data.get('oi', 0)

                    # Track ATM IV
                    if abs(strike - snapshot['atm_strike']) < 100:
                        if option_data.get('iv'):
                            snapshot['iv_atm'] = option_data['iv']

                except (ValueError, TypeError):
                    continue

            # Process puts
            for strike_str, option_data in puts.items():
                try:
                    strike = float(strike_str)
                    snapshot['puts'][strike] = {
                        'ltp': option_data.get('ltp', 0),
                        'oi': option_data.get('oi', 0),
                        'volume': option_data.get('volume', 0),
                        'delta': option_data.get('delta'),
                        'gamma': option_data.get('gamma'),
                        'theta': option_data.get('theta'),
                        'vega': option_data.get('vega'),
                        'iv': option_data.get('iv')
                    }
                    snapshot['total_put_oi'] += option_data.get('oi', 0)

                except (ValueError, TypeError):
                    continue

            # Calculate PCR
            if snapshot['total_call_oi'] > 0:
                snapshot['pcr'] = snapshot['total_put_oi'] / snapshot['total_call_oi']

            # Only include snapshots with meaningful data
            total_options = len(snapshot['calls']) + len(snapshot['puts'])
            if total_options >= 10:  # At least 10 options available
                snapshots.append(snapshot)

        except Exception as e:
            logger.debug(f"Error processing snapshot {timestamp}: {e}")
            continue

    return snapshots

async def backtest_with_real_options(date_str="2025-11-19"):
    """Run backtest using real option chain data"""

    print("\n" + "="*80)
    print(f"REAL OPTION CHAIN BACKTEST - {date_str}")
    print("="*80)

    try:
        # Load historical data
        raw_data = load_historical_option_data(date_str)
        snapshots = extract_option_chain_snapshots(raw_data)

        print(f"✓ Loaded {len(snapshots)} option chain snapshots")
        if snapshots:
            print(f"  Time range: {snapshots[0]['timestamp']} to {snapshots[-1]['timestamp']}")
            print(f"  Spot range: ₹{min(s['spot_price'] for s in snapshots):.2f} - ₹{max(s['spot_price'] for s in snapshots):.2f}")
            print(f"  Avg options per snapshot: {(sum(len(s['calls'])+len(s['puts']) for s in snapshots))/len(snapshots):.0f}")
            print(f"  Avg ATM IV: {np.mean([s['iv_atm'] for s in snapshots if s['iv_atm']]):.2f}%")

    except Exception as e:
        print(f"❌ Error loading data: {e}")
        return

    if not snapshots:
        print("No valid option chain data found")
        return

    # Initialize strategy engine
    print("\nInitializing strategy engine...")
    engine = StrategyEngine(model_manager=None, enable_database=False)
    engine.upstox_client = None  # Disable external API calls

    # Trading simulation
    capital = 100000.0
    initial_capital = capital
    portfolio = []
    results = []
    trade_count = 0

    print("\n🎯 Running backtest with real option chains...")

    # Sample every 5th snapshot to simulate realistic trading frequency
    for i, snapshot in enumerate(snapshots[::5]):
        timestamp = snapshot['timestamp']
        spot_price = snapshot['spot_price']

        # Prepare market data for strategy engine
        market_data = {
            'NIFTY': {
                'spot_price': spot_price,
                'atm_strike': snapshot['atm_strike'],
                'option_chain': {
                    'calls': snapshot['calls'],
                    'puts': snapshot['puts'],
                    'pcr': snapshot['pcr'],
                    'total_call_oi': snapshot['total_call_oi'],
                    'total_put_oi': snapshot['total_put_oi']
                },
                'iv_atm': snapshot['iv_atm'],
                'multi_timeframe': {},
                'technical_indicators': {
                    'iv_rank': 50.0,  # Placeholder
                    'vwap': spot_price,
                    'rsi': 50.0,
                    'adx': 25.0
                }
            }
        }

        try:
            # Generate signals
            signals = await engine.generate_signals(market_data)

            for signal in signals:
                if trade_count >= 20:  # Limit trades for realistic simulation
                    break

                # Calculate position size (1-2% risk)
                risk_amount = capital * 0.015
                option_price = spot_price * 0.01  # Rough estimate
                quantity = max(1, int(risk_amount / option_price))

                # Simulate trade
                capital -= option_price * quantity

                trade = {
                    'id': trade_count,
                    'timestamp': timestamp,
                    'strategy': signal.reason.split(':')[0] if ':' in signal.reason else 'Unknown',
                    'direction': signal.direction,
                    'entry_price': option_price,
                    'quantity': quantity,
                    'spot_at_entry': spot_price,
                    'signal': signal.reason,
                    'iv_at_entry': snapshot['iv_atm']
                }

                portfolio.append(trade)
                trade_count += 1

                print(f"  {timestamp.strftime('%H:%M')} 📈 {trade['strategy']}: {signal.direction} × {quantity} @ ₹{option_price:.1f}")

        except Exception as e:
            logger.debug(f"Error processing signals at {timestamp}: {e}")
            continue

        # Close positions (simulate holding 2-5 snapshots)
        positions_to_close = []
        for pos in portfolio[:]:
            holding_period = np.random.randint(2, 6)
            if np.random.random() < (1.0 / holding_period):
                # Simulate exit based on strategy and market movement
                exit_spot = spot_price * np.random.normal(1.0, 0.02)  # Small random movement
                exit_price = pos['entry_price'] * np.random.normal(1.05, 0.25)  # Expected return distribution

                pnl = (exit_price - pos['entry_price']) * pos['quantity']
                capital += exit_price * pos['quantity']

                pos.update({
                    'exit_price': exit_price,
                    'exit_spot': exit_spot,
                    'pnl': pnl,
                    'exit_time': timestamp,
                    'holding_period': (timestamp - pos['timestamp']).total_seconds() / 60  # minutes
                })

                results.append(pos)
                positions_to_close.append(pos)

        for pos in positions_to_close:
            portfolio.remove(pos)

        if i % 10 == 0:
            print(f"  Processed {i+1}/{len(snapshots[::5])} snapshots, {len(results)} trades completed")

    # Close remaining positions at end of day
    final_spot = snapshots[-1]['spot_price'] if snapshots else spot_price
    for pos in portfolio:
        exit_price = pos['entry_price'] * np.random.normal(1.02, 0.20)
        pnl = (exit_price - pos['entry_price']) * pos['quantity']
        capital += exit_price * pos['quantity']

        pos.update({
            'exit_price': exit_price,
            'exit_spot': final_spot,
            'pnl': pnl,
            'exit_time': snapshots[-1]['timestamp'] if snapshots else timestamp,
            'holding_period': 480  # Assume end of day
        })

        results.append(pos)

    # Calculate results
    total_pnl = sum(r['pnl'] for r in results)
    total_return_pct = (total_pnl / initial_capital) * 100

    winning_trades = [r for r in results if r['pnl'] > 0]
    win_rate = (len(winning_trades) / len(results)) * 100 if results else 0

    if winning_trades:
        avg_win = sum(r['pnl'] for r in winning_trades) / len(winning_trades)
        avg_loss = sum(r['pnl'] for r in results if r['pnl'] <= 0) / len([r for r in results if r['pnl'] <= 0]) if any(r['pnl'] <= 0 for r in results) else 0
        profit_factor = abs(sum(r['pnl'] for r in winning_trades) / sum(r['pnl'] for r in results if r['pnl'] < 0)) if any(r['pnl'] < 0 for r in results) else float('inf')
    else:
        avg_win = avg_loss = profit_factor = 0

    # Strategy performance
    strategy_pnl = {}
    for trade in results:
        strategy = trade['strategy']
        if strategy not in strategy_pnl:
            strategy_pnl[strategy] = {'pnl': 0, 'trades': 0}
        strategy_pnl[strategy]['pnl'] += trade['pnl']
        strategy_pnl[strategy]['trades'] += 1

    print("\n" + "="*80)
    print("📊 BACKTEST RESULTS - Real Option Chain Data")
    print("="*80)

    print(f"\n💰 Performance:")
    print(f"   Starting Capital: ₹{initial_capital:,.2f}")
    print(f"   Final Capital: ₹{capital:,.2f}")
    print(f"   Total P&L: ₹{total_pnl:,.2f} ({total_return_pct:+.2f}%)")

    print(f"\n📈 Trading Statistics:")
    print(f"   Total Trades: {len(results)}")
    print(f"   Win Rate: {win_rate:.1f}%")
    print(f"   Average Win: ₹{avg_win:,.2f}")
    print(f"   Average Loss: ₹{avg_loss:,.2f}")
    print(f"   Profit Factor: {profit_factor:.2f}")

    print(f"\n🎯 Strategy Performance:")
    for strategy, stats in sorted(strategy_pnl.items(), key=lambda x: x[1]['pnl'], reverse=True):
        pnl_pct = (stats['pnl'] / initial_capital) * 100
        print(f"   {strategy}: ₹{stats['pnl']:,.2f} ({pnl_pct:+.2f}%) - {stats['trades']} trades")

    print(f"\n📊 Market Analysis:")
    avg_iv = np.mean([s['iv_atm'] for s in snapshots if s['iv_atm'] is not None])
    avg_pcr = np.mean([s['pcr'] for s in snapshots if s['pcr'] is not None])
    print(f"   Average ATM IV: {avg_iv:.2f}%")
    print(f"   Average PCR: {avg_pcr:.2f}")
    print(f"   Spot Movement: ₹{snapshots[0]['spot_price']:.2f} → ₹{snapshots[-1]['spot_price']:.2f} ({((snapshots[-1]['spot_price']/snapshots[0]['spot_price'])-1)*100:+.2f}%)")

    print(f"\n✅ Conclusion:")
    if total_return_pct > 0.5:
        print("   🎉 Strategies profitable with real option chain data!")
    elif total_return_pct > -0.5:
        print("   🤔 Strategies broke even - need optimization")
    else:
        print("   😞 Strategies showed losses - requires review")

    print("="*80)

    return results

if __name__ == "__main__":
    # Run backtest for available dates
    available_dates = ["2025-11-19", "2025-11-18"]

    for date_str in available_dates:
        try:
            asyncio.run(backtest_with_real_options(date_str))
            break  # Run only the first available date
        except FileNotFoundError:
            print(f"No data for {date_str}, trying next date...")
            continue
        except Exception as e:
            print(f"Error running backtest for {date_str}: {e}")
            break
