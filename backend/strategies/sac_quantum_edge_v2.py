"""
SAC Strategy 5: Quantum Edge V2
Advanced ML-driven strategy with multi-factor analysis
"""

from typing import Dict, List
from backend.strategies.strategy_base import BaseStrategy, Signal
from backend.core.logger import get_logger

logger = get_logger(__name__)


class SACQuantumEdgeV2Strategy(BaseStrategy):
    """
    Quantum Edge V2 strategy for SAC agent
    ML-enhanced multi-factor analysis
    """
    
    def __init__(self, weight: int = 90):
        super().__init__("SAC_Quantum_Edge_V2", weight)
        self.oi_change_threshold = 15  # 15% OI change
        
    async def analyze(self, market_state: Dict) -> List[Signal]:
        """Generate ML-enhanced signals"""
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
                calls_dict = option_chain_data.get('calls', {})
                
                if not puts_dict:
                    continue
                
                # Find strike with significant OI change (institutional activity)
                atm_strike = round(spot_price / 100) * 100
                
                for strike_offset in [-100, 0, 100]:
                    strike = atm_strike + strike_offset
                    strike_str = str(int(strike))
                    
                    if strike_str in puts_dict:
                        put_data = puts_dict[strike_str]
                        oi_change = put_data.get('oi_change_pct', 0)
                        ltp = put_data.get('ltp', 0)
                        volume = put_data.get('volume', 0)
                        
                        # High OI change + volume = institutional activity
                        if abs(oi_change) > self.oi_change_threshold and volume > 1000 and ltp > 50:
                            # Positive OI change in PUTs = bearish
                            if oi_change > 0:
                                signal = Signal(
                                    strategy_name=self.name,
                                    symbol=symbol,
                                    direction='PUT',
                                    action='BUY',
                                    strike=strike,
                                    expiry=put_data.get('expiry_date'),
                                    entry_price=ltp,
                                    strength=min(100, int(abs(oi_change) * 3)),
                                    reason=f"Institutional PUT accumulation: OI+{oi_change:.1f}%, Vol={volume}",
                                    metadata={
                                        'oi_change': oi_change,
                                        'volume': volume,
                                        'pcr': pcr
                                    }
                                )
                                
                                signal.target_price = ltp * 1.30  # 30% target
                                signal.stop_loss = ltp * 0.88     # 12% SL
                                
                                signals.append(signal)
                                logger.info(f"Quantum Edge V2: {symbol} {strike} PUT @ ₹{ltp}, OI+{oi_change:.1f}%")
                            
                            # Negative OI change in PUTs = bullish (sell PUTs)
                            elif oi_change < -self.oi_change_threshold:
                                signal = Signal(
                                    strategy_name=self.name,
                                    symbol=symbol,
                                    direction='PUT',
                                    action='SELL',
                                    strike=strike,
                                    expiry=put_data.get('expiry_date'),
                                    entry_price=ltp,
                                    strength=min(100, int(abs(oi_change) * 2.5)),
                                    reason=f"Institutional PUT unwinding: OI{oi_change:.1f}%, Vol={volume}",
                                    metadata={
                                        'oi_change': oi_change,
                                        'volume': volume,
                                        'pcr': pcr
                                    }
                                )
                                
                                signal.target_price = ltp * 0.65  # Collect 35% premium
                                signal.stop_loss = ltp * 1.25     # 25% SL
                                
                                signals.append(signal)
                                logger.info(f"Quantum Edge V2: Sell {symbol} {strike} PUT @ ₹{ltp}, OI{oi_change:.1f}%")
                            
                            if len(signals) >= 2:
                                return signals
                        
        except Exception as e:
            logger.error(f"Error in SAC Quantum Edge V2: {e}")
        
        return signals
