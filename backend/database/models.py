"""
Database Models for Trade History and Analytics
SQLAlchemy models for PostgreSQL/TimescaleDB
STORAGE: All timestamps stored in UTC (raw)
DISPLAY: All timestamps converted to IST for display/calculations
"""

from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo
from backend.core.timezone_utils import now_utc, to_ist
from sqlalchemy import Column, Integer, BigInteger, String, Float, DateTime, Boolean, Text, Index, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

# IST timezone for display
IST = ZoneInfo("Asia/Kolkata")

Base = declarative_base()


class Trade(Base):
    """Complete trade history with all execution details"""
    __tablename__ = "trades"
    
    # Primary identification
    id = Column(Integer, primary_key=True, autoincrement=True)
    trade_id = Column(String(50), unique=True, nullable=False, index=True)
    
    # Timestamps (stored in UTC)
    entry_time = Column(DateTime, nullable=False, index=True)  # UTC
    exit_time = Column(DateTime, nullable=True)  # UTC
    created_at = Column(DateTime, default=now_utc)  # UTC
    
    # Symbol & Strike Information
    symbol = Column(String(20), nullable=False, index=True)  # NIFTY, BANKNIFTY
    instrument_type = Column(String(10), nullable=False)  # CALL, PUT, FUTURE
    strike_price = Column(Float, nullable=True)  # Strike price for options
    expiry_date = Column(DateTime, nullable=True)
    
    # Entry Details
    entry_price = Column(Float, nullable=False)
    entry_order_id = Column(String(50), nullable=True)
    quantity = Column(Integer, nullable=False)  # Lot size
    entry_mode = Column(String(10), nullable=False)  # PAPER, LIVE
    
    # Exit Details
    exit_price = Column(Float, nullable=True)
    exit_order_id = Column(String(50), nullable=True)
    exit_type = Column(String(20), nullable=True)  # TARGET, STOP_LOSS, EOD, MANUAL, REVERSAL
    
    # P&L Calculation
    gross_pnl = Column(Float, nullable=True)  # Before costs
    brokerage = Column(Float, default=0.0)
    taxes = Column(Float, default=0.0)
    net_pnl = Column(Float, nullable=True)  # After all costs
    pnl_percentage = Column(Float, nullable=True)  # Return %
    
    # Strategy Information
    strategy_name = Column(String(100), nullable=False, index=True)
    strategy_weight = Column(Integer, nullable=True)
    signal_strength = Column(Float, nullable=True)  # 0-100
    ml_score = Column(Float, nullable=True)  # ML model confidence
    
    # ML Telemetry (for traceability)
    model_version = Column(String(50), nullable=True)  # e.g., "v1.0.0"
    model_hash = Column(String(50), nullable=True)  # Hash of model file
    features_snapshot = Column(JSON, nullable=True)  # Dict of features used for prediction
    
    # Market Context (at entry)
    spot_price_entry = Column(Float, nullable=True)
    iv_entry = Column(Float, nullable=True)  # Implied Volatility %
    vix_entry = Column(Float, nullable=True)
    pcr_entry = Column(Float, nullable=True)  # Put-Call Ratio
    
    # Market Regime (at entry)
    market_regime_entry = Column(String(50), nullable=True)  # TRENDING, RANGING, VOLATILE, CALM
    regime_confidence = Column(Float, nullable=True)  # 0-1 confidence in regime classification
    
    # Time Context (at entry)
    entry_hour = Column(Integer, nullable=True)  # 0-23
    entry_minute = Column(Integer, nullable=True)  # 0-59
    day_of_week = Column(String(20), nullable=True)  # Monday, Tuesday, etc.
    is_expiry_day = Column(Boolean, nullable=True)  # True if trade entered on expiry day
    days_to_expiry = Column(Integer, nullable=True)  # Days until option expiry
    
    # Option Chain Data (at entry) - Critical for ML
    oi_entry = Column(BigInteger, nullable=True)  # Open Interest at entry
    volume_entry = Column(BigInteger, nullable=True)  # Volume at entry
    bid_entry = Column(Float, nullable=True)  # Bid price at entry
    ask_entry = Column(Float, nullable=True)  # Ask price at entry
    spread_entry = Column(Float, nullable=True)  # Bid-Ask spread % at entry
    
    # Option Chain Data (at exit) - Critical for ML
    oi_exit = Column(BigInteger, nullable=True)  # Open Interest at exit
    volume_exit = Column(BigInteger, nullable=True)  # Volume at exit
    bid_exit = Column(Float, nullable=True)  # Bid price at exit
    ask_exit = Column(Float, nullable=True)  # Ask price at exit
    spread_exit = Column(Float, nullable=True)  # Bid-Ask spread % at exit
    
    # Market Context (at exit)
    spot_price_exit = Column(Float, nullable=True)
    iv_exit = Column(Float, nullable=True)
    vix_exit = Column(Float, nullable=True)
    pcr_exit = Column(Float, nullable=True)  # Put-Call Ratio at exit
    
    # Market Regime (at exit)
    market_regime_exit = Column(String(50), nullable=True)  # TRENDING, RANGING, VOLATILE, CALM
    
    # Time Context (at exit)
    exit_hour = Column(Integer, nullable=True)  # 0-23
    exit_minute = Column(Integer, nullable=True)  # 0-59
    
    # Greeks (at entry)
    delta_entry = Column(Float, nullable=True)
    gamma_entry = Column(Float, nullable=True)
    theta_entry = Column(Float, nullable=True)
    vega_entry = Column(Float, nullable=True)
    
    # Greeks (at exit) - Important for ML to understand Greek changes
    delta_exit = Column(Float, nullable=True)
    gamma_exit = Column(Float, nullable=True)
    theta_exit = Column(Float, nullable=True)
    vega_exit = Column(Float, nullable=True)
    
    # Position Management
    target_price = Column(Float, nullable=True)
    stop_loss_price = Column(Float, nullable=True)
    max_profit_reached = Column(Float, nullable=True)
    max_loss_reached = Column(Float, nullable=True)
    
    # Trade State
    status = Column(String(20), nullable=False, default="OPEN")  # OPEN, CLOSED, CANCELLED
    is_winning_trade = Column(Boolean, nullable=True)
    hold_duration_minutes = Column(Integer, nullable=True)
    
    # Additional Metadata
    signal_reason = Column(Text, nullable=True)  # Strategy reasoning
    exit_reason = Column(Text, nullable=True)  # Why exit was taken
    notes = Column(Text, nullable=True)  # Manual notes
    tags = Column(String(200), nullable=True)  # Comma-separated tags
    
    # Risk Metrics
    risk_amount = Column(Float, nullable=True)  # Amount risked
    risk_reward_ratio = Column(Float, nullable=True)
    position_size_pct = Column(Float, nullable=True)  # % of capital
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_entry_time', 'entry_time'),
        Index('idx_symbol_strategy', 'symbol', 'strategy_name'),
        Index('idx_status_entry_time', 'status', 'entry_time'),
        Index('idx_pnl', 'net_pnl'),
    )
    
    def calculate_pnl(self):
        """Calculate P&L when trade is closed"""
        if self.exit_price and self.entry_price:
            if self.instrument_type in ["CALL", "PUT"]:
                # Options P&L
                self.gross_pnl = (self.exit_price - self.entry_price) * self.quantity
            else:
                # Futures P&L
                self.gross_pnl = (self.exit_price - self.entry_price) * self.quantity
            
            # Calculate net P&L
            self.net_pnl = self.gross_pnl - self.brokerage - self.taxes
            
            # Calculate percentage return
            investment = self.entry_price * self.quantity
            if investment > 0:
                self.pnl_percentage = (self.net_pnl / investment) * 100
            
            # Determine if winning trade
            self.is_winning_trade = self.net_pnl > 0
            
            # Calculate hold duration - ensure both times are naive to avoid timezone errors
            if self.exit_time and self.entry_time:
                # Remove timezone info if present to allow subtraction
                exit_naive = self.exit_time.replace(tzinfo=None) if self.exit_time.tzinfo else self.exit_time
                entry_naive = self.entry_time.replace(tzinfo=None) if self.entry_time.tzinfo else self.entry_time
                duration = exit_naive - entry_naive
                self.hold_duration_minutes = int(duration.total_seconds() / 60)
    
    def to_dict(self):
        """Convert to dictionary for API responses"""
        # Convert timestamps to IST for display
        # Database stores naive timestamps in IST (timezone is Asia/Kolkata)
        entry_time_ist = None
        if self.entry_time:
            if self.entry_time.tzinfo is None:
                # Database timestamp is naive but in IST - add IST timezone
                entry_time_ist = self.entry_time.replace(tzinfo=IST).isoformat()
            else:
                entry_time_ist = self.entry_time.astimezone(IST).isoformat()
        
        exit_time_ist = None
        if self.exit_time:
            if self.exit_time.tzinfo is None:
                # Database timestamp is naive but in IST - add IST timezone
                exit_time_ist = self.exit_time.replace(tzinfo=IST).isoformat()
            else:
                exit_time_ist = self.exit_time.astimezone(IST).isoformat()
        
        return {
            "trade_id": self.trade_id,
            "entry_time": entry_time_ist,
            "exit_time": exit_time_ist,
            "symbol": self.symbol,
            "instrument_type": self.instrument_type,
            "strike_price": self.strike_price,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "quantity": self.quantity,
            "gross_pnl": self.gross_pnl,
            "net_pnl": self.net_pnl,
            "pnl_percentage": self.pnl_percentage,
            "strategy_name": self.strategy_name,
            "signal_strength": self.signal_strength,
            "status": self.status,
            "is_winning_trade": self.is_winning_trade,
            "hold_duration_minutes": self.hold_duration_minutes,
            "exit_type": self.exit_type,
            "signal_reason": self.signal_reason,
            "exit_reason": self.exit_reason,
        }




