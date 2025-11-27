"""
SAC Strategy 4: Default Conservative Strategy
Conservative baseline strategy for stable returns
"""

from typing import Dict, List
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
        self.pcr_threshold = 1.2
        
    async def analyze(self, market_state: Dict) -> List[Signal]:
        """Generate conservative default signals"""
        signals = []
        
        try:
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
                
                # High PCR: More puts than calls - bearish
                if pcr > self.pcr_threshold:
                    # Find OTM PUT to buy
                    atm_strike = round(spot_price / 100) * 100
                    strike = atm_strike - 100  # Slightly OTM
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
                                strength=min(100, int((pcr / self.pcr_threshold) * 65)),
                                reason=f"High PCR ({pcr:.2f}) indicates bearish sentiment",
                                metadata={'pcr': pcr}
                            )
                            
                            signal.target_price = ltp * 1.25  # 25% target
                            signal.stop_loss = ltp * 0.85     # 15% SL
                            
                            signals.append(signal)
                            logger.info(f"Default strategy signal: {symbol} {strike} PUT @ ₹{ltp}, PCR={pcr:.2f}")
                
                # Low PCR: More calls than puts - bullish (sell OTM PUTs)
                elif pcr < (1 / self.pcr_threshold):
                    atm_strike = round(spot_price / 100) * 100
                    strike = atm_strike - 200  # Far OTM
                    strike_str = str(int(strike))
                    
                    if strike_str in puts_dict:
                        put_data = puts_dict[strike_str]
                        ltp = put_data.get('ltp', 0)
                        
                        if ltp > 20:
                            signal = Signal(
                                strategy_name=self.name,
                                symbol=symbol,
                                direction='PUT',
                                action='SELL',
                                strike=strike,
                                expiry=put_data.get('expiry_date'),
                                entry_price=ltp,
                                strength=min(100, int((1/pcr) * 50)),
                                reason=f"Low PCR ({pcr:.2f}) indicates bullish sentiment, sell OTM PUT",
                                metadata={'pcr': pcr}
                            )
                            
                            signal.target_price = ltp * 0.60  # Collect 40% premium
                            signal.stop_loss = ltp * 1.30     # 30% SL
                            
                            signals.append(signal)
                            logger.info(f"Default strategy signal: Sell {symbol} {strike} PUT @ ₹{ltp}, PCR={pcr:.2f}")
                        
        except Exception as e:
            logger.error(f"Error in SAC Default Strategy: {e}")
        
        return signals
