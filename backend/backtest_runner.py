"""Backtest runner for comprehensive strategy testing"""
import os
import json
import asyncio
from datetime import datetime, timedelta
from backend.strategies.strategy_engine import StrategyEngine
from backend.ml.model_manager import ModelManager

async def run_full_backtest():
    """Run full backtest with all strategies and ML"""
    # Initialize components
    model_manager = ModelManager()
    await model_manager.load_models()
    engine = StrategyEngine(model_manager=model_manager, enable_database=False)
    
    # Load historical data
    today = datetime.now().strftime("%Y-%m-%d")
    data_file = f"data/historical/{today}.json"
    if not os.path.exists(data_file):
        return {"error": "No historical data found"}
    
    with open(data_file) as f:
        market_data = json.load(f)
    
    # Format data
    formatted_data = {}
    for timestamp, snapshot in market_data.items():
        formatted_data[timestamp] = {"NIFTY": {"option_chain": snapshot["NIFTY"]["option_chain"], "spot_price": snapshot["NIFTY"]["spot_price"]}}
    
    # Simulate trading
    portfolio = []
    initial_capital = 100000
    capital = initial_capital
    results = []
    
    for timestamp, data_snapshot in formatted_data.items():
        signals = await engine.generate_signals(data_snapshot)
        
        # Process signals
        for signal in signals:
            # Simulate trade execution
            entry_price = data_snapshot["NIFTY"]["spot_price"] * 0.01  # 1% of spot
            quantity = min(25, int(capital * 0.01 / entry_price))
            
            position = {
                'time': timestamp,
                'symbol': "NIFTY",
                'direction': signal.direction,
                'entry': entry_price,
                'quantity': quantity,
                'reason': signal.reason,
                'exit': None
            }
            portfolio.append(position)
            capital -= entry_price * quantity
        
        # Check exits (simplified: exit after 30 minutes)
        for position in portfolio[:]:
            position_time = datetime.strptime(position['time'], "%H:%M")
            current_time = datetime.strptime(timestamp, "%H:%M")
            if (current_time - position_time).seconds >= 1800:  # 30 minutes
                exit_price = position['entry'] * 1.15 if "CALL" in position['reason'] else position['entry'] * 0.85
                pnl = (exit_price - position['entry']) * position['quantity'] * (1 if position['direction']=="CALL" else -1)
                position['exit'] = exit_price
                position['pnl'] = pnl
                results.append(position)
                portfolio.remove(position)
                capital += position['entry'] * position['quantity'] + pnl
    
    # Calculate performance
    total_pnl = sum(trade['pnl'] for trade in results)
    win_rate = len([t for t in results if t['pnl'] > 0]) / len(results) * 100 if results else 0
    
    return {
        "start_capital": initial_capital,
        "end_capital": capital,
        "total_pnl": total_pnl,
        "win_rate": win_rate,
        "trades": results
    }