class DailyPerformance(Base):
    """Daily aggregated performance metrics"""
    __tablename__ = "daily_performance"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(DateTime, nullable=False, unique=True, index=True)
    
    # Trade Statistics
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    win_rate = Column(Float, nullable=True)  # %
    
    # P&L Statistics
    gross_pnl = Column(Float, default=0.0)
    net_pnl = Column(Float, default=0.0)
    total_brokerage = Column(Float, default=0.0)
    total_taxes = Column(Float, default=0.0)
    
    # Performance Metrics
    max_profit = Column(Float, nullable=True)
    max_loss = Column(Float, nullable=True)
    average_profit = Column(Float, nullable=True)
    average_loss = Column(Float, nullable=True)
    profit_factor = Column(Float, nullable=True)  # Gross profit / Gross loss
    
    # Risk Metrics
    max_drawdown = Column(Float, nullable=True)
    sharpe_ratio = Column(Float, nullable=True)
    
    # Strategy Breakdown (JSON or separate table)
    best_strategy = Column(String(100), nullable=True)
    worst_strategy = Column(String(100), nullable=True)
    
    # Market Context
    nifty_open = Column(Float, nullable=True)
    nifty_close = Column(Float, nullable=True)
    nifty_change_pct = Column(Float, nullable=True)
    average_vix = Column(Float, nullable=True)
    
    def calculate_metrics(self):
        """Calculate derived metrics"""
        if self.total_trades > 0:
            self.win_rate = (self.winning_trades / self.total_trades) * 100
        
        if self.winning_trades > 0 and self.average_profit:
            total_profit = self.average_profit * self.winning_trades
            if self.losing_trades > 0 and self.average_loss:
                total_loss = abs(self.average_loss) * self.losing_trades
                if total_loss > 0:
                    self.profit_factor = total_profit / total_loss
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            "date": self.date.strftime("%Y-%m-%d") if self.date else None,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": self.win_rate,
            "net_pnl": self.net_pnl,
            "max_profit": self.max_profit,
            "max_loss": self.max_loss,
            "profit_factor": self.profit_factor,
            "best_strategy": self.best_strategy,
            "worst_strategy": self.worst_strategy,
        }


