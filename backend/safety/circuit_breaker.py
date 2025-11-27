"""
Circuit Breaker System
Handles automatic trading shutdown and emergency controls
"""

import asyncio
from datetime import datetime, time
from typing import Dict, List, Optional
from enum import Enum
import json
from pathlib import Path

from backend.core.logger import get_logger

logger = get_logger(__name__)


class CircuitBreakerStatus(Enum):
    """Circuit breaker states"""
    ACTIVE = "active"           # Normal trading
    TRIPPED = "tripped"         # Auto-disabled due to trigger
    EMERGENCY_STOP = "emergency_stop"  # Manual emergency stop
    MARKET_HALT = "market_halt"  # Exchange halted
    MANUAL_DISABLE = "manual_disable"  # Manually disabled


class CircuitBreakerTrigger(Enum):
    """Reasons for circuit breaker activation"""
    DAILY_LOSS_LIMIT = "daily_loss_limit"
    POSITION_LIMIT = "position_limit"
    VIX_SPIKE = "vix_spike"
    IV_SHOCK = "iv_shock"
    MARKET_HALT = "market_halt"
    DATA_FAILURE = "data_failure"
    ORDER_FAILURE = "order_failure"
    MANUAL_TRIGGER = "manual_trigger"
    EMERGENCY_STOP = "emergency_stop"


