"""
Base Strategy Class
All trading strategies inherit from this
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from datetime import datetime
from backend.core.logger import get_strategy_logger


class Signal:
    """Trading Signal with canonical strategy identification"""
    
    def __init__(
        self,
        strategy_name: str,
        symbol: str,
        direction: str,  # CALL or PUT
        action: str,  # BUY or SELL
        strike: float,
        expiry: str,
        entry_price: float,
        strength: float,  # 0-100
        reason: str,
        metadata: Dict[str, Any] = None,
        strategy_id: str = None,  # Canonical strategy identifier
        # Greeks and market data (can be passed directly or via metadata)
        delta: float = None,
        gamma: float = None,
        theta: float = None,
        vega: float = None,
        iv: float = None,
        oi: int = None,
        volume: int = None,
        bid: float = None,
        ask: float = None,
        spot_price: float = None
    ):
        self.strategy_name = strategy_name  # Human-readable name
        self.strategy_id = strategy_id  # Canonical ID for system use
        self.symbol = symbol
        self.direction = direction
        self.action = action
        self.strike = strike
        self.expiry = expiry
        self.entry_price = entry_price
        self.strength = strength
        self.reason = reason
        self.metadata = metadata or {}
        self.timestamp = datetime.now()
        self.ml_probability = 0.0
        self.ml_confidence = 0.0
        self.model_version: Optional[str] = None
        self.model_hash: Optional[str] = None
        self.features_snapshot: Dict[str, Any] = {}
        self.multi_timeframe_snapshot: Dict[str, Any] = {}
        self.strategy_weight: float = 0.0
        self.ensemble_weight: float = 0.0
        self.target_price = 0.0
        self.stop_loss = 0.0
        
        # Greeks and option chain data (prioritize direct parameters over metadata)
        self.delta = delta if delta is not None else (metadata.get('delta', 0.0) if metadata else 0.0)
        self.gamma = gamma if gamma is not None else (metadata.get('gamma', 0.0) if metadata else 0.0)
        self.theta = theta if theta is not None else (metadata.get('theta', 0.0) if metadata else 0.0)
        self.vega = vega if vega is not None else (metadata.get('vega', 0.0) if metadata else 0.0)
        self.iv = iv if iv is not None else (metadata.get('iv', 20.0) if metadata else 20.0)
        self.oi = oi if oi is not None else (metadata.get('oi', 0) if metadata else 0)
        self.volume = volume if volume is not None else (metadata.get('volume', 0) if metadata else 0)
        self.bid = bid if bid is not None else (metadata.get('bid', 0.0) if metadata else 0.0)
        self.ask = ask if ask is not None else (metadata.get('ask', 0.0) if metadata else 0.0)
        self.ltp = metadata.get('ltp', entry_price) if metadata else entry_price
        self.spot_price = spot_price if spot_price is not None else (metadata.get('spot_price', 0.0) if metadata else 0.0)
        
        # Auto-normalize strategy_id if not provided
        if not self.strategy_id:
            from backend.strategies.strategy_mappings import normalize_strategy_name
            self.strategy_id = normalize_strategy_name(self.strategy_name)
        
    def to_dict(self) -> Dict:
        """Convert signal to dictionary with canonical strategy_id"""
        return {
            'strategy': self.strategy_name,  # Human-readable for display
            'strategy_id': self.strategy_id,  # Canonical ID for system use
            'symbol': self.symbol,
            'direction': self.direction,
            'action': self.action,
            'strike': self.strike,
            'expiry': self.expiry,
            'entry_price': self.entry_price,
            'target_price': self.target_price,
            'stop_loss': self.stop_loss,
            'strength': self.strength,
            'ml_probability': self.ml_probability,
            'reason': self.reason,
            'timestamp': self.timestamp.isoformat(),
            'metadata': self.metadata,
            'strategy_weight': self.strategy_weight,
            'ml_confidence': self.ml_confidence,
            'model_version': self.model_version,
            'model_hash': self.model_hash,
            'features_snapshot': self.features_snapshot,
            'multi_timeframe_snapshot': self.multi_timeframe_snapshot,
            'ensemble_weight': self.ensemble_weight,
            # Greeks and option data
            'delta': self.delta,
            'gamma': self.gamma,
            'theta': self.theta,
            'vega': self.vega,
            'iv': self.iv,
            'oi': self.oi,
            'volume': self.volume,
            'bid': self.bid,
            'ask': self.ask,
            'ltp': self.ltp,
            'spot_price': self.spot_price
        }


class BaseStrategy(ABC):
    """Base class for all trading strategies"""
    
    def __init__(self, name: str, weight: float = 1.0, strategy_id: str = None):
        self.name = name  # Human-readable name
        self.weight = weight  # Strategy importance weight
        self.default_weight = weight  # Preserve original weight for resets
        self.logger = get_strategy_logger(name)
        self.enabled = True
        self.last_signal_time = None
        self.cooldown_seconds = 300  # 5 minutes between signals
        
        # Canonical strategy ID for consistent tracking
        if strategy_id:
            self.strategy_id = strategy_id
        else:
            from backend.strategies.strategy_mappings import normalize_strategy_name
            self.strategy_id = normalize_strategy_name(name)
        
    @abstractmethod
    async def analyze(self, market_data: Dict) -> List[Signal]:
        """
        Analyze market data and generate signals
        
        Args:
            market_data: Current market state
            
        Returns:
            List of Signal objects
        """
        pass
    
    def can_generate_signal(self) -> bool:
        """Check if strategy can generate a new signal (cooldown check)"""
        if not self.enabled:
            return False
            
        if self.last_signal_time is None:
            return True
            
        time_since_last = (datetime.now() - self.last_signal_time).seconds
        return time_since_last >= self.cooldown_seconds
    
    def record_signal(self):
        """Record that a signal was generated"""
        self.last_signal_time = datetime.now()
    
    def extract_greeks_metadata(self, option_data: Dict, spot_price: float = 0, pcr: float = 0) -> Dict:
        """
        Extract Greeks and option data from option chain for ML features
        
        Args:
            option_data: Option data from option chain (calls/puts dict)
            spot_price: Current spot price
            pcr: Put-Call Ratio
            
        Returns:
            Metadata dict with Greeks and option data
        """
        return {
            'delta': option_data.get('delta', 0.0),
            'gamma': option_data.get('gamma', 0.0),
            'theta': option_data.get('theta', 0.0),
            'vega': option_data.get('vega', 0.0),
            'iv': option_data.get('iv', 20.0),
            'oi': option_data.get('oi', 0),
            'volume': option_data.get('volume', 0),
            'bid': option_data.get('bid', 0.0),
            'ask': option_data.get('ask', 0.0),
            'ltp': option_data.get('ltp', 0.0),
            'spot_price': spot_price,
            'pcr': pcr
        }
    
    def calculate_strength(self, score: float, max_score: float = 100) -> float:
        """
        Calculate signal strength (0-100)
        
        Args:
            score: Raw score from strategy
            max_score: Maximum possible score
            
        Returns:
            Normalized strength (0-100)
        """
        strength = (score / max_score) * 100
        return max(0, min(100, strength))  # Clamp between 0-100
    
    def calculate_targets(
        self,
        entry_price: float,
        strength: float,
        volatility: float,
        time_to_expiry_days: float
    ) -> tuple:
        """
        Calculate dynamic profit target and stop loss with multiple target levels
        
        Args:
            entry_price: Entry price of option
            strength: Signal strength (0-100)
            volatility: Implied volatility
            time_to_expiry_days: Days to expiry
            
        Returns:
            Dict with target levels: {
                'target_price': main target,
                'target_1': first partial (50%),
                'target_2': main target (100%),
                'target_3': stretch target (150%),
                'stop_loss': stop loss price
            }
            OR tuple (target_price, stop_loss) for backward compatibility
        """
        # Base target percentage - increased for intraday options trading
        base_target = 25  # 25% minimum target (was 10%)
        
        # Adjust based on signal strength
        if strength > 90:
            base_target = 50  # 50% for very strong signals (was 30%)
        elif strength > 80:
            base_target = 35  # 35% for strong signals (was 20%)
        
        # Adjust based on volatility
        if volatility > 25:
            base_target *= 1.5  # Higher targets in high volatility
        elif volatility < 15:
            base_target *= 0.9  # Slightly lower in low volatility (was 0.8)
        
        # Adjust based on time decay
        if time_to_expiry_days < 2:
            base_target *= 0.7  # Still aggressive near expiry but not too quick (was 0.5)
        
        # Calculate target and stop loss
        target_percent = base_target / 100
        stop_percent = 0.3  # 30% stop loss (unchanged)
        
        # Multiple target levels for partial exits
        target_1 = entry_price * (1 + target_percent * 0.5)  # T1: 50% of main target
        target_2 = entry_price * (1 + target_percent)        # T2: Main target
        target_3 = entry_price * (1 + target_percent * 1.5)  # T3: 150% of main target
        
        stop_loss = entry_price * (1 - stop_percent)
        
        # Store in tuple for backward compatibility, but add attributes
        class TargetTuple(tuple):
            """Tuple that also has dict-like attributes"""
            def __new__(cls, target, sl, t1, t2, t3):
                instance = super().__new__(cls, (target, sl))
                instance.target_1 = t1
                instance.target_2 = t2
                instance.target_3 = t3
                instance.stop_loss = sl
                return instance
        
        return TargetTuple(target_2, stop_loss, target_1, target_2, target_3)

    def log_analysis(self, message: str, level: str = "info"):
        """Log strategy analysis"""
        if level == "debug":
            self.logger.debug(f"[{self.name}] {message}")
        elif level == "warning":
            self.logger.warning(f"[{self.name}] {message}")
        elif level == "error":
            self.logger.error(f"[{self.name}] {message}")
        else:
            self.logger.info(f"[{self.name}] {message}")

    # ------------------------------------------------------------------
    # Dynamic threshold helpers (long-term improvement scaffolding)
    # ------------------------------------------------------------------
    def get_volatility_context(self, symbol_data: Dict) -> Dict[str, Any]:
        """Extract volatility and trend context from market data for dynamic thresholds."""
        indicators = symbol_data.get('technical_indicators', {}) or {}
        multi_tf = symbol_data.get('multi_timeframe', {}) or {}

        return {
            'atr': indicators.get('atr'),
            'volatility': indicators.get('volatility'),
            'returns_1d': indicators.get('returns_1d'),
            'returns_5d': indicators.get('returns_5d'),
            'mtf': multi_tf,
        }

    def scale_threshold(
        self,
        base_value: float,
        volatility: Optional[float],
        neutral: float = 20.0,
        sensitivity: float = 0.5,
        minimum: Optional[float] = None,
        maximum: Optional[float] = None
    ) -> float:
        """Scale a threshold based on volatility context with optional bounds."""
        if volatility is None:
            return base_value

        delta_ratio = (volatility - neutral) / neutral if neutral else 0
        adjusted = base_value * (1 + delta_ratio * sensitivity)

        if minimum is not None:
            adjusted = max(minimum, adjusted)
        if maximum is not None:
            adjusted = min(maximum, adjusted)

        return adjusted

    # ------------------------------------------------------------------
    # Multi-timeframe Trend Analysis (for all strategies)
    # ------------------------------------------------------------------
    def get_trend_bias(self, multi_timeframe: Dict) -> str:
        """
        Analyze multi-timeframe data to determine overall trend bias.
        Used by all strategies to filter/boost signals based on trend.
        
        Returns: 'strongly_bullish', 'bullish', 'neutral', 'bearish', 'strongly_bearish', or 'unknown'
        """
        if not multi_timeframe:
            return 'unknown'
        
        bullish_count = 0
        bearish_count = 0
        total_timeframes = 0
        
        for timeframe, indicators in multi_timeframe.items():
            total_timeframes += 1
            trend = indicators.get('trend', 'neutral')
            rsi = indicators.get('rsi')
            macd_histogram = indicators.get('macd_histogram')
            
            # Count trend signals
            if trend == 'bullish':
                bullish_count += 1
            elif trend == 'bearish':
                bearish_count += 1
            
            # Add RSI confirmation (half weight)
            if rsi:
                if rsi > 60:
                    bullish_count += 0.5
                elif rsi < 40:
                    bearish_count += 0.5
            
            # Add MACD confirmation (half weight)
            if macd_histogram:
                if macd_histogram > 0:
                    bullish_count += 0.5
                elif macd_histogram < 0:
                    bearish_count += 0.5
        
        if total_timeframes == 0:
            return 'unknown'
        
        # Strong bias: >70% of indicators agree
        strong_threshold = total_timeframes * 1.4  # 70% of max possible (2x per timeframe)
        moderate_threshold = total_timeframes * 0.8  # 40% of max possible
        
        if bullish_count >= strong_threshold:
            return 'strongly_bullish'
        elif bullish_count >= moderate_threshold:
            return 'bullish'
        elif bearish_count >= strong_threshold:
            return 'strongly_bearish'
        elif bearish_count >= moderate_threshold:
            return 'bearish'
        else:
            return 'neutral'
    
    def check_trend_confirmation(self, multi_timeframe: Dict, signal_direction: str) -> tuple:
        """
        Check if multi-timeframe trend confirms the signal direction.
        Returns (should_skip: bool, strength_multiplier: float)
        
        Args:
            multi_timeframe: Multi-timeframe technical indicators
            signal_direction: 'bullish' or 'bearish'
            
        Returns:
            (should_skip, multiplier): Skip signal if True, apply multiplier to strength
        """
        trend = self.get_trend_bias(multi_timeframe)
        
        # Skip signals that strongly oppose the trend
        if signal_direction == 'bullish' and trend == 'strongly_bearish':
            return (True, 0.0)
        elif signal_direction == 'bearish' and trend == 'strongly_bullish':
            return (True, 0.0)
        
        # Boost signals that align with trend
        if signal_direction == 'bullish':
            if trend == 'strongly_bullish':
                return (False, 1.3)  # 30% boost for strong confirmation
            elif trend == 'bullish':
                return (False, 1.2)  # 20% boost for moderate confirmation
            elif trend == 'neutral':
                return (False, 0.95)  # Slight reduction for neutral
            elif trend == 'bearish':
                return (False, 0.85)  # Reduce for opposing trend
            else:  # strongly_bearish handled above
                return (False, 1.0)
        
        elif signal_direction == 'bearish':
            if trend == 'strongly_bearish':
                return (False, 1.3)  # 30% boost for strong confirmation
            elif trend == 'bearish':
                return (False, 1.2)  # 20% boost for moderate confirmation
            elif trend == 'neutral':
                return (False, 0.95)  # Slight reduction for neutral
            elif trend == 'bullish':
                return (False, 0.85)  # Reduce for opposing trend
            else:  # strongly_bullish handled above
                return (False, 1.0)
        
        return (False, 1.0)  # Default: no change

    def shift_threshold(
        self,
        base_value: float,
        volatility: Optional[float],
        neutral: float = 20.0,
        sensitivity: float = 0.1,
        minimum: Optional[float] = None,
        maximum: Optional[float] = None
    ) -> float:
        """Shift a threshold up or down based on volatility context."""
        if volatility is None:
            return base_value

        delta_ratio = (volatility - neutral) / neutral if neutral else 0
        adjusted = base_value + (delta_ratio * sensitivity)

        if minimum is not None:
            adjusted = max(minimum, adjusted)
        if maximum is not None:
            adjusted = min(maximum, adjusted)

        return adjusted