class StrategyPerformance(Base):
    """Strategy-wise performance tracking"""
    __tablename__ = "strategy_performance"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    strategy_name = Column(String(100), nullable=False, index=True)
    date = Column(DateTime, nullable=False, index=True)
    
    # Trade counts
    total_signals = Column(Integer, default=0)
    trades_taken = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    
    # Performance
    total_pnl = Column(Float, default=0.0)
    win_rate = Column(Float, nullable=True)
    average_pnl_per_trade = Column(Float, nullable=True)
    
    # Quality metrics
    average_signal_strength = Column(Float, nullable=True)
    average_ml_score = Column(Float, nullable=True)
    average_hold_duration = Column(Integer, nullable=True)  # minutes
    
    __table_args__ = (
        Index('idx_strategy_date', 'strategy_name', 'date'),
    )
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            "strategy_name": self.strategy_name,
            "date": self.date.strftime("%Y-%m-%d") if self.date else None,
            "total_signals": self.total_signals,
            "trades_taken": self.trades_taken,
            "winning_trades": self.winning_trades,
            "win_rate": self.win_rate,
            "total_pnl": self.total_pnl,
            "average_signal_strength": self.average_signal_strength,
        }


class Settings(Base):
    """User settings for trading configuration"""
    __tablename__ = "settings"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(50), nullable=False, default="default", unique=True, index=True)
    
    # Trading Configuration (JSON)
    trading_config = Column(JSON, nullable=False)
    # {capital, max_trades_per_day, max_positions, trade_amount, commission}
    
    # Risk Management (JSON)
    risk_config = Column(JSON, nullable=False)
    # {max_drawdown_pct, daily_loss_limit_pct, per_trade_risk_pct, stop_loss_type, position_sizing_method}
    
    # Strategy Weights (JSON)
    strategy_weights = Column(JSON, nullable=False)
    # {oi_buildup: 85, oi_unwinding: 80, ...} (0-100 for each strategy)
    
    # ML Configuration (JSON)
    ml_config = Column(JSON, nullable=False)
    # {min_ml_score, min_strategy_strength, min_strategies_agree, retrain_frequency_days}
    
    # System Configuration (JSON)
    system_config = Column(JSON, nullable=False)
    # {refresh_rate_seconds, log_level, trading_mode}
    
    # Metadata
    created_at = Column(DateTime, default=lambda: now_ist().replace(tzinfo=None))
    updated_at = Column(DateTime, default=lambda: now_ist().replace(tzinfo=None), onupdate=lambda: now_ist().replace(tzinfo=None))
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            "user_id": self.user_id,
            "trading": self.trading_config,
            "risk": self.risk_config,
            "strategies": self.strategy_weights,
            "ml": self.ml_config,
            "system": self.system_config,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class Capital(Base):
    """Capital tracking for P&L calculations"""
    __tablename__ = "capital"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(50), nullable=False, default="default", unique=True, index=True)
    
    # Capital amounts
    starting_capital = Column(Float, nullable=False, default=100000.0)
    current_capital = Column(Float, nullable=False, default=100000.0)
    
    # Daily snapshots
    capital_snapshot_date = Column(DateTime, nullable=True, index=True)
    daily_starting_capital = Column(Float, nullable=True)  # Capital at market open today
    
    # Metadata
    created_at = Column(DateTime, default=lambda: now_ist().replace(tzinfo=None))
    updated_at = Column(DateTime, default=lambda: now_ist().replace(tzinfo=None), onupdate=lambda: now_ist().replace(tzinfo=None))
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            "user_id": self.user_id,
            "starting_capital": self.starting_capital,
            "current_capital": self.current_capital,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class WatchlistRecommendation(Base):
    """Track watchlist recommendations for win rate calculation"""
    __tablename__ = "watchlist_recommendations"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Recommendation details
    symbol = Column(String(20), nullable=False, index=True)  # NIFTY, BANKNIFTY
    strike_price = Column(Float, nullable=False)
    direction = Column(String(10), nullable=False)  # CALL or PUT
    expiry_date = Column(DateTime, nullable=False)
    
    # Recommendation metrics
    composite_score = Column(Float, nullable=False)  # 0-100
    ml_score = Column(Float, nullable=True)  # 0-1
    signal_strength = Column(Float, nullable=True)  # 0-100
    num_strategies = Column(Integer, nullable=True)  # Number of strategies agreeing
    risk_reward_ratio = Column(Float, nullable=True)
    
    # Entry parameters
    recommended_entry = Column(Float, nullable=False)
    recommended_target = Column(Float, nullable=True)
    recommended_sl = Column(Float, nullable=True)
    
    # Recommendation metadata
    recommended_at = Column(DateTime, nullable=False, default=lambda: now_ist().replace(tzinfo=None), index=True)
    reasons = Column(JSON, nullable=True)  # List of strategy reasons
    
    # Outcome tracking
    outcome = Column(String(20), nullable=True, index=True)  # WIN, LOSS, PENDING, EXPIRED, CANCELLED
    actual_entry = Column(Float, nullable=True)
    actual_exit = Column(Float, nullable=True)
    pnl = Column(Float, nullable=True)
    pnl_pct = Column(Float, nullable=True)
    exit_time = Column(DateTime, nullable=True)
    exit_reason = Column(String(50), nullable=True)  # TARGET, SL, MANUAL, EXPIRED
    
    # Link to trade (if taken)
    trade_id = Column(String(50), nullable=True, index=True)
    
    # Metadata
    created_at = Column(DateTime, default=lambda: now_ist().replace(tzinfo=None))
    updated_at = Column(DateTime, default=lambda: now_ist().replace(tzinfo=None), onupdate=lambda: now_ist().replace(tzinfo=None))
    
    __table_args__ = (
        Index('idx_symbol_strike_expiry', 'symbol', 'strike_price', 'expiry_date'),
        Index('idx_outcome_time', 'outcome', 'recommended_at'),
    )
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            "id": self.id,
            "symbol": self.symbol,
            "strike": self.strike_price,
            "direction": self.direction,
            "composite_score": self.composite_score,
            "ml_score": self.ml_score,
            "recommended_entry": self.recommended_entry,
            "recommended_target": self.recommended_target,
            "recommended_sl": self.recommended_sl,
            "recommended_at": self.recommended_at.isoformat() if self.recommended_at else None,
            "outcome": self.outcome,
            "pnl": self.pnl,
            "pnl_pct": self.pnl_pct,
            "reasons": self.reasons
        }


