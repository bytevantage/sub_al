"""
Market Context Service
Enriches trades and positions with comprehensive market conditions
"""

from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from zoneinfo import ZoneInfo
from enum import Enum

from backend.core.logger import get_logger

logger = get_logger(__name__)

IST = ZoneInfo("Asia/Kolkata")


class MarketRegime(Enum):
    """Market regime classifications"""
    CALM_TRENDING = "calm_trending"          # Low VIX, directional move
    CALM_RANGING = "calm_ranging"            # Low VIX, choppy/sideways
    VOLATILE_TRENDING = "volatile_trending"  # High VIX, strong directional move
    VOLATILE_RANGING = "volatile_ranging"    # High VIX, whipsaw/choppy
    EXTREME_STRESS = "extreme_stress"        # VIX >40, panic mode
    UNKNOWN = "unknown"                      # Insufficient data


class MarketContextService:
    """
    Enriches positions and trades with market context
    - VIX level and regime
    - Time-of-day classification
    - Day-of-week patterns
    - Expiry day detection
    """
    
    def __init__(self, market_monitor=None, market_data_manager=None):
        self.market_monitor = market_monitor
        self.market_data_manager = market_data_manager
        
        # VIX thresholds for regime classification
        self.vix_calm = 15
        self.vix_elevated = 20
        self.vix_high = 30
        self.vix_extreme = 40
        
        # Trend detection parameters
        self.trend_threshold = 0.5  # % move in 1 hour to classify as trending
        
    def get_current_vix(self) -> Optional[float]:
        """Get current India VIX value"""
        try:
            if self.market_monitor and hasattr(self.market_monitor, 'current_vix'):
                return self.market_monitor.current_vix
            
            # Fallback: Try to fetch from market data
            if self.market_data_manager:
                # Try to get VIX from market data
                market_data = getattr(self.market_data_manager, 'latest_data', {})
                vix = market_data.get('vix') or market_data.get('INDIA_VIX')
                if vix:
                    return float(vix)
            
            return None
            
        except Exception as e:
            logger.debug(f"Could not get VIX: {e}")
            return None
    
    def classify_regime(self, vix: Optional[float], spot_price_current: float, 
                       spot_price_1h_ago: Optional[float] = None) -> Tuple[str, float]:
        """
        Classify current market regime
        
        Returns:
            (regime_name, confidence) tuple
        """
        if vix is None:
            return (MarketRegime.UNKNOWN.value, 0.0)
        
        # Determine volatility level
        is_calm = vix < self.vix_calm
        is_normal = self.vix_calm <= vix < self.vix_elevated
        is_elevated = self.vix_elevated <= vix < self.vix_high
        is_volatile = self.vix_high <= vix < self.vix_extreme
        is_extreme = vix >= self.vix_extreme
        
        # Determine trend strength
        is_trending = False
        confidence = 0.7  # Base confidence
        
        if spot_price_1h_ago:
            pct_change = abs((spot_price_current - spot_price_1h_ago) / spot_price_1h_ago * 100)
            is_trending = pct_change >= self.trend_threshold
            # Higher confidence if strong directional move
            if pct_change > 1.0:
                confidence = 0.9
        
        # Classify regime
        if is_extreme:
            return (MarketRegime.EXTREME_STRESS.value, 0.95)
        
        if is_calm or is_normal:
            if is_trending:
                return (MarketRegime.CALM_TRENDING.value, confidence)
            else:
                return (MarketRegime.CALM_RANGING.value, confidence)
        
        if is_elevated or is_volatile:
            if is_trending:
                return (MarketRegime.VOLATILE_TRENDING.value, confidence)
            else:
                return (MarketRegime.VOLATILE_RANGING.value, confidence)
        
        return (MarketRegime.UNKNOWN.value, 0.5)
    
    def get_time_context(self, timestamp: Optional[datetime] = None) -> Dict:
        """
        Get time-of-day context
        
        Returns dict with:
            - hour: 0-23
            - minute: 0-59
            - day_of_week: Monday, Tuesday, etc.
            - time_category: opening, morning, midday, afternoon, closing
        """
        if timestamp is None:
            timestamp = datetime.now(IST)
        elif timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=IST)
        
        hour = timestamp.hour
        minute = timestamp.minute
        day_of_week = timestamp.strftime('%A')
        
        # Categorize time of day (IST market hours: 09:15 - 15:30)
        if hour == 9 and minute < 30:
            time_category = 'opening'  # 09:15-09:30
        elif hour < 11:
            time_category = 'morning'  # 09:30-11:00
        elif hour < 13:
            time_category = 'midday'   # 11:00-13:00
        elif hour < 15:
            time_category = 'afternoon' # 13:00-15:00
        else:
            time_category = 'closing'   # 15:00-15:30
        
        return {
            'hour': hour,
            'minute': minute,
            'day_of_week': day_of_week,
            'time_category': time_category
        }
    
    def is_expiry_day(self, expiry_date: Optional[datetime], 
                     check_date: Optional[datetime] = None) -> bool:
        """Check if given date is expiry day"""
        if not expiry_date:
            return False
        
        if check_date is None:
            check_date = datetime.now(IST)
        
        # Compare dates (ignore time)
        expiry_day = expiry_date.date() if hasattr(expiry_date, 'date') else expiry_date
        check_day = check_date.date() if hasattr(check_date, 'date') else check_date
        
        return expiry_day == check_day
    
    def calculate_days_to_expiry(self, expiry_date: Optional[datetime],
                                from_date: Optional[datetime] = None) -> Optional[int]:
        """Calculate days until expiry"""
        if not expiry_date:
            return None
        
        if from_date is None:
            from_date = datetime.now(IST)
        
        # Calculate difference
        expiry_day = expiry_date.date() if hasattr(expiry_date, 'date') else expiry_date
        from_day = from_date.date() if hasattr(from_date, 'date') else from_date
        
        delta = (expiry_day - from_day).days
        return max(0, delta)  # Don't return negative days
    
    def enrich_position_entry(self, position: Dict, market_data: Dict = None) -> Dict:
        """
        Enrich position dict with market context at entry
        
        Args:
            position: Position dict
            market_data: Optional current market data
            
        Returns:
            Enriched position dict
        """
        try:
            # Get VIX
            vix = self.get_current_vix()
            if vix:
                position['vix_entry'] = vix
            
            # Get time context
            entry_time = position.get('entry_time')
            if isinstance(entry_time, str):
                entry_time = datetime.fromisoformat(entry_time)
            
            time_ctx = self.get_time_context(entry_time)
            position['entry_hour'] = time_ctx['hour']
            position['entry_minute'] = time_ctx['minute']
            position['day_of_week'] = time_ctx['day_of_week']
            position['time_category'] = time_ctx['time_category']
            
            # Get spot price for regime classification
            spot_price = position.get('spot_price_entry', 0)
            
            # Classify regime
            regime, confidence = self.classify_regime(vix, spot_price)
            position['market_regime_entry'] = regime
            position['regime_confidence'] = confidence
            
            # Expiry context
            expiry_date = position.get('expiry')
            if expiry_date:
                if isinstance(expiry_date, str):
                    expiry_date = datetime.fromisoformat(expiry_date)
                
                position['is_expiry_day'] = self.is_expiry_day(expiry_date, entry_time)
                position['days_to_expiry'] = self.calculate_days_to_expiry(expiry_date, entry_time)
            
            logger.debug(f"Enriched position entry: VIX={vix}, Regime={regime}, Time={time_ctx['time_category']}")
            
        except Exception as e:
            logger.error(f"Error enriching position entry: {e}")
        
        return position
    
    def enrich_position_exit(self, position: Dict, market_data: Dict = None) -> Dict:
        """
        Enrich position dict with market context at exit
        
        Args:
            position: Position dict
            market_data: Optional current market data
            
        Returns:
            Enriched position dict
        """
        try:
            # Get VIX at exit
            vix = self.get_current_vix()
            if vix:
                position['vix_exit'] = vix
            
            # Get time context at exit
            exit_time = position.get('exit_time')
            if isinstance(exit_time, str):
                exit_time = datetime.fromisoformat(exit_time)
            
            time_ctx = self.get_time_context(exit_time)
            position['exit_hour'] = time_ctx['hour']
            position['exit_minute'] = time_ctx['minute']
            
            # Get spot price for regime classification
            spot_price = position.get('spot_price_exit', 0)
            
            # Classify regime at exit
            regime, _ = self.classify_regime(vix, spot_price)
            position['market_regime_exit'] = regime
            
            logger.debug(f"Enriched position exit: VIX={vix}, Regime={regime}, Time={time_ctx['time_category']}")
            
        except Exception as e:
            logger.error(f"Error enriching position exit: {e}")
        
        return position
    
    def get_regime_summary(self) -> Dict:
        """Get current market regime summary"""
        vix = self.get_current_vix()
        time_ctx = self.get_time_context()
        
        regime, confidence = self.classify_regime(vix, 0)  # Spot price not needed for VIX-only classification
        
        return {
            'vix': vix,
            'regime': regime,
            'confidence': confidence,
            'time_category': time_ctx['time_category'],
            'hour': time_ctx['hour'],
            'day_of_week': time_ctx['day_of_week']
        }
