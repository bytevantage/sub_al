"""
Backtest Regression Test Suite

Validates that strategy signal generation remains consistent across code changes.
Compares current signal outputs against baseline snapshots to detect regressions.

Features:
- Historical data replay from database or JSON snapshots
- Strategy signal validation (structure, values, logic)
- Regression detection with detailed diff reporting
- Baseline management (create, update, compare)
- Per-strategy and aggregate metrics

Usage:
    # Run all regression tests
    python tests/backtest_regression.py --mode test
    
    # Create new baseline
    python tests/backtest_regression.py --mode baseline
    
    # Run specific strategy
    python tests/backtest_regression.py --mode test --strategy pcr_analysis
    
    # Use custom date range
    python tests/backtest_regression.py --mode test --start 2024-01-01 --end 2024-01-31
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
import hashlib

# Project imports
import sys
sys.path.append(str(Path(__file__).parent.parent))

from backend.strategies.strategy_engine import StrategyEngine
from backend.ml.model_manager import ModelManager
from backend.data.market_data import MarketDataManager
from backend.config import config
from backend.database.db import Trade, session_scope

logger = logging.getLogger(__name__)


@dataclass
class SignalSnapshot:
    """Snapshot of a signal for regression testing"""
    timestamp: str
    strategy_id: str
    symbol: str
    side: str  # BUY or SELL
    confidence: float
    entry_price: float
    stop_loss: Optional[float]
    take_profit: Optional[float]
    quantity: int
    reason: str
    # Additional metadata
    market_conditions: Dict[str, Any]
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    def get_hash(self) -> str:
        """Generate hash for signal comparison (excludes confidence for fuzzy matching)"""
        key_fields = f"{self.timestamp}_{self.strategy_id}_{self.symbol}_{self.side}_{self.entry_price}"
        return hashlib.md5(key_fields.encode()).hexdigest()


@dataclass
class RegressionResult:
    """Result of regression test"""
    strategy_id: str
    passed: bool
    total_signals_baseline: int
    total_signals_current: int
    matched_signals: int
    missing_signals: List[SignalSnapshot]  # In baseline, not in current
    extra_signals: List[SignalSnapshot]  # In current, not in baseline
    confidence_diffs: List[Tuple[str, float, float]]  # (signal_hash, baseline_conf, current_conf)
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            'strategy_id': self.strategy_id,
            'passed': self.passed,
            'total_signals_baseline': self.total_signals_baseline,
            'total_signals_current': self.total_signals_current,
            'matched_signals': self.matched_signals,
            'missing_signals': [s.to_dict() for s in self.missing_signals],
            'extra_signals': [s.to_dict() for s in self.extra_signals],
            'confidence_diffs': [{'hash': h, 'baseline': b, 'current': c} for h, b, c in self.confidence_diffs],
            'error_message': self.error_message
        }


class HistoricalDataLoader:
    """Loads historical market data for backtesting"""
    
    def __init__(self, data_source: str = 'database'):
        """
        Args:
            data_source: 'database' to load from Trade table, 'json' to load from snapshot files
        """
        self.data_source = data_source
        self.snapshot_dir = Path(__file__).parent / 'baseline_data'
        self.snapshot_dir.mkdir(exist_ok=True)
    
    async def load_market_states(self, start_date: datetime, end_date: datetime) -> List[Dict]:
        """
        Load historical market states for the given date range.
        
        Returns:
            List of market_state dictionaries (same format as MarketDataManager.get_current_state())
        """
        if self.data_source == 'database':
            return await self._load_from_database(start_date, end_date)
        else:
            return await self._load_from_json(start_date, end_date)
    
    async def _load_from_database(self, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Load historical data from Trade table (reconstructs market states from trades)"""
        market_states = []
        
        try:
            with session_scope() as session:
                # Query all trades in date range
                trades = session.query(Trade).filter(
                    Trade.entry_time >= start_date,
                    Trade.entry_time <= end_date
                ).order_by(Trade.entry_time).all()
                
                logger.info(f"Loaded {len(trades)} trades from database ({start_date} to {end_date})")
                
                # Group trades by timestamp (approximate to nearest minute)
                from collections import defaultdict
                trades_by_time = defaultdict(list)
                for trade in trades:
                    timestamp_key = trade.entry_time.replace(second=0, microsecond=0)
                    trades_by_time[timestamp_key].append(trade)
                
                # Reconstruct market states from trades
                for timestamp, trades_at_time in sorted(trades_by_time.items()):
                    # Build minimal market_state for testing
                    # In production, this would come from option chain data
                    market_state = {
                        'timestamp': timestamp.isoformat(),
                        'symbol': 'NIFTY',  # Assume NIFTY for now
                        'spot_price': trades_at_time[0].entry_price if trades_at_time else 0,
                        'option_chain': {},  # Would need to reconstruct from historical data
                        'technical_indicators': {},
                        'total_call_oi': 0,
                        'total_put_oi': 0,
                        'total_oi': 0,
                    }
                    market_states.append(market_state)
                
        except Exception as e:
            logger.error(f"Failed to load data from database: {e}")
            raise
        
        return market_states
    
    async def _load_from_json(self, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Load historical data from JSON snapshot files"""
        market_states = []
        
        # Iterate through snapshot files in date range
        current_date = start_date.date()
        end = end_date.date()
        
        while current_date <= end:
            snapshot_file = self.snapshot_dir / f"market_state_{current_date.isoformat()}.json"
            
            if snapshot_file.exists():
                try:
                    with open(snapshot_file, 'r') as f:
                        daily_states = json.load(f)
                        market_states.extend(daily_states)
                        logger.info(f"Loaded {len(daily_states)} market states from {snapshot_file}")
                except Exception as e:
                    logger.warning(f"Failed to load {snapshot_file}: {e}")
            
            current_date += timedelta(days=1)
        
        return market_states
    
    async def save_snapshot(self, date: datetime, market_states: List[Dict]):
        """Save market states to JSON snapshot for future testing"""
        snapshot_file = self.snapshot_dir / f"market_state_{date.date().isoformat()}.json"
        
        try:
            with open(snapshot_file, 'w') as f:
                json.dump(market_states, f, indent=2, default=str)
            logger.info(f"Saved {len(market_states)} market states to {snapshot_file}")
        except Exception as e:
            logger.error(f"Failed to save snapshot: {e}")


class BaselineManager:
    """Manages baseline signal snapshots for regression testing"""
    
    def __init__(self):
        self.baseline_dir = Path(__file__).parent / 'baselines'
        self.baseline_dir.mkdir(exist_ok=True)
    
    def save_baseline(self, strategy_id: str, signals: List[SignalSnapshot], date_range: str):
        """Save baseline signals for a strategy"""
        baseline_file = self.baseline_dir / f"{strategy_id}_{date_range}.json"
        
        try:
            baseline_data = {
                'strategy_id': strategy_id,
                'date_range': date_range,
                'created_at': datetime.now().isoformat(),
                'total_signals': len(signals),
                'signals': [s.to_dict() for s in signals]
            }
            
            with open(baseline_file, 'w') as f:
                json.dump(baseline_data, f, indent=2, default=str)
            
            logger.info(f"✓ Saved baseline for {strategy_id}: {len(signals)} signals")
            
        except Exception as e:
            logger.error(f"Failed to save baseline: {e}")
            raise
    
    def load_baseline(self, strategy_id: str, date_range: str) -> List[SignalSnapshot]:
        """Load baseline signals for a strategy"""
        baseline_file = self.baseline_dir / f"{strategy_id}_{date_range}.json"
        
        if not baseline_file.exists():
            raise FileNotFoundError(f"No baseline found for {strategy_id} ({date_range})")
        
        try:
            with open(baseline_file, 'r') as f:
                baseline_data = json.load(f)
            
            signals = [SignalSnapshot(**s) for s in baseline_data['signals']]
            logger.info(f"Loaded baseline for {strategy_id}: {len(signals)} signals")
            return signals
            
        except Exception as e:
            logger.error(f"Failed to load baseline: {e}")
            raise
    
    def list_baselines(self) -> List[str]:
        """List all available baselines"""
        return [f.stem for f in self.baseline_dir.glob('*.json')]


class RegressionTester:
    """Runs regression tests comparing current signals to baseline"""
    
    def __init__(self, confidence_tolerance: float = 0.05):
        """
        Args:
            confidence_tolerance: Acceptable difference in confidence scores (0.05 = 5%)
        """
        self.confidence_tolerance = confidence_tolerance
        self.data_loader = HistoricalDataLoader()
        self.baseline_manager = BaselineManager()
        self.model_manager = None
        self.strategy_engine = None
    
    async def initialize(self):
        """Initialize ML models and strategy engine"""
        logger.info("Initializing components for regression testing...")
        
        try:
            self.model_manager = ModelManager()
            await self.model_manager.load_models()
            
            self.strategy_engine = StrategyEngine(self.model_manager)
            
            logger.info("✓ Components initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize: {e}")
            raise
    
    async def create_baseline(
        self, 
        start_date: datetime, 
        end_date: datetime,
        strategy_id: Optional[str] = None
    ):
        """
        Create baseline snapshots by running strategies on historical data.
        
        Args:
            start_date: Start of date range
            end_date: End of date range
            strategy_id: Specific strategy to baseline (None = all strategies)
        """
        logger.info("=" * 60)
        logger.info(f"Creating Baseline: {start_date.date()} to {end_date.date()}")
        logger.info("=" * 60)
        
        # Load historical market data
        market_states = await self.data_loader.load_market_states(start_date, end_date)
        
        if not market_states:
            logger.error("No historical data available for baseline creation")
            return
        
        # Run strategies on historical data
        all_signals_by_strategy = {}
        
        for i, market_state in enumerate(market_states):
            if i % 10 == 0:
                logger.info(f"Processing market state {i+1}/{len(market_states)}...")
            
            try:
                # Generate signals
                signals = await self.strategy_engine.generate_signals(market_state)
                
                # Score signals with ML
                scored_signals = await self.model_manager.score_signals(signals, market_state)
                
                # Group by strategy
                for signal in scored_signals:
                    strat_id = signal.get('strategy_id', 'unknown')
                    
                    # Filter by strategy if specified
                    if strategy_id and strat_id != strategy_id:
                        continue
                    
                    snapshot = SignalSnapshot(
                        timestamp=market_state['timestamp'],
                        strategy_id=strat_id,
                        symbol=signal['symbol'],
                        side=signal['side'],
                        confidence=signal.get('ml_confidence', 0.5),
                        entry_price=signal['entry_price'],
                        stop_loss=signal.get('stop_loss'),
                        take_profit=signal.get('take_profit'),
                        quantity=signal.get('quantity', 0),
                        reason=signal.get('reason', ''),
                        market_conditions={
                            'spot_price': market_state.get('spot_price', 0),
                            'total_oi': market_state.get('total_oi', 0),
                        }
                    )
                    
                    if strat_id not in all_signals_by_strategy:
                        all_signals_by_strategy[strat_id] = []
                    
                    all_signals_by_strategy[strat_id].append(snapshot)
            
            except Exception as e:
                logger.warning(f"Error processing market state: {e}")
                continue
        
        # Save baselines
        date_range = f"{start_date.date().isoformat()}_to_{end_date.date().isoformat()}"
        
        for strat_id, signals in all_signals_by_strategy.items():
            self.baseline_manager.save_baseline(strat_id, signals, date_range)
        
        logger.info("=" * 60)
        logger.info(f"✓ Baseline created for {len(all_signals_by_strategy)} strategies")
        logger.info("=" * 60)
    
    async def run_regression_tests(
        self,
        start_date: datetime,
        end_date: datetime,
        strategy_id: Optional[str] = None
    ) -> Dict[str, RegressionResult]:
        """
        Run regression tests comparing current signals to baseline.
        
        Args:
            start_date: Start of date range
            end_date: End of date range
            strategy_id: Specific strategy to test (None = all strategies)
        
        Returns:
            Dict mapping strategy_id to RegressionResult
        """
        logger.info("=" * 60)
        logger.info(f"Running Regression Tests: {start_date.date()} to {end_date.date()}")
        logger.info("=" * 60)
        
        date_range = f"{start_date.date().isoformat()}_to_{end_date.date().isoformat()}"
        
        # Load historical market data
        market_states = await self.data_loader.load_market_states(start_date, end_date)
        
        if not market_states:
            logger.error("No historical data available for testing")
            return {}
        
        # Generate current signals
        current_signals_by_strategy = {}
        
        for i, market_state in enumerate(market_states):
            if i % 10 == 0:
                logger.info(f"Processing market state {i+1}/{len(market_states)}...")
            
            try:
                signals = await self.strategy_engine.generate_signals(market_state)
                scored_signals = await self.model_manager.score_signals(signals, market_state)
                
                for signal in scored_signals:
                    strat_id = signal.get('strategy_id', 'unknown')
                    
                    if strategy_id and strat_id != strategy_id:
                        continue
                    
                    snapshot = SignalSnapshot(
                        timestamp=market_state['timestamp'],
                        strategy_id=strat_id,
                        symbol=signal['symbol'],
                        side=signal['side'],
                        confidence=signal.get('ml_confidence', 0.5),
                        entry_price=signal['entry_price'],
                        stop_loss=signal.get('stop_loss'),
                        take_profit=signal.get('take_profit'),
                        quantity=signal.get('quantity', 0),
                        reason=signal.get('reason', ''),
                        market_conditions={
                            'spot_price': market_state.get('spot_price', 0),
                            'total_oi': market_state.get('total_oi', 0),
                        }
                    )
                    
                    if strat_id not in current_signals_by_strategy:
                        current_signals_by_strategy[strat_id] = []
                    
                    current_signals_by_strategy[strat_id].append(snapshot)
            
            except Exception as e:
                logger.warning(f"Error processing market state: {e}")
                continue
        
        # Compare against baselines
        results = {}
        
        for strat_id, current_signals in current_signals_by_strategy.items():
            try:
                baseline_signals = self.baseline_manager.load_baseline(strat_id, date_range)
                result = self._compare_signals(strat_id, baseline_signals, current_signals)
                results[strat_id] = result
                
            except FileNotFoundError:
                logger.warning(f"No baseline found for {strat_id}, skipping")
                results[strat_id] = RegressionResult(
                    strategy_id=strat_id,
                    passed=False,
                    total_signals_baseline=0,
                    total_signals_current=len(current_signals),
                    matched_signals=0,
                    missing_signals=[],
                    extra_signals=current_signals,
                    confidence_diffs=[],
                    error_message="No baseline available"
                )
        
        # Print summary
        self._print_summary(results)
        
        return results
    
    def _compare_signals(
        self,
        strategy_id: str,
        baseline: List[SignalSnapshot],
        current: List[SignalSnapshot]
    ) -> RegressionResult:
        """Compare baseline and current signals"""
        
        # Build hash maps
        baseline_map = {s.get_hash(): s for s in baseline}
        current_map = {s.get_hash(): s for s in current}
        
        baseline_hashes = set(baseline_map.keys())
        current_hashes = set(current_map.keys())
        
        # Find matches, missing, and extra signals
        matched_hashes = baseline_hashes & current_hashes
        missing_hashes = baseline_hashes - current_hashes
        extra_hashes = current_hashes - baseline_hashes
        
        # Check confidence differences for matched signals
        confidence_diffs = []
        for h in matched_hashes:
            baseline_conf = baseline_map[h].confidence
            current_conf = current_map[h].confidence
            diff = abs(baseline_conf - current_conf)
            
            if diff > self.confidence_tolerance:
                confidence_diffs.append((h, baseline_conf, current_conf))
        
        # Determine pass/fail
        passed = (
            len(missing_hashes) == 0 and
            len(extra_hashes) == 0 and
            len(confidence_diffs) == 0
        )
        
        return RegressionResult(
            strategy_id=strategy_id,
            passed=passed,
            total_signals_baseline=len(baseline),
            total_signals_current=len(current),
            matched_signals=len(matched_hashes),
            missing_signals=[baseline_map[h] for h in missing_hashes],
            extra_signals=[current_map[h] for h in extra_hashes],
            confidence_diffs=confidence_diffs
        )
    
    def _print_summary(self, results: Dict[str, RegressionResult]):
        """Print test summary"""
        logger.info("=" * 60)
        logger.info("REGRESSION TEST SUMMARY")
        logger.info("=" * 60)
        
        total_tests = len(results)
        passed_tests = sum(1 for r in results.values() if r.passed)
        
        for strat_id, result in results.items():
            status = "✓ PASS" if result.passed else "✗ FAIL"
            logger.info(f"{status} | {strat_id}")
            logger.info(f"  Baseline: {result.total_signals_baseline} signals")
            logger.info(f"  Current:  {result.total_signals_current} signals")
            logger.info(f"  Matched:  {result.matched_signals} signals")
            
            if result.missing_signals:
                logger.info(f"  ⚠️  Missing: {len(result.missing_signals)} signals")
            
            if result.extra_signals:
                logger.info(f"  ⚠️  Extra: {len(result.extra_signals)} signals")
            
            if result.confidence_diffs:
                logger.info(f"  ⚠️  Confidence diffs: {len(result.confidence_diffs)} signals")
            
            if result.error_message:
                logger.info(f"  ❌ Error: {result.error_message}")
            
            logger.info("")
        
        logger.info("=" * 60)
        logger.info(f"TOTAL: {passed_tests}/{total_tests} tests passed")
        logger.info("=" * 60)


async def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Backtest Regression Test Suite')
    parser.add_argument('--mode', choices=['baseline', 'test'], required=True,
                       help='Mode: baseline (create) or test (run)')
    parser.add_argument('--strategy', type=str,
                       help='Specific strategy ID to test (default: all)')
    parser.add_argument('--start', type=str,
                       help='Start date (YYYY-MM-DD), default: 7 days ago')
    parser.add_argument('--end', type=str,
                       help='End date (YYYY-MM-DD), default: today')
    parser.add_argument('--tolerance', type=float, default=0.05,
                       help='Confidence tolerance (default: 0.05)')
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Parse dates
    end_date = datetime.strptime(args.end, '%Y-%m-%d') if args.end else datetime.now()
    start_date = datetime.strptime(args.start, '%Y-%m-%d') if args.start else end_date - timedelta(days=7)
    
    # Initialize tester
    tester = RegressionTester(confidence_tolerance=args.tolerance)
    await tester.initialize()
    
    # Run mode
    if args.mode == 'baseline':
        await tester.create_baseline(start_date, end_date, args.strategy)
    else:
        results = await tester.run_regression_tests(start_date, end_date, args.strategy)
        
        # Exit with failure code if any test failed
        if not all(r.passed for r in results.values()):
            sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