class OptionSnapshot(Base):
    """
    Historical option chain snapshots with Greeks
    Used for ML training to correlate option data with trade outcomes
    STORAGE: All timestamps stored in UTC (raw)
    """
    __tablename__ = "option_chain_snapshots"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, index=True)  # UTC
    
    # Instrument identification
    symbol = Column(String(20), nullable=False, index=True)  # NIFTY, SENSEX
    strike_price = Column(Float, nullable=False)
    option_type = Column(String(4), nullable=False)  # CALL or PUT
    expiry = Column(DateTime, nullable=False)  # UTC
    
    # Market data
    ltp = Column(Float, nullable=True)
    bid = Column(Float, nullable=True)
    ask = Column(Float, nullable=True)
    volume = Column(BigInteger, nullable=True)
    oi = Column(BigInteger, nullable=True)
    oi_change = Column(BigInteger, nullable=True)
    
    # Greeks (calculated or from API)
    delta = Column(Float, nullable=True)
    gamma = Column(Float, nullable=True)
    theta = Column(Float, nullable=True)
    vega = Column(Float, nullable=True)
    iv = Column(Float, nullable=True)  # Implied Volatility
    
    # Underlying context
    spot_price = Column(Float, nullable=True)
    
    # Indexes for efficient queries
    __table_args__ = (
        Index('idx_snapshot_symbol_time', 'symbol', 'timestamp'),
        Index('idx_snapshot_strike_type', 'symbol', 'strike_price', 'option_type'),
    )

