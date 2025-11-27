"""
SAC Strategy 2: IV Rank Trading
Trade based on IV percentile and mean reversion
"""

from typing import Dict, List
from backend.strategies.strategy_base import BaseStrategy, Signal
from backend.core.logger import get_logger

logger = get_logger(__name__)


class SACIVRankStrategy(BaseStrategy):
    """
    IV Rank strategy for SAC agent
    Sells premium when IV is high, buys when IV is low
    """
    
    def __init__(self, weight: int = 75):
        super().__init__("SAC_IV_Rank", weight)
        self.high_iv_threshold = 20  # Above 20% is high
        self.low_iv_threshold = 12   # Below 12% is low
        
    async def analyze(self, market_state: Dict) -> List[Signal]:
        """Generate IV rank based signals"""
        signals = []
        
        try:
            for symbol in ['NIFTY', 'SENSEX']:
                symbol_data = market_state.get(symbol, {})
                spot_price = symbol_data.get('spot_price', 0)
                option_chain_data = symbol_data.get('option_chain', {})
                
                if spot_price == 0 or not option_chain_data:
                    continue
                
                puts_dict = option_chain_data.get('puts', {})
                
                if not puts_dict:
                    continue
                
                # Find ATM strike
                atm_strike = round(spot_price / 100) * 100
                strike_str = str(int(atm_strike))
                
                if strike_str in puts_dict:
                    put_data = puts_dict[strike_str]
                    iv = put_data.get('iv', 0)
                    ltp = put_data.get('ltp', 0)
                    
                    if ltp < 50:
                        continue
                    
                    # High IV: Sell premium
                    if iv > self.high_iv_threshold:
                        signal = Signal(
                            strategy_name=self.name,
                            symbol=symbol,
                            direction='PUT',
                            action='SELL',
                            strike=atm_strike,
                            expiry=put_data.get('expiry_date'),
                            entry_price=ltp,
                            strength=min(100, int((iv / self.high_iv_threshold) * 80)),
                            reason=f"High IV ({iv:.1f}%) - sell premium",
                            metadata={'iv': iv, 'iv_regime': 'high'}
                        )
                        
                        signal.target_price = ltp * 0.70  # Collect 30% premium
                        signal.stop_loss = ltp * 1.25     # 25% SL
                        
                        signals.append(signal)
                        logger.info(f"IV Rank signal: Sell {symbol} {atm_strike} PUT @ ₹{ltp}, IV={iv:.1f}%")
                    
                    # Low IV: Buy cheap options
                    elif iv < self.low_iv_threshold and ltp > 0:
                        signal = Signal(
                            strategy_name=self.name,
                            symbol=symbol,
                            direction='PUT',
                            action='BUY',
                            strike=atm_strike,
                            expiry=put_data.get('expiry_date'),
                            entry_price=ltp,
                            strength=min(100, int((self.low_iv_threshold / iv) * 70)),
                            reason=f"Low IV ({iv:.1f}%) - buy cheap options",
                            metadata={'iv': iv, 'iv_regime': 'low'}
                        )
                        
                        signal.target_price = ltp * 1.50  # 50% profit target
                        signal.stop_loss = ltp * 0.85     # 15% SL
                        
                        signals.append(signal)
                        logger.info(f"IV Rank signal: Buy {symbol} {atm_strike} PUT @ ₹{ltp}, IV={iv:.1f}%")
                        
        except Exception as e:
            logger.error(f"Error in SAC IV Rank: {e}")
        
        return signals
