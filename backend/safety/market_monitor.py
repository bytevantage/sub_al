"""
Market Monitor - Circuit Breakers for Market Shocks
Monitors market conditions and triggers circuit breakers on extreme events
"""

import asyncio
from typing import Dict, Optional, Callable, List
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from collections import deque
from enum import Enum

from backend.core.logger import get_logger

# IST timezone for market hours
IST = ZoneInfo("Asia/Kolkata")

logger = get_logger(__name__)


class MarketCondition(Enum):
    """Market condition states"""
    NORMAL = "normal"
    ELEVATED = "elevated"       # VIX 25-40
    HIGH_STRESS = "high_stress"  # VIX 40-60
    EXTREME = "extreme"          # VIX >60
    HALTED = "halted"            # Market halted


class MarketMonitor:
    """
    Monitors market conditions and triggers circuit breakers
    
    Features:
    - VIX spike detection
    - Market halt detection
    - IV shock detection
    - Auto position squaring
    - Market condition alerts
    """
    
    def __init__(self, config: Dict, circuit_breaker=None):
        self.config = config
        self.circuit_breaker = circuit_breaker
        
        # Thresholds
        self.vix_elevated = config.get('vix_elevated', 25)
        self.vix_high_stress = config.get('vix_high_stress', 40)
        self.vix_extreme = config.get('vix_extreme', 60)
        self.iv_shock_percent = config.get('iv_shock_percent', 50)
        self.iv_shock_window_minutes = config.get('iv_shock_window_minutes', 5)
        
        # VIX tracking
        self.current_vix = None
        self.vix_history = deque(maxlen=100)
        self.last_vix_check = None
        
        # IV tracking per symbol
        self.iv_history = {}
        
        # Market state
        self.market_condition = MarketCondition.NORMAL
        self.is_market_halted = False
        self.halt_detected_at = None
        
        # Callbacks
        self.shock_callbacks = []
        max_recent = int(self.config.get('max_recent_shocks', 50) or 50)
        self.recent_shocks = deque(maxlen=max_recent)
        
        # Auto-square settings
        self.auto_square_on_extreme = config.get('auto_square_on_extreme', False)
        self.auto_square_on_halt = config.get('auto_square_on_halt', True)
        
    def register_shock_callback(self, callback: Callable):
        """Register callback for market shock events"""
        self.shock_callbacks.append(callback)
        
    async def update_vix(self, vix: float):
        """
        Update VIX value and check for spikes
        
        Args:
            vix: Current VIX value
        """
        self.last_vix_check = datetime.now()
        previous_vix = self.current_vix
        self.current_vix = vix
        
        self.vix_history.append({
            'vix': vix,
            'timestamp': self.last_vix_check
        })
        
        # Determine market condition
        old_condition = self.market_condition
        
        if vix >= self.vix_extreme:
            self.market_condition = MarketCondition.EXTREME
        elif vix >= self.vix_high_stress:
            self.market_condition = MarketCondition.HIGH_STRESS
        elif vix >= self.vix_elevated:
            self.market_condition = MarketCondition.ELEVATED
        else:
            self.market_condition = MarketCondition.NORMAL
            
        # Log condition changes
        if old_condition != self.market_condition:
            logger.warning(
                f"⚠️ Market condition changed: {old_condition.value} → {self.market_condition.value}\n"
                f"VIX: {vix:.2f}"
            )
            
        # Check for VIX spike (circuit breaker trigger)
        if self.market_condition in [MarketCondition.HIGH_STRESS, MarketCondition.EXTREME]:
            await self._handle_vix_spike(vix, previous_vix)
            
        # Check for sudden VIX jump
        if previous_vix and vix > previous_vix * 1.5:
            logger.warning(
                f"⚠️ VIX spike detected: {previous_vix:.2f} → {vix:.2f} "
                f"({(vix/previous_vix - 1)*100:.1f}% increase)"
            )
            
    async def _handle_vix_spike(self, vix: float, previous_vix: Optional[float]):
        """Handle VIX spike event"""
        
        if self.circuit_breaker:
            # Trip circuit breaker
            self.circuit_breaker.check_vix_spike(vix)
            
        # Trigger callbacks
        await self._trigger_shock_callbacks({
            'type': 'vix_spike',
            'vix': vix,
            'previous_vix': previous_vix,
            'condition': self.market_condition.value,
            'timestamp': datetime.now().isoformat()
        })
        
        # Auto-square on extreme conditions
        if self.market_condition == MarketCondition.EXTREME and self.auto_square_on_extreme:
            logger.critical("🚨 EXTREME VIX - Auto-squaring all positions")
            await self._auto_square_positions("extreme_vix")
            
    async def check_iv_shock(self, symbol: str, current_iv: float) -> bool:
        """
        Check for IV shock on a symbol
        
        Args:
            symbol: Instrument symbol
            current_iv: Current implied volatility
            
        Returns:
            True if IV shock detected
        """
        # Initialize history for symbol
        if symbol not in self.iv_history:
            self.iv_history[symbol] = deque(maxlen=100)
            
        now = datetime.now()
        
        # Add current IV
        self.iv_history[symbol].append({
            'iv': current_iv,
            'timestamp': now
        })
        
        # Need historical data to detect shock
        if len(self.iv_history[symbol]) < 2:
            return False
            
        # Get IV from N minutes ago
        cutoff_time = now - timedelta(minutes=self.iv_shock_window_minutes)
        
        historical_ivs = [
            entry['iv'] for entry in self.iv_history[symbol]
            if entry['timestamp'] >= cutoff_time
        ]
        
        if not historical_ivs:
            return False
            
        min_iv = min(historical_ivs)
        max_iv = max(historical_ivs)
        
        # Check for shock (>50% change)
        if min_iv > 0:
            iv_change_percent = (max_iv - min_iv) / min_iv * 100
            
            if iv_change_percent >= self.iv_shock_percent:
                logger.critical(
                    f"🚨 IV SHOCK DETECTED: {symbol}\n"
                    f"IV change: {min_iv:.1f}% → {max_iv:.1f}% "
                    f"({iv_change_percent:.1f}% change in {self.iv_shock_window_minutes} min)"
                )
                
                if self.circuit_breaker:
                    self.circuit_breaker.check_iv_shock(current_iv, min_iv)
                    
                # Trigger callbacks
                await self._trigger_shock_callbacks({
                    'type': 'iv_shock',
                    'symbol': symbol,
                    'min_iv': min_iv,
                    'max_iv': max_iv,
                    'change_percent': iv_change_percent,
                    'timestamp': now.isoformat()
                })
                
                return True
                
        return False
        
    async def check_market_halt(self, nse_status: Optional[Dict] = None) -> bool:
        """
        Check if market is halted
        
        Args:
            nse_status: Optional NSE status dict with 'is_open' flag
            
        Returns:
            True if market halted
        """
        # Check NSE status if provided
        if nse_status:
            is_open = nse_status.get('is_open', True)
            
            if not is_open and not self.is_market_halted:
                # Market just halted
                self.is_market_halted = True
                self.halt_detected_at = datetime.now()
                self.market_condition = MarketCondition.HALTED
                
                logger.critical(
                    "🚨 MARKET HALT DETECTED 🚨\n"
                    "NSE trading halted"
                )
                
                if self.circuit_breaker:
                    self.circuit_breaker.trip(
                        trigger=self.circuit_breaker.__class__.__dict__.get(
                            'CircuitBreakerTrigger', type('obj', (object,), {})
                        ).MARKET_HALT,
                        reason="NSE market halt detected",
                        metadata={'halt_time': self.halt_detected_at.isoformat()}
                    )
                    
                # Trigger callbacks
                await self._trigger_shock_callbacks({
                    'type': 'market_halt',
                    'halt_time': self.halt_detected_at.isoformat(),
                    'timestamp': datetime.now().isoformat()
                })
                
                # Auto-square on halt
                if self.auto_square_on_halt:
                    logger.critical("Auto-squaring all positions due to market halt")
                    await self._auto_square_positions("market_halt")
                    
                return True
                
            elif is_open and self.is_market_halted:
                # Market resumed
                self.is_market_halted = False
                halt_duration = (datetime.now() - self.halt_detected_at).total_seconds() / 60
                
                logger.warning(
                    f"✅ Market resumed after {halt_duration:.1f} minute halt"
                )
                
        # Heuristic: Check if we've received any VIX updates recently
        # (if no updates for 5+ minutes during market hours, might be halted)
        if self.last_vix_check:
            minutes_since_update = (datetime.now(IST) - self.last_vix_check).total_seconds() / 60
            
            # During market hours (9:15 - 15:25 IST)
            now_time = datetime.now(IST).time()
            market_start = datetime.strptime("09:15", "%H:%M").time()
            market_end = datetime.strptime("15:25", "%H:%M").time()
            
            if market_start <= now_time <= market_end:
                if minutes_since_update > 5 and not self.is_market_halted:
                    logger.warning(
                        f"⚠️ No market data updates for {minutes_since_update:.1f} minutes\n"
                        "Possible market halt or data feed issue"
                    )
                    
        return self.is_market_halted
        
    async def _auto_square_positions(self, reason: str):
        """Auto-square all positions (requires position manager)"""
        logger.critical(f"Auto-squaring positions: {reason}")
        
        # Trigger callbacks to let main system handle position squaring
        await self._trigger_shock_callbacks({
            'type': 'auto_square',
            'reason': reason,
            'timestamp': datetime.now().isoformat()
        })
        
    async def _trigger_shock_callbacks(self, shock_data: Dict):
        """Trigger all registered shock callbacks"""
        # Maintain bounded history for dashboard queries
        self.recent_shocks.appendleft(shock_data)
        for callback in self.shock_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(shock_data)
                else:
                    callback(shock_data)
            except Exception as e:
                logger.error(f"Error in shock callback: {e}")
                
    def get_market_status(self) -> Dict:
        """Get current market status"""
        return {
            'condition': self.market_condition.value,
            'current_vix': self.current_vix,
            'is_market_halted': self.is_market_halted,
            'halt_detected_at': self.halt_detected_at.isoformat() if self.halt_detected_at else None,
            'last_vix_check': self.last_vix_check.isoformat() if self.last_vix_check else None,
            'thresholds': {
                'vix_elevated': self.vix_elevated,
                'vix_high_stress': self.vix_high_stress,
                'vix_extreme': self.vix_extreme,
                'iv_shock_percent': self.iv_shock_percent
            },
            'auto_square_settings': {
                'on_extreme': self.auto_square_on_extreme,
                'on_halt': self.auto_square_on_halt
            },
            'recent_shocks': list(self.recent_shocks)
        }

    def get_recent_shocks(self) -> List[Dict]:
        """Return recent market shock events for dashboards"""
        return list(self.recent_shocks)
        
    def get_vix_stats(self) -> Dict:
        """Get VIX statistics"""
        if not self.vix_history:
            return {'message': 'No VIX data available'}
            
        recent_vix = [entry['vix'] for entry in self.vix_history]
        
        return {
            'current': self.current_vix,
            'min': min(recent_vix),
            'max': max(recent_vix),
            'avg': sum(recent_vix) / len(recent_vix),
            'data_points': len(recent_vix)
        }
