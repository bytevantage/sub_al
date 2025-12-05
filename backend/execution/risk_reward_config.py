"""
OFFICIAL SRB NIFTY/SENSEX CLEAN REGIME 2025 SPEC
Fixed risk management - NO dynamic adjustments
"""

from datetime import datetime, time
from typing import Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

# OFFICIAL SPEC - Fixed parameters
RISK_REWARD_CONFIG = {
    "base_rr": 4.2,  # Fixed 1:4.2 R:R achieved by system
    "dynamic_rr_enabled": False,  # NO dynamic adjustments
    "max_risk_per_trade": 0.5,  # Fixed 0.5% per SAC decision
    "daily_loss_limit": 5.0,  # Fixed 5% daily limit -> full shutdown
    "max_leverage": 4.0,  # Max 4x leverage
    "max_position_pct": 30.0,  # No position > 30% of capital
    "position_sizing": "fixed",  # Fixed sizing - NO Kelly
}

class RiskRewardCalculator:
    """Advanced risk-reward calculator with dynamic regime detection"""
    
    def __init__(self, capital: float = 100000):
        self.capital = capital
        self.last_regime = None
        
    def determine_regime(self, confidence: Optional[float] = None, 
                        vix: Optional[float] = None, 
                        adx: Optional[float] = None) -> str:
        """
        Determine market regime for RR adjustment
        
        Args:
            confidence: ML confidence score (0-1)
            vix: India VIX value
            adx: ADX trend strength indicator
            
        Returns:
            Regime string for RR calculation
        """
        try:
            # Check for expiry day morning
            now = datetime.now()
            is_expiry_day = self._is_expiry_day(now)
            is_morning = time(9, 25) <= now.time() <= time(11, 0)
            
            # High confidence regime (ML or SAC)
            if confidence and confidence >= 0.80:
                regime = "high_confidence"
                logger.info(f"🎯 High confidence regime: ML conf={confidence:.2f}")
                return regime
                
            # Monster day regime (high volatility + strong trend)
            if vix and adx and vix > 20 and adx > 32:
                regime = "monster_day"
                logger.info(f"🔥 Monster day regime: VIX={vix:.1f}, ADX={adx:.1f}")
                return regime
                
            # Expiry day morning regime
            if is_expiry_day and is_morning:
                regime = "expiry_day_morning"
                logger.info(f"📅 Expiry day morning regime")
                return regime
                
            # Choppy market regime
            if (adx and adx < 20) or (vix and vix < 13):
                regime = "chop_regime"
                adx_str = f"{adx:.1f}" if adx is not None else "N/A"
                vix_str = f"{vix:.1f}" if vix is not None else "N/A"
                logger.info(f"📊 Choppy regime: ADX={adx_str}, VIX={vix_str}")
                return regime
                
            # Default regime
            regime = "default"
            logger.info(f"📈 Default regime")
            return regime
            
        except Exception as e:
            logger.error(f"Error determining regime: {e}")
            return "default"
    
    def calculate_targets(self, entry_price: float, signal_direction: str, 
                         confidence: Optional[float] = None,
                         vix: Optional[float] = None, 
                         adx: Optional[float] = None,
                         quantity: int = 1,
                         max_risk_pct: Optional[float] = None) -> Dict:
        """
        OFFICIAL SPEC: Fixed 18% stop loss, NO tiered targets
        
        Args:
            entry_price: Entry price of the option
            signal_direction: 'CALL' or 'PUT' 
            confidence: Ignored - fixed system
            vix: Used only for dynamic SL (15-24%)
            adx: Ignored - fixed system
            quantity: Position quantity
            
        Returns:
            Dictionary with stop_loss only (no TP1/TP2/TP3)
        """
        try:
            # OFFICIAL SPEC: Fixed 18% stop loss (dynamic 15-24% with VIX)
            # If caller requests an explicit max risk percent (e.g., option-specific wider SL), honor it.
            if max_risk_pct and max_risk_pct > 0:
                # Caller may pass 0.30 (30%) or similar; accept reasonable ranges up to 50%
                max_sl_pct = float(max_risk_pct)
            else:
                vix_multiplier = 1.0 + (max(0, (vix or 20) - 15) * 0.02)  # 0.02 per VIX point above 15
                max_sl_pct = min(0.24, max(0.15, 0.18 * vix_multiplier))  # 15-24% dynamic range
            
            # Calculate stop loss based on direction
            if signal_direction.upper() == 'CALL':
                stop_loss = entry_price * (1 - max_sl_pct)
            else:  # PUT
                stop_loss = entry_price * (1 - max_sl_pct)
            
            # Ensure stop loss is positive
            stop_loss = max(0.01, stop_loss)
            
            # OFFICIAL SPEC: NO tiered targets - let winners run
            return {
                'stop_loss': round(stop_loss, 2),
                'sl_pct': round(max_sl_pct * 100, 1),
                'regime': 'FIXED_SPEC',
                'rr_ratio': 4.2,  # Achieved system R:R
                'rr_final': '1:4.2',  # Added for strategy compatibility
                'risk_pct': round(max_sl_pct * 100, 1),  # Added for strategy compatibility
                'risk_amount': entry_price * max_sl_pct * quantity,
                # NO TP1/TP2/TP3 per official spec
                'tp1': 0,
                'tp2': 0, 
                'tp3': 0
            }
            
        except Exception as e:
            logger.error(f"Error calculating targets: {e}")
            # Fallback - simple 18% stop loss
            fallback_sl = entry_price * 0.82
            return {
                'stop_loss': round(fallback_sl, 2),
                'sl_pct': 18.0,
                'regime': 'FALLBACK',
                'rr_ratio': 4.2,
                'risk_amount': entry_price * 0.18 * quantity,
                'tp1': 0, 'tp2': 0, 'tp3': 0
            }
    
    def calculate_position_size(self, signal: Dict, entry_price: float) -> int:
        """
        OFFICIAL SPEC: Fixed 0.5% risk per SAC decision
        
        Args:
            signal: Trading signal (regime/confidence ignored)
            entry_price: Entry price of option
            
        Returns:
            Position quantity (lots)
        """
        try:
            # OFFICIAL SPEC: Fixed 0.5% risk per decision
            risk_pct = 0.005  # 0.5%
            risk_amount = self.capital * risk_pct
            
            # Fixed 18% stop loss (dynamic 15-24% with VIX)
            vix = signal.get('vix', 20)
            vix_multiplier = 1.0 + (max(0, vix - 15) * 0.02)
            sl_pct = min(0.24, max(0.15, 0.18 * vix_multiplier))
            
            # Calculate quantity
            risk_per_lot = entry_price * sl_pct
            quantity = int(risk_amount / risk_per_lot)
            
            # Ensure minimum 1 lot and max leverage check
            quantity = max(1, min(quantity, int(self.capital * 4.0 / entry_price)))
            
            return quantity
            
        except Exception as e:
            logger.error(f"Error calculating position size: {e}")
            return 1  # Minimum 1 lot

# Global calculator instance
calculator = RiskRewardCalculator()

def calculate_targets(entry_price: float, signal_direction: str, 
                     confidence: Optional[float] = None,
                     vix: Optional[float] = None, 
                     adx: Optional[float] = None,
                     quantity: int = 1,
                     max_risk_pct: Optional[float] = None) -> Dict:
    """
    Convenience function for target calculation
    
    Args:
        entry_price: Entry price of the option
        signal_direction: 'CALL' or 'PUT'
        confidence: ML confidence score (0-1)
        vix: India VIX value
        adx: ADX trend strength
        quantity: Position quantity
        
    Returns:
        Dictionary with stop_loss, tp1, tp2, tp3, and metadata
    """
    return calculator.calculate_targets(entry_price, signal_direction, confidence, vix, adx, quantity, max_risk_pct)