class CircuitBreaker:
    """
    Circuit breaker for automatic trading shutdown
    
    Features:
    - Auto-disable on daily loss limit
    - Emergency kill switch
    - Market shock detection
    - Manual override with logging
    - Persistent state across restarts
    """
    
    def __init__(self, config: Dict):
        self.config = config
        self.status = CircuitBreakerStatus.ACTIVE
        self.triggers: List[Dict] = []
        self.override_enabled = False
        self.state_file = Path("data/circuit_breaker_state.json")
        
        # Thresholds
        self.daily_loss_limit_percent = config.get('daily_loss_limit_percent', 3)
        self.max_positions = config.get('max_positions', 5)
        self.vix_threshold = config.get('vix_threshold', 40)
        self.iv_shock_threshold = config.get('iv_shock_percent', 50)
        
        # Load previous state
        self._load_state()
        
    def _load_state(self):
        """Load circuit breaker state from disk"""
        try:
            if self.state_file.exists():
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                    
                self.status = CircuitBreakerStatus(state.get('status', 'active'))
                self.triggers = state.get('triggers', [])
                self.override_enabled = state.get('override_enabled', False)
                
                logger.info(f"Loaded circuit breaker state: {self.status.value}")
                
                if self.status != CircuitBreakerStatus.ACTIVE:
                    logger.warning(
                        f"⚠️ Circuit breaker is {self.status.value}. "
                        f"Trading is DISABLED. Triggers: {len(self.triggers)}"
                    )
        except Exception as e:
            logger.error(f"Error loading circuit breaker state: {e}")
            
    def _save_state(self):
        """Persist circuit breaker state to disk"""
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            
            state = {
                'status': self.status.value,
                'triggers': self.triggers,
                'override_enabled': self.override_enabled,
                'last_updated': datetime.now().isoformat()
            }
            
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error saving circuit breaker state: {e}")
            
    def is_trading_allowed(self) -> bool:
        """Check if trading is currently allowed"""
        if self.status == CircuitBreakerStatus.ACTIVE:
            return True
            
        if self.override_enabled:
            logger.warning("⚠️ Trading with OVERRIDE enabled despite circuit breaker")
            return True
            
        return False

    def get_status(self) -> str:
        """Return current circuit breaker status string"""
        return self.status.value

    def get_active_triggers(self) -> List[Dict]:
        """Return list of active triggers"""
        return self.triggers

    def is_override_enabled(self) -> bool:
        """Return whether override mode is enabled"""
        return self.override_enabled
        
    def check_daily_loss(self, daily_pnl: float, initial_capital: float) -> bool:
        """
        Check if daily loss limit is breached
        
        Returns:
            True if circuit breaker tripped
        """
        if daily_pnl >= 0:
            return False
            
        loss_percent = abs(daily_pnl / initial_capital * 100)
        
        if loss_percent >= self.daily_loss_limit_percent:
            self.trip(
                trigger=CircuitBreakerTrigger.DAILY_LOSS_LIMIT,
                reason=f"Daily loss {loss_percent:.2f}% >= limit {self.daily_loss_limit_percent}%",
                metadata={
                    'daily_pnl': daily_pnl,
                    'loss_percent': loss_percent,
                    'limit': self.daily_loss_limit_percent
                }
            )
            return True
            
        # Warning at 80% of limit
        if loss_percent >= self.daily_loss_limit_percent * 0.8:
            logger.warning(
                f"⚠️ Daily loss at {loss_percent:.2f}% "
                f"({loss_percent/self.daily_loss_limit_percent*100:.0f}% of limit)"
            )
            
        return False
        
    def check_position_limit(self, num_positions: int) -> bool:
        """
        Check if position limit is breached
        
        Returns:
            True if circuit breaker tripped
        """
        if num_positions > self.max_positions:
            self.trip(
                trigger=CircuitBreakerTrigger.POSITION_LIMIT,
                reason=f"Open positions {num_positions} > limit {self.max_positions}",
                metadata={
                    'num_positions': num_positions,
                    'limit': self.max_positions
                }
            )
            return True
            
        return False
        
    def check_vix_spike(self, vix: float) -> bool:
        """
        Check for VIX spike (market stress)
        
        Returns:
            True if circuit breaker tripped
        """
        if vix > self.vix_threshold:
            self.trip(
                trigger=CircuitBreakerTrigger.VIX_SPIKE,
                reason=f"VIX spike: {vix:.2f} > threshold {self.vix_threshold}",
                metadata={'vix': vix, 'threshold': self.vix_threshold}
            )
            return True
            
        return False
        
    def check_iv_shock(self, current_iv: float, previous_iv: float) -> bool:
        """
        Check for sudden IV change (volatility shock)
        
        Returns:
            True if circuit breaker tripped
        """
        if previous_iv == 0:
            return False
            
        iv_change_percent = abs((current_iv - previous_iv) / previous_iv * 100)
        
        if iv_change_percent > self.iv_shock_threshold:
            self.trip(
                trigger=CircuitBreakerTrigger.IV_SHOCK,
                reason=f"IV shock: {iv_change_percent:.1f}% change",
                metadata={
                    'current_iv': current_iv,
                    'previous_iv': previous_iv,
                    'change_percent': iv_change_percent
                }
            )
            return True
            
        return False
        
    def trip(
        self,
        trigger: CircuitBreakerTrigger,
        reason: str,
        metadata: Optional[Dict] = None
    ):
        """
        Trip the circuit breaker
        
        Args:
            trigger: Reason for tripping
            reason: Human-readable explanation
            metadata: Additional context
        """
        if self.status == CircuitBreakerStatus.ACTIVE or trigger == CircuitBreakerTrigger.EMERGENCY_STOP:
            # Set appropriate status
            if trigger == CircuitBreakerTrigger.EMERGENCY_STOP:
                self.status = CircuitBreakerStatus.EMERGENCY_STOP
            elif trigger == CircuitBreakerTrigger.MARKET_HALT:
                self.status = CircuitBreakerStatus.MARKET_HALT
            else:
                self.status = CircuitBreakerStatus.TRIPPED
                
            # Record trigger
            trigger_record = {
                'trigger': trigger.value,
                'reason': reason,
                'timestamp': datetime.now().isoformat(),
                'metadata': metadata or {}
            }
            self.triggers.append(trigger_record)
            
            # Save state
            self._save_state()
            
            # Log critical alert
            logger.critical(
                f"🚨 CIRCUIT BREAKER TRIPPED 🚨\n"
                f"Status: {self.status.value}\n"
                f"Trigger: {trigger.value}\n"
                f"Reason: {reason}\n"
                f"Time: {datetime.now()}\n"
                f"Trading is now DISABLED"
            )
            
            # TODO: Send emergency notifications (email/SMS/Telegram)
            
    def emergency_stop(self, reason: str = "Manual emergency stop"):
        """
        Emergency kill switch - immediately stop all trading
        
        Args:
            reason: Reason for emergency stop
        """
        self.trip(
            trigger=CircuitBreakerTrigger.EMERGENCY_STOP,
            reason=reason,
            metadata={'manual': True}
        )
        
        logger.critical(
            "🛑 EMERGENCY STOP ACTIVATED 🛑\n"
            "All trading IMMEDIATELY STOPPED\n"
            f"Reason: {reason}"
        )
        
    def reset(self, reason: str, override_password: Optional[str] = None) -> bool:
        """
        Reset circuit breaker to allow trading
        
        Args:
            reason: Reason for reset
            override_password: Password for sensitive resets
            
        Returns:
            True if reset successful
        """
        # Validate override password for emergency stops
        if self.status == CircuitBreakerStatus.EMERGENCY_STOP:
            expected_password = self.config.get('override_password', 'OVERRIDE123')
            if override_password != expected_password:
                logger.error("❌ Invalid override password for emergency stop reset")
                return False
                
        old_status = self.status
        self.status = CircuitBreakerStatus.ACTIVE
        self.override_enabled = False
        
        # Keep trigger history but mark as resolved
        if self.triggers:
            self.triggers[-1]['resolved_at'] = datetime.now().isoformat()
            self.triggers[-1]['resolved_reason'] = reason
            
        self._save_state()
        
        logger.warning(
            f"⚠️ Circuit Breaker RESET\n"
            f"Previous status: {old_status.value}\n"
            f"Reason: {reason}\n"
            f"Trading is now ENABLED"
        )
        
        return True
        
    def enable_override(self, reason: str, override_password: str) -> bool:
        """
        Enable override to trade despite circuit breaker
        
        WARNING: Use with extreme caution!
        
        Args:
            reason: Reason for override
            override_password: Password verification
            
        Returns:
            True if override enabled
        """
        expected_password = self.config.get('override_password', 'OVERRIDE123')
        
        if override_password != expected_password:
            logger.error("❌ Invalid override password")
            return False
            
        self.override_enabled = True
        self._save_state()
        
        logger.critical(
            f"⚠️⚠️⚠️ OVERRIDE ENABLED ⚠️⚠️⚠️\n"
            f"Trading enabled despite circuit breaker: {self.status.value}\n"
            f"Reason: {reason}\n"
            f"USE WITH EXTREME CAUTION!"
        )
        
        return True
        
    def disable_override(self):
        """Disable override mode"""
        self.override_enabled = False
        self._save_state()
        logger.warning("Override mode DISABLED")
        
    def get_status_report(self) -> Dict:
        """Get detailed status report"""
        return {
            'status': self.status.value,
            'trading_allowed': self.is_trading_allowed(),
            'override_enabled': self.override_enabled,
            'triggers': self.triggers,
            'thresholds': {
                'daily_loss_limit_percent': self.daily_loss_limit_percent,
                'max_positions': self.max_positions,
                'vix_threshold': self.vix_threshold,
                'iv_shock_threshold': self.iv_shock_threshold
            },
            'timestamp': datetime.now().isoformat()
        }
        
    def reset_daily(self):
        """Reset daily triggers (call at start of new trading day)"""
        # Keep emergency stops and market halts
        if self.status in [CircuitBreakerStatus.EMERGENCY_STOP, CircuitBreakerStatus.MARKET_HALT]:
            logger.warning(
                f"Daily reset skipped - {self.status.value} requires manual intervention"
            )
            return
            
        # Clear daily triggers
        daily_triggers = [
            CircuitBreakerTrigger.DAILY_LOSS_LIMIT.value,
            CircuitBreakerTrigger.VIX_SPIKE.value,
            CircuitBreakerTrigger.IV_SHOCK.value
        ]
        
        if any(t['trigger'] in daily_triggers for t in self.triggers):
            self.status = CircuitBreakerStatus.ACTIVE
            self.triggers = []
            self._save_state()
            
            logger.info("✅ Circuit breaker reset for new trading day")
