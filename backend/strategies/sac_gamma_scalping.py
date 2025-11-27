"""
SAC Strategy 1: Gamma Scalping
Enhanced gamma scalping with real-time Greeks analysis
"""

from typing import Dict, List
from backend.strategies.strategy_base import BaseStrategy, Signal
from backend.core.logger import get_logger

logger = get_logger(__name__)


class SACGammaScalpingStrategy(BaseStrategy):
    """
    Gamma Scalping strategy optimized for SAC agent
    Trades based on gamma exposure and delta hedging opportunities
    """
    
    def __init__(self, weight: int = 80):
        super().__init__("SAC_Gamma_Scalping", weight)
        self.min_gamma = 0.001
        self.target_delta = 0.5
        
    async def analyze(self, market_state: Dict) -> List[Signal]:
        """Generate gamma scalping signals"""
        signals = []
        
        try:
            for symbol in ['NIFTY', 'SENSEX']:
                symbol_data = market_state.get(symbol, {})
                spot_price = symbol_data.get('spot_price', 0)
                option_chain_data = symbol_data.get('option_chain', {})
                
                if spot_price == 0 or not option_chain_data:
                    continue
                
                # Get calls and puts
                calls_dict = option_chain_data.get('calls', {})
                puts_dict = option_chain_data.get('puts', {})
                
                if not calls_dict and not puts_dict:
                    continue
                
                # Scan ALL strikes in option chain for high gamma (not just 5 near ATM)
                atm_strike = round(spot_price / 100) * 100
                
                # Process ALL strikes in option chain
                for strike_str, put_data in puts_dict.items():
                    strike = float(strike_str)
                    
                    # Skip strikes too far OTM (>5% from spot for efficiency)
                    if abs(strike - spot_price) / spot_price > 0.05:
                        continue
                    
                    # Extract data for PUT
                    gamma = put_data.get('gamma', 0)
                    delta = abs(put_data.get('delta', 0))
                    ltp = put_data.get('ltp', 0)
                        
                    # High gamma + moderate delta = good scalping opportunity
                    if gamma > self.min_gamma and 0.3 < delta < 0.7 and ltp > 50:
                        signal = Signal(
                            strategy_name=self.name,
                            symbol=symbol,
                            direction='PUT',
                            action='BUY',
                            strike=strike,
                            expiry=put_data.get('expiry_date'),
                            entry_price=ltp,
                            strength=min(100, int(gamma * 10000)),
                            reason=f"High gamma ({gamma:.4f}), delta={delta:.2f}, ideal for scalping",
                            metadata={
                                'gamma': gamma,
                                'delta': delta,
                                'theta': put_data.get('theta', 0),
                                'iv': put_data.get('iv', 0)
                            }
                        )
                        
                        # Set targets based on gamma
                        signal.target_price = ltp * 1.15  # 15% target
                        signal.stop_loss = ltp * 0.90     # 10% SL
                        
                        signals.append(signal)
                        logger.info(f"Gamma scalping signal: {symbol} {strike} PUT @ ₹{ltp}, γ={gamma:.4f}")
                        
                        if len(signals) >= 3:  # Conservative signal limit
                            return signals
                
        except Exception as e:
            logger.error(f"Error in SAC Gamma Scalping: {e}")
        
        return signals
