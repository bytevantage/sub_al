import os
import sys
import json
import asyncio
import logging
from datetime import datetime, timedelta

from backend.strategies.strategy_engine import StrategyEngine
from backend.strategies.high_frequency import ScalpingStrategy, ArbitrageStrategy

sys.path.append("backend")

logger = logging.getLogger(__name__)


def normalize_symbol_snapshot(symbol: str, payload: dict) -> dict:
    if not isinstance(payload, dict):
        return {}

    snapshot = payload.copy()
    option_chain = snapshot.get("option_chain") or {}
    option_chain.setdefault("calls", {})
    option_chain.setdefault("puts", {})

    # Aggregate PCR if available
    total_call_oi = option_chain.get("total_call_oi") or sum(
        leg.get("oi", 0) for leg in option_chain["calls"].values()
    )
    total_put_oi = option_chain.get("total_put_oi") or sum(
        leg.get("oi", 0) for leg in option_chain["puts"].values()
    )
    if total_call_oi:
        option_chain["pcr"] = total_put_oi / total_call_oi

    snapshot["option_chain"] = option_chain
    snapshot.setdefault("spot_price", snapshot.get("ltp"))
    snapshot.setdefault("atm_strike", round(snapshot.get("spot_price", 0), -2) if snapshot.get("spot_price") else 0)
    snapshot.setdefault("multi_timeframe", {})
    snapshot.setdefault("technical_indicators", {})
    snapshot.setdefault("symbol", symbol)
    return snapshot

async def main():
    # Load today's market data
    today = datetime.now()
    yesterday = today - timedelta(days=1)
    target_date = yesterday
    data_file = f"data/historical/{target_date.strftime('%Y-%m-%d')}.json"
    db_file = f"data/historical/{target_date.strftime('%Y-%m-%d')}_db.json"

    if os.path.exists(db_file):
        data_file = db_file
    
    if not os.path.exists(data_file):
        print(f"No market data found for {target_date.strftime('%Y-%m-%d')}")
        return
    
    with open(data_file) as f:
        raw_data = json.load(f)

    # Normalize data into list of market state snapshots
    market_snapshots = []

    # Case 1: bucketed structure {timestamp: {symbol: {...}}}
    if all(isinstance(v, dict) for v in raw_data.values()):
        for timestamp, bucket in sorted(raw_data.items()):
            if not isinstance(bucket, dict):
                continue
            snapshot = {
                symbol: normalize_symbol_snapshot(symbol, data)
                for symbol, data in bucket.items()
                if isinstance(data, dict)
            }
            snapshot = {k: v for k, v in snapshot.items() if v}
            if not snapshot:
                continue
            snapshot["timestamp"] = timestamp
            market_snapshots.append(snapshot)
    else:
        # Legacy single snapshot structure
        normalized = {
            symbol: normalize_symbol_snapshot(symbol, data)
            for symbol, data in raw_data.items()
            if isinstance(data, dict)
        }
        normalized["timestamp"] = raw_data.get("timestamp", "00:00")
        market_snapshots.append(normalized)
    
    # Initialize strategy engine with full strategy roster
    engine = StrategyEngine(model_manager=None, enable_database=False)
    
    # Disable external dependencies
    engine.upstox_client = None
    
    # Simulate signals throughout the day
    portfolio = []
    initial_capital = 100000
    capital = initial_capital
    results = []

    for snapshot in market_snapshots:
        timestamp = snapshot.get("timestamp")
        data_snapshot = {
            symbol: data
            for symbol, data in snapshot.items()
            if symbol not in {"timestamp", "last_update", "is_stale"}
        }

        if not data_snapshot:
            continue

        logger.debug(f"Snapshot {timestamp} symbols: {list(data_snapshot.keys())}")
        signals = await engine.generate_signals(data_snapshot)
        print(f"[Backtest] {timestamp}: Found {len(signals)} signals")
        for signal in signals:
            print(f"  - {signal.reason}")
        
        if "NIFTY" not in data_snapshot:
            logger.debug(f"Skipping {timestamp} - NIFTY data unavailable")
            continue

        for signal in signals:
            # Get ATM price
            atm_price = data_snapshot["NIFTY"].get("spot_price")
            if not atm_price:
                continue
            entry_price = atm_price * 0.01  # Simulate option price as 1% of spot
            quantity = min(25, int(capital * 0.01 / entry_price))
            
            position = {
                'time': timestamp,
                'symbol': "NIFTY",
                'direction': signal.direction,
                'entry': entry_price,
                'quantity': quantity,
                'pattern': signal.reason.split(":")[0],
                'exit': None
            }
            portfolio.append(position)
            capital -= entry_price * quantity
            
        # Check exits after 30 minutes
        for position in portfolio[:]:
            exit_time = (datetime.strptime(timestamp, "%H:%M") + timedelta(minutes=30)).strftime("%H:%M")
            if timestamp >= exit_time:
                exit_price = position['entry'] * 1.15 if "CALL" in position['pattern'] else position['entry'] * 0.85
                pnl = (exit_price - position['entry']) * position['quantity'] * (1 if position['direction']=="CALL" else -1)
                position['exit'] = exit_price
                position['pnl'] = pnl
                capital += position['entry'] * position['quantity'] + pnl
                results.append(position)
                portfolio.remove(position)

    # Print results
    total_pnl = sum(p['pnl'] for p in results)
    win_rate = len([p for p in results if p['pnl'] > 0]) / len(results) * 100

    print(f"\nBacktest Results for {target_date.strftime('%Y-%m-%d')}")
    print(f"Starting Capital: ₹{initial_capital:,.2f}")
    print(f"Final Capital: ₹{capital:,.2f}")
    print(f"Total P&L: ₹{total_pnl:,.2f} ({total_pnl/initial_capital*100:.2f}%)")
    print(f"Win Rate: {win_rate:.1f}%")
    print(f"Trades: {len(results)}")

    # Detailed trade report
    print("\nTrade Details:")
    for trade in results:
        print(f"{trade['time']} {trade['symbol']} {trade['direction']} "
              f"Entry:₹{trade['entry']:.2f} Exit:₹{trade['exit']:.2f} "
              f"P&L:₹{trade['pnl']:+,.2f} ({trade['pattern']})")

if __name__ == "__main__":
    asyncio.run(main())
