"""
SAC Strategy 3: VWAP Deviation
Trade based on price deviation from VWAP
"""

from typing import Dict, List
from backend.strategies.strategy_base import BaseStrategy, Signal
from backend.core.logger import get_logger

logger = get_logger(__name__)


class SACVWAPDeviationStrategy(BaseStrategy):
    """
    VWAP Deviation strategy for SAC agent
    Trade mean reversion when price deviates significantly from VWAP
    """
    
    def __init__(self, weight: int = 70):
        super().__init__("SAC_VWAP_Deviation", weight)
        self.deviation_threshold = 0.005  # 0.5% deviation
        
    async def analyze(self, market_state: Dict) -> List[Signal]:
        """Generate VWAP deviation signals"""
        signals = []
        
        try:
            for symbol in ['NIFTY', 'SENSEX']:
                symbol_data = market_state.get(symbol, {})
                spot_price = symbol_data.get('spot_price', 0)
                vwap = symbol_data.get('vwap', spot_price)
                option_chain_data = symbol_data.get('option_chain', {})
                
                if spot_price == 0 or vwap == 0 or not option_chain_data:
                    continue
                
                # Calculate deviation
                deviation = (spot_price - vwap) / vwap
                
                puts_dict = option_chain_data.get('puts', {})
                
                if not puts_dict:
                    continue
                
                # Price above VWAP: expect mean reversion down (buy PUTs)
                if deviation > self.deviation_threshold:
                    atm_strike = round(spot_price / 100) * 100
                    strike_str = str(int(atm_strike))
                    
                    if strike_str in puts_dict:
                        put_data = puts_dict[strike_str]
                        ltp = put_data.get('ltp', 0)
                        
                        if ltp > 50:
                            signal = Signal(
                                strategy_name=self.name,
                                symbol=symbol,
                                direction='PUT',
                                action='BUY',
                                strike=atm_strike,
                                expiry=put_data.get('expiry_date'),
                                entry_price=ltp,
                                strength=min(100, int(abs(deviation) * 10000)),
                                reason=f"Price {deviation*100:.2f}% above VWAP, expect reversion",
                                metadata={
                                    'deviation': deviation,
                                    'vwap': vwap,
                                    'spot': spot_price
                                }
                            )
                            
                            signal.target_price = ltp * 1.20  # 20% target
                            signal.stop_loss = ltp * 0.88     # 12% SL
                            
                            signals.append(signal)
                            logger.info(f"VWAP deviation signal: {symbol} {atm_strike} PUT @ ₹{ltp}, dev={deviation*100:.2f}%")
                
                # Price below VWAP: expect mean reversion up (sell PUTs or buy CALLs)
                elif deviation < -self.deviation_threshold:
                    atm_strike = round(spot_price / 100) * 100
                    strike_str = str(int(atm_strike))
                    
                    if strike_str in puts_dict:
                        put_data = puts_dict[strike_str]
                        ltp = put_data.get('ltp', 0)
                        
                        if ltp > 50:
                            signal = Signal(
                                strategy_name=self.name,
                                symbol=symbol,
                                direction='PUT',
                                action='SELL',
                                strike=atm_strike,
                                expiry=put_data.get('expiry_date'),
                                entry_price=ltp,
                                strength=min(100, int(abs(deviation) * 8000)),
                                reason=f"Price {abs(deviation)*100:.2f}% below VWAP, expect bounce",
                                metadata={
                                    'deviation': deviation,
                                    'vwap': vwap,
                                    'spot': spot_price
                                }
                            )
                            
                            signal.target_price = ltp * 0.75  # Collect 25% premium
                            signal.stop_loss = ltp * 1.20     # 20% SL
                            
                            signals.append(signal)
                            logger.info(f"VWAP deviation signal: Sell {symbol} {atm_strike} PUT @ ₹{ltp}, dev={deviation*100:.2f}%")
                        
        except Exception as e:
            logger.error(f"Error in SAC VWAP Deviation: {e}")
        
        return signals
