#!/usr/bin/env python3
"""
Backtester for Options Trading Strategies
Tests strategies against historical option chain data with Greeks
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from pathlib import Path

from backend.database.db import session_scope
from backend.database.models import Trade, OptionChainSnapshot
from backend.strategies.strategy_engine import StrategyEngine
from backend.ml.model_manager import ModelManager
from backend.core.logger import logger


@dataclass
class BacktestResult:
    """Result of a backtest run"""
    timestamp: datetime
    strategy_id: str
    symbol: str
    direction: str
    strike: float
    entry_price: float
    confidence: float
    potential_pnl: float
    actual_trade_taken: bool
    market_conditions: Dict[str, Any]


class OptionChainBacktester:
    """Backtests trading strategies against historical option chain data"""

    def __init__(self):
        self.strategy_engine = None
        self.model_manager = None

    async def initialize(self):
        """Initialize strategy engine and ML models"""
        logger.info("Initializing backtester...")

        try:
            self.model_manager = ModelManager()
            await self.model_manager.load_models()

            self.strategy_engine = StrategyEngine(self.model_manager)

            logger.info("✓ Backtester initialized")

        except Exception as e:
            logger.error(f"Failed to initialize backtester: {e}")
            raise

    def load_option_chain_snapshot(self, symbol: str, timestamp: datetime) -> Optional[Dict]:
        """
        Load option chain snapshot for a specific timestamp
        Uses closest available data within time window

        Args:
            symbol: NIFTY, BANKNIFTY
            timestamp: Target timestamp to find closest data for

        Returns:
            Market state dict with option chain
        """
        try:
            with session_scope() as session:
                # Find snapshots within 10 minutes of the timestamp
                time_window = timedelta(minutes=10)
                start_time = timestamp - time_window
                end_time = timestamp + time_window

                snapshots = session.query(OptionChainSnapshot).filter(
                    OptionChainSnapshot.symbol == symbol,
                    OptionChainSnapshot.timestamp >= start_time,
                    OptionChainSnapshot.timestamp <= end_time
                ).order_by(OptionChainSnapshot.timestamp).all()

                if not snapshots:
                    logger.debug(f"No option chain data for {symbol} around {timestamp}")
                    return None

                # Use the snapshot closest to our target time
                closest_snapshot = min(snapshots, key=lambda s: abs((s.timestamp - timestamp).total_seconds()))

                # Group by timestamp (use data from the closest timestamp)
                target_timestamp = closest_snapshot.timestamp

                relevant_snapshots = [s for s in snapshots if s.timestamp == target_timestamp]

                logger.debug(f"Using option chain data from {target_timestamp} ({len(relevant_snapshots)} strikes)")

                # Build option chain
                calls = {}
                puts = {}

                for snap in relevant_snapshots:
                    strike_key = str(snap.strike_price)

                    if snap.option_type == 'CALL':
                        calls[strike_key] = {
                            'ltp': snap.ltp,
                            'bid': snap.bid,
                            'ask': snap.ask,
                            'volume': snap.volume,
                            'oi': snap.oi,
                            'oi_change': snap.oi_change,
                            'delta': snap.delta,
                            'gamma': snap.gamma,
                            'theta': snap.theta,
                            'vega': snap.vega,
                            'iv': snap.iv,
                            'expiry_date': snap.expiry.isoformat() if snap.expiry else None
                        }
                    elif snap.option_type == 'PUT':
                        puts[strike_key] = {
                            'ltp': snap.ltp,
                            'bid': snap.bid,
                            'ask': snap.ask,
                            'volume': snap.volume,
                            'oi': snap.oi,
                            'oi_change': snap.oi_change,
                            'delta': snap.delta,
                            'gamma': snap.gamma,
                            'theta': snap.theta,
                            'vega': snap.vega,
                            'iv': snap.iv,
                            'expiry_date': snap.expiry.isoformat() if snap.expiry else None
                        }

                # Calculate PCR and other metrics
                total_call_oi = sum(c.get('oi', 0) for c in calls.values())
                total_put_oi = sum(p.get('oi', 0) for p in puts.values())

                pcr = total_put_oi / total_call_oi if total_call_oi > 0 else 0

                # Get spot price (use the first snapshot's spot price)
                spot_price = relevant_snapshots[0].spot_price if relevant_snapshots else 0

                # Build market state
                market_state = {
                    symbol: {
                        'spot_price': spot_price,
                        'atm_strike': round(spot_price / 100) * 100,  # Round to nearest 100
                        'expiry': relevant_snapshots[0].expiry.isoformat() if relevant_snapshots else None,
                        'option_chain': {
                            'calls': calls,
                            'puts': puts,
                            'pcr': pcr,
                            'total_call_oi': total_call_oi,
                            'total_put_oi': total_put_oi,
                            'max_pain': self._calculate_max_pain_simple(calls, puts)
                        },
                        'technical_indicators': {},  # Would need historical OHLCV data
                        'timestamp': target_timestamp.isoformat()
                    },
                    'timestamp': target_timestamp.isoformat(),
                    'last_update': target_timestamp
                }

                return market_state

        except Exception as e:
            logger.error(f"Error loading option chain snapshot: {e}")
            return None

    def _calculate_max_pain_simple(self, calls: Dict, puts: Dict) -> float:
        """Simple max pain calculation"""
        try:
            strikes = set(calls.keys()) | set(puts.keys())
            min_pain = float('inf')
            max_pain_strike = 0

            for strike_str in strikes:
                strike = float(strike_str)
                pain = 0

                # Calls below strike expire worthless
                for call_strike_str, call_data in calls.items():
                    call_strike = float(call_strike_str)
                    if call_strike < strike:
                        pain += call_data.get('oi', 0)

                # Puts above strike expire worthless
                for put_strike_str, put_data in puts.items():
                    put_strike = float(put_strike_str)
                    if put_strike > strike:
                        pain += put_data.get('oi', 0)

                if pain < min_pain:
                    min_pain = pain
                    max_pain_strike = strike

            return max_pain_strike

        except Exception as e:
            logger.error(f"Error calculating max pain: {e}")
            return 0

    async def backtest_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        symbol: str = 'NIFTY',
        interval_minutes: int = 30
    ) -> List[BacktestResult]:
        """
        Backtest strategies against historical data for a date range
        Samples at regular intervals instead of matching specific trades

        Args:
            start_date: Start date for backtesting
            end_date: End date for backtesting
            symbol: Symbol to backtest (NIFTY, BANKNIFTY)
            interval_minutes: Minutes between samples

        Returns:
            List of backtest results
        """
        logger.info(f"Starting backtest for {symbol} from {start_date.date()} to {end_date.date()} (every {interval_minutes}min)")

        results = []

        # Get all trades for the period to compare
        actual_trades = self._get_actual_trades(start_date, end_date, symbol)
        actual_trades_map = {
            (t.entry_time.replace(second=0, microsecond=0), t.symbol, t.instrument_type, t.strike_price): t
            for t in actual_trades
        }

        current_date = start_date
        while current_date <= end_date:
            logger.info(f"Backtesting {current_date.date()}...")

            # Sample at regular intervals during market hours
            market_open = current_date.replace(hour=9, minute=15)
            market_close = current_date.replace(hour=15, minute=30)

            sample_time = market_open
            while sample_time <= market_close:
                market_state = self.load_option_chain_snapshot(symbol, sample_time)

                if market_state:
                    try:
                        # Generate signals
                        signals = await self.strategy_engine.generate_signals(market_state)

                        # Score signals with ML
                        scored_signals = await self.model_manager.score_signals(signals, market_state)

                        # Process each signal
                        for signal in scored_signals:
                            # Normalize Signal objects to dictionaries for downstream processing
                            if hasattr(signal, "to_dict"):
                                signal_dict = signal.to_dict()
                                # Carry over ML fields injected during scoring
                                signal_dict['ml_probability'] = getattr(signal, 'ml_probability', signal_dict.get('ml_probability', 0))
                                signal_dict['ml_confidence'] = getattr(signal, 'ml_confidence', signal_dict.get('ml_confidence', 0))
                                signal_dict['strategy_id'] = getattr(signal, 'strategy_id', signal_dict.get('strategy_id', 'unknown'))
                                signal_dict['entry_price'] = getattr(signal, 'entry_price', signal_dict.get('entry_price', 0))
                                signal_dict['iv'] = getattr(signal, 'iv', signal_dict.get('iv', 0))
                                signal_dict['oi'] = getattr(signal, 'oi', signal_dict.get('oi', 0))
                            elif isinstance(signal, dict):
                                signal_dict = signal
                            else:
                                logger.debug("Skipping unsupported signal type during backtest: %s", type(signal))
                                continue

                            # Check if this signal was actually traded (within 5 minutes)
                            signal_time_key = sample_time.replace(second=0, microsecond=0)
                            signal_key = (
                                signal_time_key,
                                signal_dict['symbol'],
                                signal_dict['direction'],
                                signal_dict['strike']
                            )

                            # Check for trades within a 10-minute window
                            actual_trade = None
                            for trade_key, trade in actual_trades_map.items():
                                if (trade_key[1] == signal_dict['symbol'] and
                                    trade_key[2] == signal_dict['direction'] and
                                    trade_key[3] == signal_dict['strike'] and
                                    abs((trade.entry_time - sample_time).total_seconds()) <= 600):  # 10 minutes
                                    actual_trade = trade
                                    break

                            # Calculate potential P&L if we had taken this trade
                            potential_pnl = self._calculate_potential_pnl(signal_dict, market_state)

                            result = BacktestResult(
                                timestamp=sample_time,
                                strategy_id=signal_dict.get('strategy_id', 'unknown'),
                                symbol=signal_dict['symbol'],
                                direction=signal_dict['direction'],
                                strike=signal_dict['strike'],
                                entry_price=signal_dict['entry_price'],
                                confidence=signal_dict.get('ml_confidence', 0),
                                potential_pnl=potential_pnl,
                                actual_trade_taken=actual_trade is not None,
                                market_conditions={
                                    'spot_price': market_state.get(symbol, {}).get('spot_price', 0),
                                    'pcr': market_state.get(symbol, {}).get('option_chain', {}).get('pcr', 0),
                                    'iv': signal_dict.get('iv', 0),
                                    'oi': signal_dict.get('oi', 0)
                                }
                            )

                            results.append(result)

                    except Exception as e:
                        logger.warning(f"Error processing sample at {sample_time}: {e}")

                # Move to next sample
                sample_time += timedelta(minutes=interval_minutes)

            current_date += timedelta(days=1)

        logger.info(f"Backtest completed: {len(results)} signals analyzed")
        return results

    def _get_actual_trades(self, start_date: datetime, end_date: datetime, symbol: str) -> List[Trade]:
        """Get actual trades for comparison"""
        try:
            with session_scope() as session:
                trades = session.query(Trade).filter(
                    Trade.symbol == symbol,
                    Trade.entry_time >= start_date,
                    Trade.entry_time <= end_date
                ).all()
                return trades
        except Exception as e:
            logger.error(f"Error loading actual trades: {e}")
            return []

    def _calculate_potential_pnl(self, signal: Dict, market_state: Dict) -> float:
        """
        Calculate potential P&L for a signal based on market movement

        This is a simplified calculation - in reality would need price series
        """
        try:
            # For now, use a simple estimation based on Greeks and market conditions
            # In a real backtest, we'd simulate price movement

            direction = signal['direction']
            delta = signal.get('delta', 0)
            gamma = signal.get('gamma', 0)
            theta = signal.get('theta', 0)

            # Simplified: assume average daily move of 1%
            spot_move_pct = 0.01  # 1% move

            # Estimate option price change using delta approximation
            if direction == 'CALL':
                price_change = delta * spot_move_pct * signal['entry_price']
            else:  # PUT
                price_change = -delta * spot_move_pct * signal['entry_price']

            # Add some randomness and risk adjustment
            potential_pnl = price_change * 100  # Assume lot size of 100

            return potential_pnl

        except Exception as e:
            logger.error(f"Error calculating potential P&L: {e}")
            return 0


async def main():
    """Main backtest function"""
    import argparse

    parser = argparse.ArgumentParser(description='Backtest Options Trading Strategies')
    parser.add_argument('--symbol', default='NIFTY', help='Symbol to backtest')
    parser.add_argument('--start-date', required=True, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', required=True, help='End date (YYYY-MM-DD)')
    parser.add_argument('--output', default='backtest_results.json', help='Output file')

    args = parser.parse_args()

    # Initialize backtester
    backtester = OptionChainBacktester()
    await backtester.initialize()

    # Parse dates
    start_date = datetime.strptime(args.start_date, '%Y-%m-%d')
    end_date = datetime.strptime(args.end_date, '%Y-%m-%d')

    # Run backtest
    results = await backtester.backtest_date_range(start_date, end_date, args.symbol)

    # Analyze results
    print(f"\n📊 BACKTEST RESULTS for {args.symbol}")
    print("=" * 60)

    total_signals = len(results)
    profitable_signals = sum(1 for r in results if r.potential_pnl > 0)
    actual_trades_taken = sum(1 for r in results if r.actual_trade_taken)

    print(f"Total signals generated: {total_signals}")
    profitable_signals = sum(1 for r in results if r.potential_pnl > 0)
    print(f"Potentially profitable signals: {profitable_signals} ({profitable_signals/max(total_signals,1)*100:.1f}%)")
    actual_trades_taken = sum(1 for r in results if r.actual_trade_taken)
    print(f"Signals actually traded: {actual_trades_taken} ({actual_trades_taken/max(total_signals,1)*100:.1f}%)")

    # Find missed opportunities
    missed_profitable = [r for r in results if r.potential_pnl > 0 and not r.actual_trade_taken]

    print(f"Missed profitable opportunities: {len(missed_profitable)}")

    if missed_profitable:
        print("\n🎯 TOP MISSED OPPORTUNITIES:")
        # Sort by potential P&L
        missed_profitable.sort(key=lambda x: x.potential_pnl, reverse=True)

        for i, result in enumerate(missed_profitable[:10]):  # Top 10
            print(f"{i+1}. {result.timestamp.strftime('%m-%d %H:%M')} | {result.symbol} {result.direction} {result.strike} | "
                  f"Strategy: {result.strategy_id} | Confidence: {result.confidence:.2f} | "
                  f"Potential P&L: ₹{result.potential_pnl:.2f}")

    # Save detailed results
    import json
    results_dict = [
        {
            'timestamp': r.timestamp.isoformat(),
            'strategy_id': r.strategy_id,
            'symbol': r.symbol,
            'direction': r.direction,
            'strike': r.strike,
            'entry_price': r.entry_price,
            'confidence': r.confidence,
            'potential_pnl': r.potential_pnl,
            'actual_trade_taken': r.actual_trade_taken,
            'market_conditions': r.market_conditions
        }
        for r in results
    ]

    with open(args.output, 'w') as f:
        json.dump(results_dict, f, indent=2, default=str)

    print(f"\n✓ Detailed results saved to {args.output}")


if __name__ == '__main__':
    asyncio.run(main())
