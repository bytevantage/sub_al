"""
Risk Manager
Manages trading risk and position sizing
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, time
from backend.core.config import config
from backend.core.timezone_utils import now_ist, today_ist, should_exit_eod as tz_should_exit_eod, is_market_hours, IST
from backend.core.logger import get_execution_logger
from backend.config.production_locks import PRODUCTION_LOCKS, apply_production_locks
from backend.monitoring.prometheus_exporter import MetricsExporter
from backend.database.database import db
from backend.database.models import Trade
from backend.strategies.strategy_watchdog import StrategyWatchdog
from backend.ml.training_dataset import TrainingDatasetPipeline
from backend.strategies.strategy_mappings import (
    normalize_strategy_name,
    get_strategy_allocation,
    DEFAULT_STRATEGY_ALLOCATIONS
)
from backend.core.adaptive_config import adaptive_config
from backend.execution.fee_calculator import get_fee_calculator

logger = get_execution_logger()


REGIME_PARAMS = {
    "STRONG_TREND_LOW_VOL": {"risk_per_trade": 3.0, "daily_loss_limit": 10},
    "RANGING_LOW_VOL": {"risk_per_trade": 2.0, "daily_loss_limit": 6},
    "TRENDING_MODERATE_VOL": {"risk_per_trade": 2.5, "daily_loss_limit": 8},
    "MEAN_REVERSION": {"risk_per_trade": 1.5, "daily_loss_limit": 5},
    "HIGH_VOLATILITY": {"risk_per_trade": 1.0, "daily_loss_limit": 4}
}

class RiskManager:
    """Manages risk and position sizing with per-strategy allocation and circuit breakers"""
    
    def __init__(self, risk_config: Dict):
        self.is_paper_mode = config.is_paper_mode()
        self.initial_capital = config.get('trading.initial_capital', 100000)
        self.current_capital = self.initial_capital
        self.daily_loss_limit = risk_config.get('daily_loss_limit_percent', 3)
        self.per_trade_risk = risk_config.get('per_trade_risk_percent', 1)
        self.max_positions = config.get('trading.max_positions', 5)
        
        # Per-strategy capital allocation using canonical IDs
        # These will be overridden by DEFAULT_STRATEGY_ALLOCATIONS but kept for backward compatibility
        self.strategy_allocations = DEFAULT_STRATEGY_ALLOCATIONS.copy()
        
        # Per-strategy position tracking
        self.strategy_positions = {}  # {strategy: [positions]}
        self.strategy_pnl = {}  # {strategy: pnl}
        
        # Circuit breakers
        self.circuit_breaker_active = False
        self.circuit_breaker_triggers = {
            'high_iv': {'threshold': 40, 'triggered': False},  # VIX > 40
            'daily_loss': {'threshold': self.daily_loss_limit, 'triggered': False},
            'max_drawdown': {'threshold': 8, 'triggered': False},  # 8% equity drawdown
            'rapid_losses': {'threshold': 3, 'triggered': False}  # 3 consecutive losses
        }
        self.consecutive_losses = 0
        self.max_drawdown = 0
        self.peak_capital = self.initial_capital
        
        # Tracking
        self.open_positions = []
        self.closed_trades = []
        self.daily_pnl = 0
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        
        # Metrics exporter
        self.metrics_exporter = MetricsExporter()
        
        # Adaptive configuration system (initialize early)
        self.adaptive_config = adaptive_config
        
        # Strategy watchdog with adaptive thresholds
        adaptive_thresholds = self.adaptive_config.get_current_thresholds()
        watchdog_win_rate = adaptive_thresholds.get('strategy_watchdog_win_rate', 45.0)
        watchdog_consecutive_losses = adaptive_thresholds.get('strategy_watchdog_consecutive_losses', 5)
        
        self.strategy_watchdog = StrategyWatchdog(
            min_trades_for_evaluation=20,
            min_win_rate=watchdog_win_rate / 100.0,  # Convert to decimal
            max_consecutive_losses=watchdog_consecutive_losses
        )
        
        # Training dataset pipeline
        self.training_dataset = TrainingDatasetPipeline()
        
        # Fee calculator
        self.fee_calculator = get_fee_calculator()
        self.override_enabled = False
        self.circuit_breaker_reason: Optional[str] = None
        self.circuit_breaker_history: List[Dict] = []
        
        # Aggressive mode flag
        self.aggressive_mode_enabled = False
        
        # Market regime detection
        self.current_regime = "TRENDING_MODERATE_VOL"  # Default
        
        logger.info(
            f"Risk Manager initialized - Capital: ₹{self.initial_capital:,.0f}, "
            f"Circuit breakers: enabled, Strategy watchdog: enabled, Training dataset: enabled, "
            f"Fee calculator: enabled"
        )
    
    def can_take_trade(self, signal: Dict) -> bool:
        """
        Check if we can take a new trade with circuit breaker, per-strategy, and watchdog checks
        """
        
        # Skip circuit breakers in paper trading mode
        if self.is_paper_mode:
            logger.debug("Paper trading mode - circuit breakers disabled")
        else:
            # Check circuit breakers (only in live mode)
            if self.circuit_breaker_active and not self.override_enabled:
                logger.warning("⛔ Circuit breaker active - trading halted")
                self.metrics_exporter.update_circuit_breaker_metrics(True)
                return False

            if self.circuit_breaker_active and self.override_enabled:
                logger.warning("⚠️ Trading under override mode despite circuit breaker trigger")

        # Normalize strategy identifier (handles both strategy_id and strategy fields)
        strategy_raw = signal.get('strategy_id') or signal.get('strategy', 'default')
        strategy = normalize_strategy_name(strategy_raw)
        logger.info(f"🔍 Risk check for strategy: {strategy_raw} -> {strategy}")
        
        # Check strategy watchdog - is strategy enabled?
        if not self.strategy_watchdog.is_strategy_enabled(strategy):
            logger.warning(f"⛔ Strategy '{strategy}' is disabled by watchdog")
            return False
        
        # Check max positions with adaptive threshold
        adaptive_thresholds = self.adaptive_config.get_current_thresholds()
        max_positions = adaptive_thresholds.get('max_positions', self.max_positions)
        logger.info(f"🔍 Position check: {len(self.open_positions)} open, max={max_positions}")
        if len(self.open_positions) >= max_positions:
            logger.warning(f"Max positions ({max_positions}) reached")
            return False
        
        # Check daily loss limit (skip in paper trading mode)
        if not self.is_paper_mode:
            loss_percent = abs(self.daily_pnl / self.initial_capital * 100)
            if self.daily_pnl < 0 and loss_percent >= self.daily_loss_limit:
                logger.warning(f"Daily loss limit ({self.daily_loss_limit}%) reached")
                self._trigger_circuit_breaker('daily_loss', details=f"Loss {loss_percent:.2f}%")
                return False
        
            # Check max drawdown
            peak_capital = max(self.peak_capital, self.initial_capital)
            drawdown_percent = (self.max_drawdown / peak_capital) * 100 if peak_capital else 0
            if drawdown_percent >= self.circuit_breaker_triggers['max_drawdown']['threshold']:
                logger.warning(f"Max drawdown ({drawdown_percent:.2f}%) breached")
                self._trigger_circuit_breaker('max_drawdown', details=f"Drawdown {drawdown_percent:.2f}%")
                return False
        
        # Check signal strength with adaptive threshold
        adaptive_thresholds = self.adaptive_config.get_current_thresholds()
        min_strength = adaptive_thresholds.get('min_signal_strength', config.get('risk.min_signal_strength', 75))
        signal_strength = signal.get('strength', 0)
        logger.info(f"🔍 Strength check: signal={signal_strength}, min={min_strength}")
        if signal_strength < min_strength:
            logger.debug(f"Signal strength {signal_strength} below adaptive minimum {min_strength}")
            return False
        
        # Check per-strategy capital allocation
        if not self._check_strategy_allocation(strategy):
            logger.warning(f"Strategy {strategy} has reached capital allocation limit")
            return False
        
        return True
    
    def _check_strategy_allocation(self, strategy: str) -> bool:
        """
        Check if strategy has exceeded its capital allocation
        Uses canonical strategy_id for consistent allocation tracking
        """
        # Get allocation for this strategy (defaults handled by get_strategy_allocation)
        allocation_percent = get_strategy_allocation(strategy)
        max_strategy_capital = self.initial_capital * (allocation_percent / 100)
        
        # Calculate capital currently used by this strategy
        strategy_capital_used = 0
        for pos in self.open_positions:
            if pos.get('strategy') == strategy:
                strategy_capital_used += pos.get('entry_price', 0) * pos.get('quantity', 0)
        
        if strategy_capital_used >= max_strategy_capital:
            logger.debug(
                f"Strategy {strategy} at allocation limit: "
                f"₹{strategy_capital_used:,.0f} / ₹{max_strategy_capital:,.0f}"
            )
            return False
        
        return True
    
    def _trigger_circuit_breaker(self, reason: str, details: Optional[str] = None):
        """
        Trigger circuit breaker and halt trading (disabled in paper mode)
        """
        # Skip circuit breaker in paper trading mode
        if self.is_paper_mode:
            logger.debug(f"Paper trading mode - circuit breaker trigger '{reason}' ignored")
            return
            
        self.circuit_breaker_active = True
        self.circuit_breaker_triggers[reason]['triggered'] = True
        trigger_record = {
            'trigger': reason,
            'details': details,
            'timestamp': datetime.now().isoformat()
        }
        self.circuit_breaker_history.append(trigger_record)
        self.circuit_breaker_reason = details or reason
        
        # Record metrics
        self.metrics_exporter.record_circuit_breaker_trigger(reason)
        self.metrics_exporter.update_circuit_breaker_metrics(True)
        
        logger.error(f"🚨 CIRCUIT BREAKER TRIGGERED: {reason}")
        logger.error("All new trading halted. Please review system state.")
    
    def check_market_conditions(self, vix: float) -> bool:
        """
        Check if market conditions are suitable for trading
        Returns False if conditions are extreme
        """
        # Check VIX circuit breaker
        vix_threshold = self.circuit_breaker_triggers['high_iv']['threshold']
        if vix > vix_threshold:
            logger.warning(f"VIX {vix} exceeds threshold {vix_threshold}")
            self._trigger_circuit_breaker('high_iv')
            return False
        
        return True
    
    def calculate_position_size(self, signal: Dict, entry_price: float) -> int:
        """
        Calculate position size with production locks
        
        Args:
            signal: Trading signal
            entry_price: Entry price of option
            
        Returns:
            Quantity to trade (locked to production limits)
        """
        # Get adaptive risk percentage
        adaptive_thresholds = self.adaptive_config.get_current_thresholds()
        risk_percent = adaptive_thresholds.get('per_trade_risk_percent', self.per_trade_risk)
        
        # ML-Driven Position Sizing Boost (Aggressive Mode)
        if self.aggressive_mode_enabled:
            ml_confidence = signal.get('ml_confidence', 0.0)
            if ml_confidence > 0.7:  # High ML confidence threshold
                # Boost risk by 1.5x, capped at 3%
                risk_percent = min(3.0, risk_percent * 1.5)
                logger.info(f"⚡ Aggressive mode: Boosting position size (ML confidence: {ml_confidence:.2f}, Risk: {risk_percent:.2f}%)")
        
        # Risk amount per trade
        risk_amount = self.current_capital * (risk_percent / 100)
        
        # Get stop loss, ensure it's valid - CORRECTED 18% base (dynamic 15-24% with VIX)
        stop_loss = signal.get('stop_loss', entry_price * 0.82)  # Default 18% loss (was 8% - too tight!)
        
        # Handle invalid stop loss (>= entry price)
        if stop_loss >= entry_price:
            logger.warning(f"Invalid stop_loss ({stop_loss}) >= entry_price ({entry_price}), using 18% default")
            stop_loss = entry_price * 0.82  # 18% loss (was 8% - too tight!)
        
        # Calculate risk per lot (entry - stop loss)
        risk_per_lot = entry_price - stop_loss
        
        if risk_per_lot <= 0:
            logger.error(f"Risk per lot still invalid: {risk_per_lot}, returning 0 quantity")
            return 0
        
        # Calculate quantity
        lot_size = self._get_lot_size(signal.get('symbol'))
        quantity = int(risk_amount / (risk_per_lot * lot_size))
        
        # Ensure at least 1 lot
        if quantity < 1:
            quantity = 1
        
        # 🔒 Apply Production Locks - Maximum quantity per strike
        max_lots = PRODUCTION_LOCKS["max_position_size_per_strike"]
        if quantity > max_lots:
            quantity = max_lots
            logger.info(f"🔒 Position size capped at production limit: {max_lots} lots")
        
        return quantity * lot_size
    
    def should_exit(self, position: Dict) -> bool:
        """Check if position should be closed with trailing stop loss support"""
        
        # Check EOD exit first
        if self.should_exit_eod():
            return True
        
        current_price = position.get('current_price', 0)
        entry_price = position.get('entry_price', 0)
        stop_loss = position.get('stop_loss', 0)
        target = position.get('target_price', 0)
        
        # Skip if no valid current price yet
        if not current_price or current_price <= 0:
            return False
        
        # Initialize trailing stop loss and highest price if not present
        if 'trailing_sl' not in position:
            position['trailing_sl'] = stop_loss
        if 'highest_price' not in position:
            position['highest_price'] = entry_price
        
        # Use ADVANCED dynamic TP1/TP2/TP3 system from signal
        # Get the pre-calculated targets from the signal
        tp1 = position.get('tp1', 0)
        tp2 = position.get('tp2', 0)
        tp3 = position.get('tp3', target)  # Fallback to old target if TP3 not set
        regime = position.get('regime', 'default')
        
        # Ensure targets are valid numbers (not None)
        tp1 = tp1 or 0
        tp2 = tp2 or 0
        tp3 = tp3 or target or 0
        
        # If no TP1/TP2/TP3 set, fall back to calculation
        if not tp1 or not tp2:
            target = target or 0  # Ensure target is not None
            if target <= 0:
                # Create a default target based on stop loss distance
                stop_loss_distance = abs(entry_price - stop_loss) if stop_loss > 0 else entry_price * 0.18
                target = entry_price + stop_loss_distance * 2.7  # Default RR 1:2.7
                logger.warning(f"Using emergency fallback targets for {position.get('symbol')}: target=₹{target:.2f}")
            
            target_move = target - entry_price
            tp1 = entry_price + (target_move * 0.40)  # 40% scale-out
            tp2 = entry_price + (target_move * 0.75)  # 75% scale-out
            tp3 = target  # 100% target
            logger.info(f"Using fallback targets for {position.get('symbol')}: TP1=₹{tp1:.2f}, TP2=₹{tp2:.2f}, TP3=₹{tp3:.2f}")
        else:
            logger.info(f"🎯 Using dynamic targets for {position.get('symbol')} ({regime} regime): TP1=₹{tp1:.2f}, TP2=₹{tp2:.2f}, TP3=₹{tp3:.2f}")
        
        # FINAL SAFETY CHECK - ensure all targets are valid numbers
        tp1 = tp1 if tp1 and tp1 > 0 else 0
        tp2 = tp2 if tp2 and tp2 > 0 else 0  
        tp3 = tp3 if tp3 and tp3 > 0 else 0
        
        # If still no valid targets, skip exit checks entirely
        if tp1 <= 0 and tp2 <= 0 and tp3 <= 0:
            logger.warning(f"No valid targets for {position.get('symbol')} - skipping exit checks")
            return False
        
        # OFFICIAL SPEC: NO tiered profit taking
        # Only stop loss or EOD exit - let winners run
        
        # Check for stop loss hit (18% of premium, dynamic 15-24% with VIX)
        if current_price <= stop_loss:
            position['exit_reason'] = 'STOP_LOSS_HIT'
            position['exit_price'] = current_price
            logger.info(f"❌ Stop loss hit for {position.get('symbol')} - SL: ₹{stop_loss:.2f}, Current: ₹{current_price:.2f}")
            logger.info(f"🔔 STOP LOSS EXECUTED: Position closed at stop loss level")
            return True
        
        # NO TP1/TP2/TP3 - let winners run until EOD or stop loss
        
        return False
    
    def should_stop_trading(self, daily_pnl: float) -> bool:
        """Check if trading should be stopped for the day (disabled in paper trading mode)"""
        # Never stop trading in paper trading mode
        if self.is_paper_mode:
            return False
        
        remaining_budget = self.calculate_intraday_runway()
        if daily_pnl < -remaining_budget:
            logger.critical(
                f"Daily loss exceeded intraday budget: P&L ₹{daily_pnl:.2f} vs budget ₹{remaining_budget:.2f}"
            )
            return True

        return False

    def calculate_intraday_runway(self) -> float:
        """Calculate remaining loss budget based on time of day (IST)"""
        from backend.core.timezone_utils import ist_time, market_open_time, market_close_time
        
        # Full trading session duration in minutes (09:15 to 15:25)
        total_minutes = 6 * 60 + 10  # 370 minutes
        
        # Use IST timezone for accurate market hours
        now = ist_time()
        market_open = market_open_time()
        market_close = market_close_time()

        if now <= market_open:
            return self.initial_capital * (self.daily_loss_limit / 100)
        if now >= market_close:
            return 0.0

        elapsed = (now.hour - market_open.hour) * 60 + (now.minute - market_open.minute)
        remaining_ratio = max(0.0, 1 - (elapsed / total_minutes))
        daily_budget = self.initial_capital * (self.daily_loss_limit / 100)
        return daily_budget * remaining_ratio
    
    def check_daily_loss_limit(self) -> bool:
        """
        Check if daily loss limit has been exceeded
        
        Returns:
            True if daily loss limit exceeded, False otherwise
        """
        try:
            daily_pnl = self.get_daily_pnl()
            if daily_pnl >= 0:
                return False  # No loss, limit not exceeded
            
            loss_percent = abs(daily_pnl) / self.initial_capital * 100
            return loss_percent >= self.daily_loss_limit
        except Exception as e:
            logger.error(f"Error checking daily loss limit: {e}")
            return False  # Conservative: don't trigger on error
    
    def _convert_numpy_types(self, data):
        """Convert numpy types to native Python types for JSON serialization"""
        if isinstance(data, np.integer):
            return int(data)
        elif isinstance(data, np.floating):
            return float(data)
        elif isinstance(data, np.ndarray):
            return data.tolist()
        else:
            return data
    
    def _calculate_pnl_percentage(self, net_pnl: float, entry_price: float, quantity: int, direction: str = 'SELL') -> float:
        """Calculate P&L percentage with correct direction logic"""
        if entry_price * quantity == 0:
            return 0.0
        
        # For SELL positions (most options trades), percentage is based on premium received
        if direction == 'SELL':
            return (net_pnl / (entry_price * quantity)) * 100
        else:  # BUY
            return (net_pnl / (entry_price * quantity)) * 100
    
    def record_trade(self, trade: Dict, market_state: Dict = None):
        """Record completed trade in memory, metrics, database, watchdog, and training dataset"""
        self.total_trades += 1
        
        # Convert numpy types to native Python types
        trade = self._convert_numpy_types(trade)
        
        # Calculate fees and net P&L
        entry_price = trade.get('entry_price', 0)
        exit_price = trade.get('exit_price', 0)
        quantity = trade.get('quantity', 0)
        gross_pnl = trade.get('pnl', 0)  # This is gross P&L
        
        # Calculate net P&L after fees
        net_pnl, fee_breakdown = self.fee_calculator.calculate_net_pnl(
            gross_pnl, entry_price, exit_price, quantity
        )
        
        # Update capital with net P&L
        self.daily_pnl += net_pnl
        self.current_capital += net_pnl

        # Update equity peak/drawdown tracking
        if self.current_capital > self.peak_capital:
            self.peak_capital = self.current_capital

        drawdown_amount = max(0, self.peak_capital - self.current_capital)
        if drawdown_amount > self.max_drawdown:
            self.max_drawdown = drawdown_amount

        if not self.is_paper_mode and self.peak_capital > 0:
            drawdown_pct = (drawdown_amount / self.peak_capital) * 100
            if drawdown_pct >= self.circuit_breaker_triggers['max_drawdown']['threshold']:
                logger.error(
                    f"🚨 Max drawdown {drawdown_pct:.2f}% exceeded (limit {self.circuit_breaker_triggers['max_drawdown']['threshold']}%)."
                )
                self._trigger_circuit_breaker(
                    'max_drawdown',
                    details=f"Drawdown {drawdown_pct:.2f}%"
                )
        
        # Normalize strategy identifier
        strategy_raw = trade.get('strategy_id') or trade.get('strategy', 'unknown')
        strategy = normalize_strategy_name(strategy_raw)
        
        # Track consecutive losses for circuit breaker
        if net_pnl > 0:
            self.winning_trades += 1
            self.consecutive_losses = 0  # Reset on win
            is_winning = True
        else:
            self.losing_trades += 1
            self.consecutive_losses += 1
            is_winning = False
            
            # Check rapid losses circuit breaker
            rapid_loss_threshold = self.circuit_breaker_triggers['rapid_losses']['threshold']
            if self.consecutive_losses >= rapid_loss_threshold:
                logger.warning(f"{self.consecutive_losses} consecutive losses detected")
                self._trigger_circuit_breaker('rapid_losses', details=f"Consecutive losses: {self.consecutive_losses}")
        
        # Update peak capital and drawdown
        if self.current_capital > self.peak_capital:
            self.peak_capital = self.current_capital
        
        drawdown = self.peak_capital - self.current_capital
        if drawdown > self.max_drawdown:
            self.max_drawdown = drawdown
        
        self.closed_trades.append(trade)
        
        # Report to strategy watchdog
        allocated_capital = get_strategy_allocation(strategy)
        allocated_capital_value = (allocated_capital / 100) * self.initial_capital
        self.strategy_watchdog.record_trade(strategy, net_pnl, allocated_capital_value)
        
        # Log to training dataset
        if market_state:
            try:
                self.training_dataset.log_trade(trade, market_state)
            except Exception as e:
                logger.error(f"Failed to log trade to training dataset: {e}")
        
        # Record metrics
        side = trade.get('side', 'BUY')
        status = 'closed'
        self.metrics_exporter.record_trade(strategy, side, status, net_pnl)
        
        # Update per-strategy tracking
        if strategy not in self.strategy_pnl:
            self.strategy_pnl[strategy] = 0
        self.strategy_pnl[strategy] += net_pnl
        
        # Persist to database with fees
        try:
            # Ensure entry_time and exit_time are datetime objects (not strings)
            entry_time_raw = trade.get('entry_time', datetime.now())
            exit_time_raw = trade.get('exit_time', datetime.now())
            
            # Convert string to datetime if needed
            if isinstance(entry_time_raw, str):
                try:
                    entry_time_raw = datetime.fromisoformat(entry_time_raw.replace('Z', '+00:00'))
                except:
                    entry_time_raw = datetime.now()
            
            if isinstance(exit_time_raw, str):
                try:
                    exit_time_raw = datetime.fromisoformat(exit_time_raw.replace('Z', '+00:00'))
                except:
                    exit_time_raw = datetime.now()
            
            session = db.get_session()
            if session:
                trade_record = Trade(
                    trade_id=trade.get('id', ''),
                    entry_time=entry_time_raw,
                    exit_time=exit_time_raw,
                    symbol=trade.get('symbol', ''),
                    instrument_type=trade.get('direction', 'CALL'),  # CALL or PUT
                    strike_price=trade.get('strike', 0),
                    expiry_date=trade.get('expiry'),
                    entry_price=entry_price,
                    exit_price=exit_price,
                    quantity=quantity,
                    entry_mode=trade.get('mode', 'PAPER'),
                    exit_type=trade.get('exit_reason', 'MANUAL'),
                    gross_pnl=gross_pnl,
                    brokerage=fee_breakdown['total_brokerage'],
                    taxes=fee_breakdown['stt'] + fee_breakdown['stamp_duty'],
                    net_pnl=net_pnl,
                    pnl_percentage=self._calculate_pnl_percentage(net_pnl, entry_price, quantity, trade.get('direction', 'SELL')),
                    strategy_name=strategy,
                    signal_strength=trade.get('signal_strength', 0),
                    ml_score=trade.get('ml_confidence', 0),
                    # ML Telemetry
                    model_version=trade.get('model_version'),
                    model_hash=trade.get('model_hash'),
                    features_snapshot=trade.get('features_snapshot', {}),
                    # Market context at entry
                    spot_price_entry=trade.get('spot_price_entry', 0),
                    vix_entry=trade.get('vix_entry', 0),
                    pcr_entry=trade.get('pcr_entry', 0),
                    # Market context at exit
                    spot_price_exit=trade.get('spot_price_exit', 0),
                    vix_exit=trade.get('vix_exit', 0),
                    pcr_exit=trade.get('pcr_exit', 0),
                    # Greeks at entry
                    delta_entry=trade.get('delta_entry', 0.0),
                    gamma_entry=trade.get('gamma_entry', 0.0),
                    theta_entry=trade.get('theta_entry', 0.0),
                    vega_entry=trade.get('vega_entry', 0.0),
                    iv_entry=trade.get('iv_entry', 20.0),
                    # Greeks at exit
                    delta_exit=trade.get('delta_exit', 0.0),
                    gamma_exit=trade.get('gamma_exit', 0.0),
                    theta_exit=trade.get('theta_exit', 0.0),
                    vega_exit=trade.get('vega_exit', 0.0),
                    iv_exit=trade.get('iv_exit', 0.0),
                    # Option chain at entry
                    oi_entry=trade.get('oi_entry', 0),
                    volume_entry=trade.get('volume_entry', 0),
                    bid_entry=trade.get('bid_entry', 0.0),
                    ask_entry=trade.get('ask_entry', 0.0),
                    spread_entry=trade.get('spread_entry', 0.0),
                    # Option chain at exit
                    oi_exit=trade.get('oi_exit', 0),
                    volume_exit=trade.get('volume_exit', 0),
                    bid_exit=trade.get('bid_exit', 0.0),
                    ask_exit=trade.get('ask_exit', 0.0),
                    spread_exit=trade.get('spread_exit', 0.0),
                    # Position management
                    target_price=trade.get('target_price', 0),
                    stop_loss_price=trade.get('stop_loss', 0),
                    # Status
                    status='CLOSED',
                    is_winning_trade=is_winning,
                    hold_duration_minutes=trade.get('hold_duration_minutes', 0),
                    signal_reason=trade.get('signal_reason', ''),
                    exit_reason=trade.get('exit_reason', '')
                )
                
                # Calculate P&L and duration
                trade_record.calculate_pnl()
                
                session.add(trade_record)
                session.commit()
                session.close()
                
                logger.debug(f"Trade persisted to database: {trade.get('id')}")
        except Exception as e:
            logger.error(f"Failed to persist trade to database: {e}")
            # Don't crash - trading continues even if DB write fails
        
        logger.info(
            f"Trade closed: {trade.get('symbol')} | "
            f"Gross P&L: ₹{gross_pnl:,.2f} | Fees: ₹{fee_breakdown['total_fees']:,.2f} | "
            f"Net P&L: ₹{net_pnl:,.2f} | "
            f"Total P&L: ₹{self.daily_pnl:,.2f} | "
            f"Consecutive losses: {self.consecutive_losses}"
        )
        
        # Update adaptive configuration with trade result
        self.adaptive_config.update_performance_data(trade_result={
            'pnl': net_pnl,
            'strategy': strategy,
            'is_winning': is_winning
        })
    
    def add_position(self, position: Dict):
        """Add new open position"""
        self.open_positions.append(position)
    
    def remove_position(self, position_id: str):
        """Remove closed position - check both id and position_id fields"""
        self.open_positions = [
            p for p in self.open_positions 
            if (p.get('id') != position_id and p.get('position_id') != position_id)
        ]

    def get_open_positions(self) -> List[Dict]:
        """Return list of open position dicts"""
        return list(self.open_positions)

    def get_open_positions_summary(self) -> List[Dict]:
        """Return simplified snapshot of open positions"""
        summaries: List[Dict] = []
        for pos in self.open_positions:
            entry_price = pos.get('entry_price') or 0.0
            current_price = pos.get('current_price', entry_price) or entry_price
            quantity = pos.get('quantity') or 0
            direction = pos.get('direction') or pos.get('side') or 'BUY'
            unrealized = pos.get('unrealized_pnl')
            if unrealized is None:
                if direction.upper() == 'SELL':
                    unrealized = (entry_price - current_price) * quantity
                else:
                    unrealized = (current_price - entry_price) * quantity
            invested = entry_price * quantity
            pnl_pct = (unrealized / invested * 100) if invested else 0.0
            entry_time = pos.get('entry_time')
            # Convert CALL/PUT to CE/PE for dashboard
            instrument_type = pos.get('instrument_type', '')
            option_type = 'CE' if instrument_type == 'CALL' else 'PE' if instrument_type == 'PUT' else ''
            
            # Get or calculate target price
            target_price = pos.get('target_price', 0)
            if target_price == 0:
                # Set default target based on strategy and direction
                strategy = pos.get('strategy', '').lower()
                if 'gamma' in strategy:
                    target_price = entry_price * 1.15  # 15% target for gamma scalping
                elif 'quantum' in strategy:
                    target_price = entry_price * 1.25  # 25% target for quantum edge
                elif 'default' in strategy:
                    target_price = entry_price * 1.20  # 20% target for default
                elif 'iv_rank' in strategy:
                    target_price = entry_price * 1.30  # 30% target for IV rank
                elif 'vwap' in strategy:
                    target_price = entry_price * 1.15  # 15% target for VWAP
                else:
                    target_price = entry_price * 1.15  # Default 15% target
                
                # Update the position with calculated target price for future reference
                pos['target_price'] = target_price
            
            summaries.append({
                'id': pos.get('id'),
                'symbol': pos.get('symbol'),
                'direction': direction,
                'strike_price': pos.get('strike_price', 0),  # Fixed: was 'strike'
                'instrument_type': instrument_type,  # CALL/PUT
                'option_type': option_type,  # CE/PE for dashboard
                'expiry': pos.get('expiry'),
                'quantity': quantity,
                'entry_price': round(entry_price, 2),
                'current_price': round(current_price, 2),
                'unrealized_pnl': round(unrealized, 2),
                'pnl_percent': round(pnl_pct, 2),
                'strategy': pos.get('strategy') or pos.get('strategy_name'),
                'entry_time': entry_time.isoformat() if hasattr(entry_time, 'isoformat') else entry_time,
                'status': pos.get('status', 'open'),
                # Added: Risk management levels
                'stop_loss': pos.get('stop_loss', 0),
                'trailing_sl': pos.get('trailing_sl', 0),
                'target_price': pos.get('target_price', 0),
                'highest_price': pos.get('highest_price', entry_price),
                # Calculate target levels for dashboard (T1/T2/T3) - only if target_price exists
                'target_1': self._calculate_target_1(entry_price, target_price) if target_price > 0 else 0,
                'target_2': target_price if target_price > 0 else 0,
                'target_3': self._calculate_target_3(entry_price, target_price) if target_price > 0 else 0,
            })
        return summaries

    def _calculate_target_1(self, entry_price: float, target_price: float) -> float:
        """Calculate T1 (50% of target) - CORRECTED for option buying"""
        if entry_price <= 0 or target_price <= 0:
            return 0.0
        # For option buying, targets should be HIGHER than entry price
        return round(entry_price + (target_price - entry_price) * 0.5, 2)  # 50% of target

    def _calculate_target_3(self, entry_price: float, target_price: float) -> float:
        """Calculate T3 (150% of target) - CORRECTED for option buying"""
        if entry_price <= 0 or target_price <= 0:
            return 0.0
        # For option buying, targets should be HIGHER than entry price
        return round(entry_price + (target_price - entry_price) * 1.5, 2)  # 150% of target

    def get_metrics_summary(self) -> Dict:
        """Aggregate risk metrics for API consumption"""
        capital_info = self.get_capital_info()
        cb_summary = self.get_circuit_breaker_summary()
        profit_factor = self.get_profit_factor()
        if profit_factor == float('inf'):
            profit_factor = None
        return {
            'daily_pnl': self.daily_pnl,
            'daily_pnl_percent': cb_summary.get('daily_pnl_percent'),
            'total_trades': self.total_trades,
            'win_rate': round(self.get_win_rate(), 2),
            'profit_factor': profit_factor,
            'max_drawdown': self.max_drawdown,
            'max_drawdown_percent': round((self.max_drawdown / self.initial_capital * 100) if self.initial_capital else 0, 2),
            'consecutive_losses': self.consecutive_losses,
            'capital': capital_info,
            'circuit_breaker': cb_summary,
            'open_positions': self.get_open_positions_summary(),
        }
    
    def get_win_rate(self) -> float:
        """Calculate win rate"""
        if self.total_trades == 0:
            return 0.0
        return (self.winning_trades / self.total_trades) * 100
    
    def get_profit_factor(self) -> float:
        """Calculate profit factor"""
        gross_profit = sum(t.get('pnl', 0) for t in self.closed_trades if t.get('pnl', 0) > 0)
        gross_loss = abs(sum(t.get('pnl', 0) for t in self.closed_trades if t.get('pnl', 0) < 0))
        
        if gross_loss == 0:
            return float('inf') if gross_profit > 0 else 0.0
        
        return gross_profit / gross_loss
    
    def get_capital_info(self) -> Dict:
        """
        Get comprehensive capital information for metrics and monitoring
        
        Returns:
            Dict with total, used, available, utilization, pnl
        """
        # Calculate capital used in open positions
        capital_used = sum(
            pos.get('entry_price', 0) * pos.get('quantity', 0) 
            for pos in self.open_positions
        )
        
        # Calculate available capital
        capital_available = max(0, self.current_capital - capital_used)
        
        # Calculate utilization percentage
        if self.current_capital > 0:
            utilization = (capital_used / self.current_capital) * 100
        else:
            utilization = 0.0
        
        return {
            'total': self.current_capital,
            'used': capital_used,
            'available': capital_available,
            'utilization': utilization,
            'daily_pnl': self.daily_pnl,
            'initial_capital': self.initial_capital
        }

    def force_emergency_stop(self, reason: str):
        """Force circuit breaker activation with provided reason."""
        self.circuit_breaker_active = True
        self.circuit_breaker_reason = reason
        self.circuit_breaker_history.append({
            'trigger': 'emergency_stop',
            'details': reason,
            'timestamp': datetime.now().isoformat()
        })

    def reset_circuit_breaker(self, reason: Optional[str] = None):
        """Reset circuit breaker state."""
        self.circuit_breaker_active = False
        self.override_enabled = False
        self.circuit_breaker_reason = reason
        for trigger in self.circuit_breaker_triggers.values():
            trigger['triggered'] = False

    def enable_override(self, note: Optional[str] = None):
        """Enable manual override mode."""
        self.override_enabled = True
        self.circuit_breaker_reason = note or self.circuit_breaker_reason

    def disable_override(self):
        """Disable manual override mode."""
        self.override_enabled = False

    def get_circuit_breaker_summary(self) -> Dict:
        """Return a summary usable by status endpoints."""
        active_triggers = [
            name for name, info in self.circuit_breaker_triggers.items()
            if info.get('triggered')
        ]
        daily_loss_percent = (
            abs(self.daily_pnl) / self.initial_capital * 100
            if self.initial_capital else 0
        )
        return {
            'active': self.circuit_breaker_active,
            'override_enabled': self.override_enabled,
            'reason': self.circuit_breaker_reason,
            'active_triggers': active_triggers,
            'history': self.circuit_breaker_history[-20:],
            'daily_pnl': self.daily_pnl,
            'daily_pnl_percent': round(daily_loss_percent, 2)
        }

    def get_daily_pnl(self) -> float:
        """Return current day's realized P&L"""
        return float(self.daily_pnl)

    def get_daily_pnl_percent(self) -> float:
        """Return daily P&L as percentage of initial capital"""
        if self.initial_capital <= 0:
            return 0.0
        return (self.daily_pnl / self.initial_capital) * 100

    def get_total_trades(self) -> int:
        """Return total number of trades executed today"""
        return int(self.total_trades)

    def get_win_rate(self) -> float:
        """Return win rate as fraction (0-1)"""
        total = self.winning_trades + self.losing_trades
        if total == 0:
            return 0.0
        return self.winning_trades / total

    def get_max_drawdown_percent(self) -> float:
        """Return maximum drawdown as percentage of initial capital"""
        if self.initial_capital <= 0:
            return 0.0
        return (self.max_drawdown / self.initial_capital) * 100
    
    def calculate_live_mtm(self, position: Dict, current_price: float) -> float:
        """
        Calculate live mark-to-market P&L for a position
        
        Args:
            position: Position dict with entry_price, quantity, side
            current_price: Current market price of the option
            
        Returns:
            Current P&L (unrealized)
        """
        entry_price = position.get('entry_price', 0)
        quantity = position.get('quantity', 0)
        side = position.get('side', 'BUY')
        
        if side == 'BUY':
            # Long position: profit when price increases
            mtm_pnl = (current_price - entry_price) * quantity
        else:
            # Short position: profit when price decreases
            mtm_pnl = (entry_price - current_price) * quantity
        
        return mtm_pnl
    
    def should_exit_eod(self) -> bool:
        """
        Check if End-of-Day exit logic should trigger
        
        Returns:
            True if time is after production lock time (15:25 PM IST)
        """
        # Use production lock time for EOD exit (15:25 IST, not 15:29)
        production_eod_time = PRODUCTION_LOCKS["force_eod_exit_time"]
        current_time = now_ist().time()
        
        if current_time >= production_eod_time:
            logger.info(f"🔒 PRODUCTION EOD exit triggered at {current_time.strftime('%H:%M:%S')} IST "
                       f"(lock time: {production_eod_time.strftime('%H:%M')}) - closing all positions")
            return True
        return False
    
    def should_stop_new_orders(self) -> bool:
        """
        Check if new orders should be stopped (15:20 PM IST)
        
        Returns:
            True if time is after no-new-orders cutoff (15:20 PM IST)
        """
        no_orders_time = PRODUCTION_LOCKS["no_new_orders_after"]
        current_time = now_ist().time()
        
        if current_time >= no_orders_time:
            logger.info(f"⛔ NO NEW ORDERS cutoff at {current_time.strftime('%H:%M:%S')} IST "
                       f"(cutoff time: {no_orders_time.strftime('%H:%M')}) - stopping new position generation")
            return True
        return False
    
    def _check_trend_strength(self, position: Dict) -> bool:
        """Check if there's a strong trend based on technical indicators"""
        try:
            symbol = position.get('symbol', '')
            if not symbol:
                return False
            
            # Get market state for technical indicators
            from backend.main import app
            trading_system = getattr(app.state, 'trading_system', None)
            if not trading_system or not hasattr(trading_system, 'market_data'):
                return False
            
            market_state = trading_system.market_data.market_state.get(symbol, {})
            technical_indicators = market_state.get('technical_indicators', {})
            
            # Check for strong trend signals
            rsi = technical_indicators.get('rsi', 50)
            vwap = technical_indicators.get('vwap', 0)
            spot_price = market_state.get('spot_price', 0)
            
            # Strong trend criteria:
            # 1. RSI > 60 (bullish) or < 40 (bearish) - but for options buying we want bullish
            # 2. Price above VWAP (bullish momentum)
            # 3. ADX > 25 (strong trend) - if available
            
            strong_rsi = rsi > 60
            above_vwap = spot_price > vwap if vwap > 0 else False
            
            # Consider trend strong if at least 2 criteria met
            trend_score = sum([strong_rsi, above_vwap])
            
            logger.debug(f"Trend check for {symbol}: RSI={rsi}, above_VWAP={above_vwap}, score={trend_score}/2")
            return trend_score >= 2
            
        except Exception as e:
            logger.error(f"Error checking trend strength: {e}")
            return False
    
    def _check_volume_strength(self, position: Dict) -> bool:
        """Check if volume is strong based on recent option chain data"""
        try:
            symbol = position.get('symbol', '')
            if not symbol:
                return False
            
            # Get market state for volume data
            from backend.main import app
            trading_system = getattr(app.state, 'trading_system', None)
            if not trading_system or not hasattr(trading_system, 'market_data'):
                return False
            
            market_state = trading_system.market_data.market_state.get(symbol, {})
            option_chain = market_state.get('option_chain', {})
            
            # Calculate total OI and volume for ATM strikes
            calls = option_chain.get('calls', {})
            puts = option_chain.get('puts', {})
            
            # Get ATM strike
            spot_price = market_state.get('spot_price', 0)
            atm_strike = round(spot_price / 50) * 50  # Round to nearest 50
            
            # Check OI for ATM and nearby strikes
            total_oi = 0
            for strike_offset in [-100, -50, 0, 50, 100]:  # Check 5 strikes around ATM
                strike_key = str(int(atm_strike + strike_offset))
                if strike_key in calls:
                    total_oi += calls[strike_key].get('oi', 0)
                if strike_key in puts:
                    total_oi += puts[strike_key].get('oi', 0)
            
            # Consider volume strong if total OI > 100,000 (indicating high interest)
            strong_volume = total_oi > 100000
            
            logger.debug(f"Volume check for {symbol}: Total OI={total_oi}, strong={strong_volume}")
            return strong_volume
            
        except Exception as e:
            logger.error(f"Error checking volume strength: {e}")
            return False
    
    def calculate_dynamic_targets(self, position: Dict) -> Dict:
        """
        Calculate dynamic TP1/TP2/TP3 targets for a position based on risk-reward ratios
        
        Args:
            position: Position dict with entry_price, stop_loss, etc.
            
        Returns:
            Position dict with tp1, tp2, tp3 added/updated
        """
        try:
            entry_price = position.get('entry_price', 0)
            stop_loss = position.get('stop_loss', 0)
            
            if entry_price <= 0:
                logger.warning(f"Invalid entry price for dynamic targets: {entry_price}")
                return position
            
            # If no stop loss, use 18% default (same as risk_reward_config)
            if not stop_loss or stop_loss <= 0:
                stop_loss = entry_price * 0.82  # 18% loss
                position['stop_loss'] = stop_loss
            
            # Calculate risk amount
            risk_amount = entry_price - stop_loss
            
            if risk_amount <= 0:
                logger.warning(f"Invalid risk amount for dynamic targets: {risk_amount}")
                return position
            
            # Get regime for RR multiplier (default to 2.7)
            regime = position.get('regime', 'default')
            rr_multiplier = self._get_rr_multiplier(regime)
            
            # Calculate layered targets
            tp1 = entry_price + (risk_amount * rr_multiplier * 0.40)  # 40% at partial RR
            tp2 = entry_price + (risk_amount * rr_multiplier * 0.75)  # 75% at higher RR  
            tp3 = entry_price + (risk_amount * rr_multiplier * 1.00)  # 100% at full RR
            
            # Update position with targets
            position['tp1'] = round(tp1, 2)
            position['tp2'] = round(tp2, 2)
            position['tp3'] = round(tp3, 2)
            
            logger.debug(f"Calculated dynamic targets for {position.get('symbol')}: TP1=₹{tp1:.2f}, TP2=₹{tp2:.2f}, TP3=₹{tp3:.2f}")
            
            return position
            
        except Exception as e:
            logger.error(f"Error calculating dynamic targets: {e}")
            # Return position unchanged on error
            return position
    
    def check_exit_conditions(self, position: Dict, current_price: float, 
                          current_greeks: Dict = None) -> Tuple[bool, str, Optional[float]]:
        try:
            direction = position.get('direction', 'BUY')
            entry_price = position.get('entry_price', 0)
            stop_loss = position.get('stop_loss', 0)
            
            # Calculate dynamic targets if not present
            if not all([position.get('tp1'), position.get('tp2'), position.get('tp3')]):
                position = self.calculate_dynamic_targets(position)
            
            # Get dynamic targets
            tp1 = position.get('tp1')
            tp2 = position.get('tp2')
            tp3 = position.get('tp3')
            original_quantity = position.get('original_quantity', position.get('quantity', 0))
            
            # Calculate profit percentage
            if direction == 'BUY':
                profit_pct = ((current_price - entry_price) / entry_price) * 100
            else:
                profit_pct = ((entry_price - current_price) / entry_price) * 100
            
            # Check TP1 (40% scale-out) + Move SL to breakeven + 0.5% buffer
            if tp1 and tp1 > 0 and not position.get('tp1_hit'):
                if (direction == 'BUY' and current_price >= tp1) or \
                   (direction == 'SELL' and current_price <= tp1):
                    position['tp1_hit'] = True
                    # Scale out 40%
                    scale_quantity = int(original_quantity * 0.4)
                    position['remaining_quantity'] = original_quantity - scale_quantity
                    
                    # Move SL to breakeven + 0.5% buffer
                    if direction == 'BUY':
                        new_sl = entry_price * 1.005  # 0.5% above entry
                    else:
                        new_sl = entry_price * 0.995  # 0.5% below entry
                    position['stop_loss'] = new_sl
                    
                    logger.info(f"🎯 TP1 hit: Scale out 40% ({scale_quantity} lots) at ₹{current_price}, "
                               f"SL moved to breakeven +0.5% (₹{new_sl:.2f})")
                    return True, "TP1_SCALE_OUT", current_price
            
            # Check TP2 (35% scale-out)
            if tp2 and tp2 > 0 and not position.get('tp2_hit') and position.get('tp1_hit'):
                if (direction == 'BUY' and current_price >= tp2) or \
                   (direction == 'SELL' and current_price <= tp2):
                    position['tp2_hit'] = True
                    # Scale out 35%
                    scale_quantity = int(original_quantity * 0.35)
                    position['remaining_quantity'] -= scale_quantity
                    
                    logger.info(f"🎯 TP2 hit: Scale out 35% ({scale_quantity} lots) at ₹{current_price}, "
                               f"Remaining: {position['remaining_quantity']} lots")
                    return True, "TP2_SCALE_OUT", current_price
            
            # Check TP3 (final 25% runner) + Start trailing after 12% profit
            if tp3 and tp3 > 0 and not position.get('tp3_hit') and position.get('tp2_hit'):
                if (direction == 'BUY' and current_price >= tp3) or \
                   (direction == 'SELL' and current_price <= tp3):
                    position['tp3_hit'] = True
                    logger.info(f"🎯 TP3 hit: Final exit 25% at ₹{current_price}")
                    return True, "TP3_COMPLETE", current_price
            
            # Trailing stop for runner after 12% profit
            if position.get('tp2_hit') and profit_pct >= 12.0:
                trail_distance = self.get_trail_distance(position, current_greeks)
                if direction == 'BUY':
                    new_trailing_sl = current_price - trail_distance
                    if new_trailing_sl > position.get('stop_loss', 0):
                        position['stop_loss'] = new_trailing_sl
                        position['trailing_sl'] = new_trailing_sl
                        logger.debug(f"📈 Trailing SL updated: ₹{new_trailing_sl:.2f} (trail: {trail_distance:.2f})")
                else:
                    new_trailing_sl = current_price + trail_distance
                    if new_trailing_sl < position.get('stop_loss', float('inf')):
                        position['stop_loss'] = new_trailing_sl
                        position['trailing_sl'] = new_trailing_sl
                        logger.debug(f"📉 Trailing SL updated: ₹{new_trailing_sl:.2f} (trail: {trail_distance:.2f})")
            
            # Check stop loss (including trailing)
            current_sl = position.get('stop_loss')
            if current_sl:
                if (direction == 'BUY' and current_price <= current_sl) or \
                   (direction == 'SELL' and current_price >= current_sl):
                    sl_type = "TRAILING_STOP" if position.get('trailing_sl') else "STOP_LOSS"
                    return True, sl_type, current_price
            
            return False, "", None
            
        except Exception as e:
            logger.error(f"Error checking exit conditions: {e}")
            return False, "", None
    
    def get_trail_distance(self, position: Dict, current_greeks: Dict = None) -> float:
        """
        Calculate trailing stop distance based on ATR and volatility
        
        Args:
            position: Position dict
            current_greeks: Current Greeks values
            
        Returns:
            Trail distance in price units
        """
        try:
            # Use 1.5x ATR(10) as default trail distance
            # In production, this would use actual ATR from market data
            entry_price = position.get('entry_price', 0)
            
            # Default trail distance (would be calculated from ATR in production)
            trail_pct = 0.015  # 1.5% default
            
            # Adjust for gamma positions (wider trail)
            if current_greeks:
                gamma = current_greeks.get('gamma', 0)
                if abs(gamma) > 0.05:  # High gamma
                    trail_pct = 0.02  # 2% trail for gamma positions
            
            return entry_price * trail_pct
            
        except Exception as e:
            logger.error(f"Error calculating trail distance: {e}")
            # Fallback to 1.5% of entry price
            return position.get('entry_price', 0) * 0.015
    
    def _get_rr_multiplier(self, regime: str) -> float:
        """Get risk-reward multiplier based on regime"""
        multipliers = {
            'high_confidence': 3.8,
            'monster_day': 4.5,
            'expiry_morning': 3.2,
            'chop_regime': 1.8,
            'default': 2.7
        }
        return multipliers.get(regime, 2.7)
    
    def update_position_mtm(self, position: Dict, current_price: float):
        """
        Update position with live MTM P&L
        
        Args:
            position: Position dict to update
            current_price: Current market price
        """
        mtm_pnl = self.calculate_live_mtm(position, current_price)
        position['current_price'] = current_price
        position['unrealized_pnl'] = mtm_pnl
        
        # Update max profit/loss tracking
        if mtm_pnl > position.get('max_profit', 0):
            position['max_profit'] = mtm_pnl
        if mtm_pnl < position.get('max_loss', 0):
            position['max_loss'] = mtm_pnl
    
    def _get_lot_size(self, symbol: str) -> int:
        """
        Get lot size for symbol
        
        Official lot sizes (as of Nov 2025):
        - NIFTY: 75 (expires every Tuesday)
        - SENSEX: 20 (expires every Thursday)
        """
        lot_sizes = {
            'NIFTY': 75,
            'SENSEX': 20
        }
        return lot_sizes.get(symbol, 75)

    def detect_market_regime(self, vix: float, trend_strength: float) -> str:
        """Classify market conditions into regimes"""
        if vix < 15 and trend_strength > 0.7:
            return "STRONG_TREND_LOW_VOL"
        elif vix < 15:
            return "RANGING_LOW_VOL"
        elif vix < 25 and trend_strength > 0.6:
            return "TRENDING_MODERATE_VOL"
        elif vix < 25:
            return "MEAN_REVERSION"
        else:
            return "HIGH_VOLATILITY"
            
    def refresh_risk_parameters(self, vix: float, trend_strength: float):
        """Update risk parameters based on current market regime"""
        self.current_regime = self.detect_market_regime(vix, trend_strength)
        params = REGIME_PARAMS[self.current_regime]
        self.per_trade_risk = params["risk_per_trade"]
        self.daily_loss_limit = params["daily_loss_limit"]
        logger.info(f"Market regime: {self.current_regime} | Risk: {self.per_trade_risk}%/trade, Daily Loss Limit: {self.daily_loss_limit}%")
