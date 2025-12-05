"""
SAC Strategy 4: Default Conservative Strategy
Conservative baseline strategy for stable returns
"""

from typing import Dict, List
from datetime import datetime
from backend.strategies.strategy_base import BaseStrategy, Signal
from backend.core.logger import get_logger

logger = get_logger(__name__)


class SACDefaultStrategy(BaseStrategy):
    """
    Default conservative strategy for SAC agent
    Balanced approach with moderate risk
    """
    
    def __init__(self, weight: int = 65):
        super().__init__("SAC_Default", weight)
        self.contrarian_bullish_threshold = 1.70  # Extreme PCR > 1.70
        self.contrarian_bearish_threshold = 0.70  # Extreme PCR < 0.70
        
    async def analyze(self, market_state: Dict) -> List[Signal]:
        """Generate conservative default signals"""
        signals = []
        
        try:
            # ORB Time filter: 09:15-10:00 only
            current_time = datetime.now()
            current_hour = current_time.hour
            current_minute = current_time.minute
            
            if not ((current_hour == 9 and current_minute >= 15) or 
                   (current_hour == 10 and current_minute == 0)):
                return []  # Outside ORB window
            
            for symbol in ['NIFTY', 'SENSEX']:
                symbol_data = market_state.get(symbol, {})
                spot_price = symbol_data.get('spot_price', 0)
                pcr = symbol_data.get('pcr', 1.0)
                option_chain_data = symbol_data.get('option_chain', {})
                
                if spot_price == 0 or not option_chain_data:
                    continue
                
                puts_dict = option_chain_data.get('puts', {})
                
                if not puts_dict:
                    continue
                
                # Extreme PCR contrarian logic (spec)
                if pcr > self.contrarian_bullish_threshold:
                    # Extreme PCR > 1.70 - contrarian bullish (buy calls)
                    atm_strike = round(spot_price / 100) * 100
                    strike = atm_strike + 100  # Slightly OTM CALL
                    strike_str = str(int(strike))
                    
                    # Look for CALL instead of PUT
                    calls_dict = option_chain_data.get('calls', {})
                    if strike_str in calls_dict:
                        call_data = calls_dict[strike_str]
                        ltp = call_data.get('ltp', 0)
                        
                        if ltp > 50:
                            signal = Signal(
                                strategy_name=self.name,
                                symbol=symbol,
                                direction='CALL',
                                action='BUY',
                                strike=strike,
                                expiry=call_data.get('expiry_date'),
                                entry_price=ltp,
                                strength=75,
                                reason=f"ORB Extreme PCR ({pcr:.2f}) - contrarian bullish",
                                metadata={'pcr': pcr, 'time': 'ORB'}
                            )
                            
                            signal.target_price = ltp * 1.25  # 25% target
                            signal.stop_loss = ltp * 0.85     # 15% SL
                            
                            signals.append(signal)
                            logger.info(f"Default ORB: Buy {symbol} {strike} CALL @ ₹{ltp}, PCR={pcr:.2f}")
                
                elif pcr < self.contrarian_bearish_threshold:
                    # Extreme PCR < 0.70 - contrarian bearish (buy puts)
                    atm_strike = round(spot_price / 100) * 100
                    strike = atm_strike - 100  # Slightly OTM PUT
                    strike_str = str(int(strike))
                    
                    if strike_str in puts_dict:
                        put_data = puts_dict[strike_str]
                        ltp = put_data.get('ltp', 0)
                        
                        if ltp > 30:
                            signal = Signal(
                                strategy_name=self.name,
                                symbol=symbol,
                                direction='PUT',
                                action='BUY',
                                strike=strike,
                                expiry=put_data.get('expiry_date'),
                                entry_price=ltp,
                                strength=75,
                                reason=f"ORB Extreme PCR ({pcr:.2f}) - contrarian bearish",
                                metadata={'pcr': pcr, 'time': 'ORB'}
                            )
                            
                            signal.target_price = ltp * 1.25  # 25% target
                            signal.stop_loss = ltp * 0.85     # 15% SL
                            
                            signals.append(signal)
                            logger.info(f"Default ORB: Buy {symbol} {strike} PUT @ ₹{ltp}, PCR={pcr:.2f}")
                
                else:
                    # Normal PCR range (0.70-1.70) - no trades
                    continue
                        
        except Exception as e:
            logger.error(f"Error in SAC Default Strategy: {e}")
        
        return signals
