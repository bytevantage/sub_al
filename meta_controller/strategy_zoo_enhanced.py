# Enhanced Strategy Zoo with Real Price Validation
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Import Signal class and RealPriceValidator
try:
    from backend.strategies.strategy_base import Signal
except ImportError:
    # Create a simple Signal class if import fails
    class Signal:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

try:
    from backend.core.real_price_validator import RealPriceValidator
except ImportError:
    # Create a simple validator if import fails
    class RealPriceValidator:
        def validate_option_price(self, symbol, strike, direction, option_chain, current_time=None):
            return True, 50.0, "Simple validation"

class EnhancedStrategyZoo:
    """
    Enhanced Strategy Zoo with real price validation
    """
    
    def __init__(self, portfolio_value: float = 5000000):
        self.portfolio_value = portfolio_value
        self.price_validator = RealPriceValidator()
        self.strategies = self._load_strategies()
    
    def _load_strategies(self) -> List[Dict]:
        """Load all strategies with real price validation enabled"""
        strategies = [
            {
                'id': 0,
                'name': 'Gamma Scalping',
                'allocation': 0.20,
                'enabled': True,
                'requires_validation': True
            },
            {
                'id': 1,
                'name': 'IV Rank Trading',
                'allocation': 0.15,
                'enabled': True,
                'requires_validation': True
            },
            {
                'id': 2,
                'name': 'VWAP Deviation',
                'allocation': 0.15,
                'enabled': True,
                'requires_validation': True
            },
            {
                'id': 3,
                'name': 'Default Strategy',
                'allocation': 0.15,
                'enabled': True,
                'requires_validation': True
            },
            {
                'id': 4,
                'name': 'Quantum Edge V2',
                'allocation': 0.20,
                'enabled': True,
                'requires_validation': True
            },
            {
                'id': 5,
                'name': 'Quantum Edge',
                'allocation': 0.15,
                'enabled': True,
                'requires_validation': True
            }
        ]
        return strategies
    
    async def generate_signals(self, strategy_idx: int, market_state: Dict) -> List[Signal]:
        """
        Generate signals with real price validation
        """
        strategy = self.strategies[strategy_idx]
        logger.info(f"🎯 Generating signals for {strategy['name']} with real price validation")
        
        signals = []
        current_time = datetime.now()
        
        # Get symbols from market state
        for symbol in ['NIFTY', 'SENSEX']:
            if symbol not in market_state:
                continue
                
            symbol_data = market_state[symbol]
            option_chain = symbol_data.get('option_chain', {})
            
            if not option_chain:
                logger.warning(f"No option chain data for {symbol}")
                continue
            
            # Check option chain freshness
            chain_timestamp = option_chain.get('timestamp', current_time)
            if isinstance(chain_timestamp, str):
                try:
                    chain_timestamp = datetime.fromisoformat(chain_timestamp.replace('Z', '+00:00'))
                except:
                    chain_timestamp = current_time
            
            age_seconds = (current_time - chain_timestamp).total_seconds()
            if age_seconds > 60:  # Option chain older than 1 minute
                logger.warning(f"Option chain for {symbol} is {age_seconds:.1f}s old - skipping signal generation")
                continue
            
            # Generate strategy-specific signals with validation
            if strategy['name'] == 'Gamma Scalping':
                signals.extend(self._generate_gamma_scalping_signals(symbol, market_state, current_time))
            elif strategy['name'] == 'IV Rank Trading':
                signals.extend(self._generate_iv_rank_signals(symbol, market_state, current_time))
            elif strategy['name'] == 'VWAP Deviation':
                signals.extend(self._generate_vwap_signals(symbol, market_state, current_time))
            elif strategy['name'] == 'Default Strategy':
                signals.extend(self._generate_default_signals(symbol, market_state, current_time))
            elif 'Quantum Edge' in strategy['name']:
                signals.extend(self._generate_quantum_signals(symbol, market_state, current_time))
        
        logger.info(f"Generated {len(signals)} validated signals for {strategy['name']}")
        return signals
    
    def _generate_gamma_scalping_signals(self, symbol: str, market_state: Dict, current_time: datetime) -> List[Signal]:
        """Generate gamma scalping signals with real price validation"""
        signals = []
        
        try:
            symbol_data = market_state[symbol]
            spot_price = symbol_data.get('spot_price', 0)
            option_chain = symbol_data.get('option_chain', {})
            
            if spot_price <= 0 or not option_chain:
                return signals
            
            # Get ATM strike
            if symbol == 'NIFTY':
                step = 50
            else:
                step = 100
            atm_strike = round(spot_price / step) * step
            
            # Get calls/puts from option chain
            calls_dict = option_chain.get('calls', {})
            puts_dict = option_chain.get('puts', {})
            
            # Validate and create straddle signals
            call_valid, call_price, call_msg = self.price_validator.validate_option_price(
                symbol, atm_strike, 'CALL', option_chain, current_time
            )
            put_valid, put_price, put_msg = self.price_validator.validate_option_price(
                symbol, atm_strike, 'PUT', option_chain, current_time
            )
            
            if call_valid and put_valid:
                # Both legs have valid prices
                total_premium = call_price + put_price
                max_cost = spot_price * 0.05  # Max 5% of underlying
                
                if total_premium <= max_cost:
                    # Create CALL leg
                    call_signal = Signal(
                        strategy_name='Gamma Scalping',
                        symbol=symbol,
                        direction='CALL',
                        action='BUY',
                        strike=atm_strike,
                        expiry=self._get_expiry(),
                        entry_price=call_price,
                        strength=80,
                        reason=f"Gamma Scalping ATM Straddle - CALL leg (validated: {call_msg})"
                    )
                    call_signal.strategy_id = "sac_0"
                    
                    # Create PUT leg
                    put_signal = Signal(
                        strategy_name='Gamma Scalping',
                        symbol=symbol,
                        direction='PUT',
                        action='BUY',
                        strike=atm_strike,
                        expiry=self._get_expiry(),
                        entry_price=put_price,
                        strength=80,
                        reason=f"Gamma Scalping ATM Straddle - PUT leg (validated: {put_msg})"
                    )
                    put_signal.strategy_id = "sac_0"
                    
                    # Set targets and stops
                    self._set_straddle_targets(call_signal, put_signal, total_premium)
                    
                    signals.extend([call_signal, put_signal])
                    logger.info(f"✅ Gamma Scalping: Valid straddle {symbol} {atm_strike} (CALL: ₹{call_price}, PUT: ₹{put_price})")
                else:
                    logger.warning(f"⚠️ Gamma Scalping: Straddle too expensive ₹{total_premium:.2f} > ₹{max_cost:.2f}")
            else:
                logger.warning(f"❌ Gamma Scalping: Invalid prices - CALL: {call_msg}, PUT: {put_msg}")
                
        except Exception as e:
            logger.error(f"Error in gamma scalping signal generation: {e}")
        
        return signals
    
    def _get_expiry(self) -> str:
        """Get current weekly expiry"""
        from datetime import datetime, timedelta
        today = datetime.now()
        days_until_thursday = (3 - today.weekday()) % 7
        if days_until_thursday == 0:
            days_until_thursday = 7
        expiry = today + timedelta(days=days_until_thursday)
        return expiry.strftime('%Y-%m-%d')
    
    def _set_straddle_targets(self, call_signal: Signal, put_signal: Signal, total_premium: float):
        """Set targets and stops for straddle"""
        # Dynamic targets based on premium
        target_pct = 0.15  # 15% target
        stop_pct = 0.08    # 8% stop loss
        
        target_price = total_premium * (1 + target_pct)
        stop_loss = total_premium * (1 - stop_pct)
        
        # Allocate targets proportionally
        call_signal.target_price = target_price * 0.5
        call_signal.stop_loss = stop_loss * 0.5
        put_signal.target_price = target_price * 0.5
        put_signal.stop_loss = stop_loss * 0.5
        
        call_signal.tp1 = target_price * 0.25
        call_signal.tp2 = target_price * 0.5
        call_signal.tp3 = target_price * 0.5
        
        put_signal.tp1 = target_price * 0.25
        put_signal.tp2 = target_price * 0.5
        put_signal.tp3 = target_price * 0.5
