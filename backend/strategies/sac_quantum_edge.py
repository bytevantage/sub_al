"""
SAC Strategy 6: Quantum Edge
Premium ML-powered strategy combining multiple signals
"""

from typing import Dict, List
from backend.strategies.strategy_base import BaseStrategy, Signal
from backend.core.logger import get_logger

logger = get_logger(__name__)


class SACQuantumEdgeStrategy(BaseStrategy):
    """
    Quantum Edge strategy for SAC agent
    Top-tier ML-powered multi-signal strategy
    """
    
    def __init__(self, weight: int = 100):
        super().__init__("SAC_Quantum_Edge", weight)
        self.confidence_threshold = 0.7
        
    async def analyze(self, market_state: Dict) -> List[Signal]:
        """Generate premium ML-driven signals"""
        signals = []
        
        try:
            for symbol in ['NIFTY', 'SENSEX']:
                symbol_data = market_state.get(symbol, {})
                spot_price = symbol_data.get('spot_price', 0)
                pcr = symbol_data.get('pcr', 1.0)
                iv_rank = symbol_data.get('iv_rank', 50)
                option_chain_data = symbol_data.get('option_chain', {})
                
                if spot_price == 0 or not option_chain_data:
                    continue
                
                puts_dict = option_chain_data.get('puts', {})
                
                if not puts_dict:
                    continue
                
                # Multi-factor scoring
                confidence = 0
                signals_list = []
                
                # Factor 1: PCR extreme (spec thresholds)
                if pcr > 1.70:
                    confidence += 30  # Extreme PCR - contrarian bullish
                    direction = 'CALL'
                    action = 'BUY'
                elif pcr < 0.70:
                    confidence += 25  # Extreme PCR - contrarian bearish
                    direction = 'PUT'
                    action = 'BUY'
                else:
                    continue  # Only trade in extreme PCR zones
                
                # Factor 2: IV regime
                if iv_rank > 70:
                    confidence += 20  # High IV = sell premium
                    if action == 'BUY':
                        action = 'SELL'  # Override to sell in high IV
                elif iv_rank < 30:
                    confidence += 15  # Low IV = buy options
                    if action == 'SELL':
                        action = 'BUY'  # Override to buy in low IV
                
                # Factor 3: Price momentum (simplified)
                price_change = symbol_data.get('price_change', 0)
                if abs(price_change) > 1:
                    confidence += 15  # Strong momentum
                
                # Only generate signal if confidence is high
                if confidence / 100 < self.confidence_threshold:
                    continue
                
                # Find optimal strike
                atm_strike = round(spot_price / 100) * 100
                
                # If buying, go slightly OTM; if selling, go further OTM
                if action == 'BUY':
                    strike = atm_strike - 50 if direction == 'PUT' else atm_strike + 50
                else:
                    strike = atm_strike - 150 if direction == 'PUT' else atm_strike + 150
                
                strike_str = str(int(strike))
                
                if strike_str in puts_dict:
                    put_data = puts_dict[strike_str]
                    ltp = put_data.get('ltp', 0)
                    delta = abs(put_data.get('delta', 0))
                    gamma = put_data.get('gamma', 0)
                    
                    if ltp > (30 if action == 'BUY' else 20):
                        signal = Signal(
                            strategy_name=self.name,
                            symbol=symbol,
                            direction=direction,
                            action=action,
                            strike=strike,
                            expiry=put_data.get('expiry_date'),
                            entry_price=ltp,
                            strength=min(100, confidence),
                            reason=f"Quantum Edge: PCR={pcr:.2f}, IV_Rank={iv_rank}, Confidence={confidence}%",
                            metadata={
                                'pcr': pcr,
                                'iv_rank': iv_rank,
                                'confidence': confidence,
                                'delta': delta,
                                'gamma': gamma,
                                'price_change': price_change
                            }
                        )
                        
                        # Dynamic targets based on confidence
                        if action == 'BUY':
                            signal.target_price = ltp * (1.20 + confidence/500)  # 20-40% target
                            signal.stop_loss = ltp * 0.87                         # 13% SL
                        else:
                            signal.target_price = ltp * (0.70 - confidence/500)  # Collect 30-50%
                            signal.stop_loss = ltp * 1.22                         # 22% SL
                        
                        signals.append(signal)
                        logger.info(f"Quantum Edge: {action} {symbol} {strike} {direction} @ ₹{ltp}, Conf={confidence}%")
                        
                        if len(signals) >= 2:
                            return signals
                        
        except Exception as e:
            logger.error(f"Error in SAC Quantum Edge: {e}")
        
        return signals