class Position(Base):
    """
    Active open positions - persisted across restarts
    When a trade is opened, create a Position record
    When closed, update the Trade record and delete Position
    """
    __tablename__ = "positions"
    
    # Primary identification
    id = Column(Integer, primary_key=True, autoincrement=True)
    position_id = Column(String(50), unique=True, nullable=False, index=True)
    
    # Timestamps (stored in UTC)
    entry_time = Column(DateTime, nullable=False, index=True)  # UTC
    last_updated = Column(DateTime, default=now_utc, onupdate=now_utc)  # UTC
    
    # Symbol & Strike Information
    symbol = Column(String(20), nullable=False, index=True)
    instrument_type = Column(String(10), nullable=False)  # CALL, PUT
    strike_price = Column(Float, nullable=True)
    expiry = Column(DateTime, nullable=True)
    direction = Column(String(10), nullable=False)  # BUY, SELL
    
    # Entry Details
    entry_price = Column(Float, nullable=False)
    quantity = Column(Integer, nullable=False)
    entry_value = Column(Float, nullable=False)  # entry_price * quantity
    
    # Risk Management
    stop_loss = Column(Float, nullable=True)
    target = Column(Float, nullable=True)
    trailing_sl = Column(Float, nullable=True)
    
    # Current Status
    current_price = Column(Float, nullable=True)
    unrealized_pnl = Column(Float, default=0.0)
    unrealized_pnl_pct = Column(Float, default=0.0)
    
    # Strategy & Metadata
    strategy_name = Column(String(100), nullable=True)
    signal_strength = Column(Float, nullable=True)
    ml_score = Column(Float, nullable=True)
    
    # Upstox Order Details
    order_id = Column(String(100), nullable=True)
    instrument_token = Column(String(50), nullable=True)
    
    # Greeks at entry (if available)
    delta_entry = Column(Float, nullable=True)
    gamma_entry = Column(Float, nullable=True)
    theta_entry = Column(Float, nullable=True)
    vega_entry = Column(Float, nullable=True)
    
    # Position metadata (use different name to avoid SQLAlchemy conflict)
    position_metadata = Column(JSON, nullable=True)  # Additional position data
    
    # Indexes for faster queries
    __table_args__ = (
        Index('idx_position_symbol_active', 'symbol', 'entry_time'),
        Index('idx_position_entry_time', 'entry_time'),
    )
    
    def to_dict(self):
        """Convert to dictionary"""
        # Convert naive timestamps to IST-aware for API responses
        entry_time_ist = None
        if self.entry_time:
            if self.entry_time.tzinfo is None:
                entry_time_ist = self.entry_time.replace(tzinfo=IST).isoformat()
            else:
                entry_time_ist = self.entry_time.astimezone(IST).isoformat()
        
        last_updated_ist = None
        if self.last_updated:
            if self.last_updated.tzinfo is None:
                last_updated_ist = self.last_updated.replace(tzinfo=IST).isoformat()
            else:
                last_updated_ist = self.last_updated.astimezone(IST).isoformat()
        
        data = {
            "position_id": self.position_id,
            "symbol": self.symbol,
            "instrument_type": self.instrument_type,
            "strike_price": self.strike_price,
            "expiry": self.expiry.isoformat() if self.expiry else None,
            "direction": self.direction,
            "entry_price": self.entry_price,
            "quantity": self.quantity,
            "entry_value": self.entry_value,
            "current_price": self.current_price,
            "unrealized_pnl": self.unrealized_pnl,
            "unrealized_pnl_pct": self.unrealized_pnl_pct,
            "target_price": self.target,
            "stop_loss": self.stop_loss,
            "trailing_sl": self.trailing_sl,
            "strategy_name": self.strategy_name,
            "signal_strength": self.signal_strength,
            "ml_score": self.ml_score,
            "entry_time": entry_time_ist,
            "last_updated": last_updated_ist,
            "order_id": self.order_id,
            "instrument_token": self.instrument_token,
            "delta_entry": self.delta_entry,
            "gamma_entry": self.gamma_entry,
            "theta_entry": self.theta_entry,
            "vega_entry": self.vega_entry,
            "position_metadata": self.position_metadata
        }

        # Surface instrument key stored inside metadata (legacy records)
        metadata = data.get("position_metadata") or {}
        instrument_key = metadata.get("instrument_key")
        if instrument_key:
            data["instrument_key"] = instrument_key

        return data


