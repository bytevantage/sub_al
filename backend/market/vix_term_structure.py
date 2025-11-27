"""
VIX Term Structure Analysis
Analyze VIX futures term structure for volatility arbitrage opportunities
"""

from typing import Dict, Optional, List
from datetime import datetime
from backend.core.logger import get_logger

logger = get_logger(__name__)


class VIXTermStructureAnalyzer:
    """
    Analyze VIX futures term structure for trading signals
    
    Term Structure States:
    - Contango: Front month < Back month (normal, bullish)
    - Backwardation: Front month > Back month (fear, bearish)
    - Steep Contango: > 10% difference (volatility selling opportunity)
    - Steep Backwardation: > 10% difference (volatility buying opportunity)
    """
    
    def __init__(self):
        self.vix_history: List[Dict] = []
        self.last_analysis = None
        self.current_structure = "neutral"
    
    def analyze_term_structure(self, front_month_vix: float, back_month_vix: float) -> Dict:
        """
        Analyze VIX term structure
        
        Args:
            front_month_vix: Front month VIX futures price
            back_month_vix: Back month VIX futures price
            
        Returns:
            Dict with structure analysis and trading signals
        """
        try:
            if not front_month_vix or not back_month_vix or front_month_vix <= 0 or back_month_vix <= 0:
                return {
                    "structure": "unknown",
                    "spread": 0.0,
                    "spread_percent": 0.0,
                    "signal": "neutral",
                    "confidence": 0.0
                }
            
            # Calculate spread
            spread = back_month_vix - front_month_vix
            spread_percent = (spread / front_month_vix) * 100
            
            # Determine structure
            if spread_percent > 10:
                structure = "steep_contango"
                signal = "sell_volatility"
                confidence = min(100, abs(spread_percent) * 5)
            elif spread_percent > 2:
                structure = "contango"
                signal = "neutral_bearish"
                confidence = abs(spread_percent) * 10
            elif spread_percent < -10:
                structure = "steep_backwardation"
                signal = "buy_volatility"
                confidence = min(100, abs(spread_percent) * 5)
            elif spread_percent < -2:
                structure = "backwardation"
                signal = "neutral_bullish"
                confidence = abs(spread_percent) * 10
            else:
                structure = "flat"
                signal = "neutral"
                confidence = 0.0
            
            self.current_structure = structure
            
            analysis = {
                "structure": structure,
                "front_month": front_month_vix,
                "back_month": back_month_vix,
                "spread": round(spread, 2),
                "spread_percent": round(spread_percent, 2),
                "signal": signal,
                "confidence": round(confidence, 1),
                "timestamp": datetime.now().isoformat()
            }
            
            self.last_analysis = analysis
            self.vix_history.append(analysis)
            
            # Keep only last 100 readings
            if len(self.vix_history) > 100:
                self.vix_history.pop(0)
            
            if abs(spread_percent) > 5:
                logger.info(
                    f"VIX Term Structure: {structure.upper()} | "
                    f"Spread: {spread_percent:+.2f}% | Signal: {signal}"
                )
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing VIX term structure: {e}")
            return {
                "structure": "error",
                "spread": 0.0,
                "spread_percent": 0.0,
                "signal": "neutral",
                "confidence": 0.0
            }
    
    def get_volatility_regime(self, current_vix: float) -> str:
        """
        Determine volatility regime based on VIX level and term structure
        
        Returns:
            "low_vol", "normal", "elevated", "high_vol", "crisis"
        """
        if current_vix < 15:
            return "low_vol"
        elif current_vix < 20:
            return "normal"
        elif current_vix < 30:
            return "elevated"
        elif current_vix < 40:
            return "high_vol"
        else:
            return "crisis"
    
    def should_harvest_volatility(self, current_vix: float) -> bool:
        """
        Determine if conditions are favorable for volatility harvesting (gamma scalping)
        
        Favorable conditions:
        - VIX > 25 (elevated volatility)
        - Steep contango (premium decay)
        """
        if not self.last_analysis:
            return False
        
        structure = self.last_analysis.get("structure", "unknown")
        
        # High volatility + contango = good for gamma scalping
        if current_vix > 25 and structure in ["contango", "steep_contango"]:
            return True
        
        return False
    
    def get_status(self) -> Dict:
        """Get current term structure status"""
        return {
            "current_structure": self.current_structure,
            "last_analysis": self.last_analysis,
            "history_length": len(self.vix_history)
        }


# Singleton instance
_vix_analyzer = None


def get_vix_analyzer() -> VIXTermStructureAnalyzer:
    """Get singleton VIX term structure analyzer"""
    global _vix_analyzer
    if _vix_analyzer is None:
        _vix_analyzer = VIXTermStructureAnalyzer()
    return _vix_analyzer
