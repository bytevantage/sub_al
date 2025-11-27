"""
Simple Strategy Zoo for SAC - 6 Strategies with REAL OPTION CHAIN PRICES
"""

from typing import Dict, List
from backend.strategies.strategy_base import Signal
from backend.core.logger import get_logger
from datetime import datetime, timedelta

logger = get_logger(__name__)


class StrategyZoo:
    """
    Simplified Strategy Zoo with 6 strategies for SAC Meta-Controller
    Uses REAL prices from option chain - NO FAKE CALCULATIONS
    """
    
    def __init__(self, portfolio_value: float = 5000000):
        self.portfolio_value = portfolio_value
        self.strategies = self._initialize_strategies()
        logger.info(f"Strategy Zoo initialized with {len(self.strategies)} strategies")
    
    def _initialize_strategies(self) -> List[Dict]:
        """Initialize the 6 SAC strategies"""
        strategies = [
            {'name': 'Gamma Scalping', 'id': 'gamma_scalping', 'allocation': 0.15, 'meta_group': 1},
            {'name': 'IV Rank Trading', 'id': 'iv_rank_trading', 'allocation': 0.15, 'meta_group': 2},
            {'name': 'VWAP Deviation', 'id': 'vwap_deviation', 'allocation': 0.15, 'meta_group': 3},
            {'name': 'Default Strategy', 'id': 'default', 'allocation': 0.15, 'meta_group': 0},
            {'name': 'Quantum Edge V2', 'id': 'quantum_edge_v2', 'allocation': 0.25, 'meta_group': 0},
            {'name': 'Quantum Edge', 'id': 'quantum_edge', 'allocation': 0.25, 'meta_group': 0}
        ]
        return strategies
    
    async def generate_signals(self, strategy_idx: int, market_data: Dict) -> List[Signal]:
        """
        Generate signals from the selected strategy using REAL option chain prices
        """
        try:
            if strategy_idx < 0 or strategy_idx >= len(self.strategies):
                logger.warning(f"Invalid strategy index: {strategy_idx}")
                return []
            
            strategy = self.strategies[strategy_idx]
            logger.info(f"Executing strategy: {strategy['name']} (index: {strategy_idx})")
            
            # Execute strategy logic
            signals = await self._execute_strategy(strategy, market_data)
            
            # Tag signals with SAC metadata
            for signal in signals:
                signal.metadata = signal.metadata or {}
                signal.metadata['sac_selected'] = True
                signal.metadata['strategy_index'] = strategy_idx
                signal.metadata['strategy_name'] = strategy['name']
                signal.strategy_id = f"sac_{strategy['id']}"
                signal.strategy = strategy['name']
            
            return signals
            
        except Exception as e:
            logger.error(f"Error generating signals from strategy {strategy_idx}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []
    
    async def _execute_strategy(self, strategy: Dict, market_data: Dict) -> List[Signal]:
        """
        Execute specific strategy logic based on strategy ID
        ALWAYS uses real option chain prices - NO CALCULATIONS
        """
        strategy_id = strategy['id']
        signals = []
        
        # Get market data
        nifty_data = market_data.get('NIFTY', {})
        sensex_data = market_data.get('SENSEX', {})
        
        if not nifty_data and not sensex_data:
            logger.warning("No market data available for signal generation")
            return []
        
        # Choose primary symbol (prefer NIFTY)
        symbol_data = nifty_data if nifty_data else sensex_data
        symbol = 'NIFTY' if nifty_data else 'SENSEX'
        
        spot_price = symbol_data.get('spot_price', 0)
        pcr = symbol_data.get('pcr', 1.0)
        iv_rank = symbol_data.get('iv_rank', 50)
        
        # CRITICAL: Get option chain
        option_chain_data = symbol_data.get('option_chain', {})
        
        if spot_price == 0:
            logger.warning(f"No spot price for {symbol}")
            return []
        
        # Extract actual option chain list
        if isinstance(option_chain_data, dict):
            option_chain = option_chain_data.get('option_chain', [])
        elif isinstance(option_chain_data, list):
            option_chain = option_chain_data
        else:
            option_chain = []
        
        if not option_chain:
            logger.warning(f"No option chain data for {symbol} - cannot fetch real prices")
            return []
        
        logger.debug(f"{symbol} option chain has {len(option_chain)} strikes")
        
        # Determine strike and direction based on strategy logic
        strike = None
        direction = None
        
        if strategy_id == 'gamma_scalping':
            strike = round(spot_price / 100) * 100
            direction = 'CALL' if pcr > 1.2 else 'PUT'
            
        elif strategy_id == 'iv_rank_trading':
            if iv_rank > 70:
                direction = 'PUT'
                strike = round(spot_price * 0.98 / 100) * 100
            elif iv_rank < 30:
                direction = 'CALL'
                strike = round(spot_price * 1.02 / 100) * 100
            else:
                logger.debug(f"IV Rank {iv_rank} not extreme enough for signal")
                return []
            
        elif strategy_id == 'vwap_deviation':
            tech = symbol_data.get('technical_indicators', {})
            vwap = tech.get('vwap', spot_price)
            deviation = (spot_price - vwap) / vwap * 100
            
            if deviation > 0.5:
                direction = 'PUT'
                strike = round(spot_price / 100) * 100
            elif deviation < -0.5:
                direction = 'CALL'
                strike = round(spot_price / 100) * 100
            else:
                logger.debug(f"VWAP deviation {deviation:.2f}% not extreme enough")
                return []
            
        elif strategy_id in ['quantum_edge', 'quantum_edge_v2']:
            if pcr > 1.3:
                direction = 'CALL'
                strike = round(spot_price * 1.01 / 100) * 100
            elif pcr < 0.8:
                direction = 'PUT'
                strike = round(spot_price * 0.99 / 100) * 100
            else:
                logger.debug(f"PCR {pcr:.2f} not extreme enough for Quantum Edge")
                return []
            
        else:  # default
            if pcr > 1.2:
                direction = 'CALL'
                strike = round(spot_price * 1.01 / 100) * 100
            elif pcr < 0.9:
                direction = 'PUT'
                strike = round(spot_price * 0.99 / 100) * 100
            else:
                logger.debug(f"PCR {pcr:.2f} not extreme enough for Default")
                return []
        
        # CRITICAL: Fetch REAL price from option chain - NO FAKE CALCULATIONS!
        entry_price = self._get_option_price_from_chain(option_chain, strike, direction)
        
        if entry_price == 0:
            logger.warning(f"Could not find REAL price for {symbol} {strike} {direction} in option chain")
            return []
        
        logger.info(f"✓ Found REAL price: {symbol} {strike} {direction} = ₹{entry_price:.2f}")
        
        # Calculate targets based on REAL entry price
        target_price = entry_price * 1.15  # 15% profit
        stop_loss = entry_price * 0.92  # 8% stop loss
        
        # Get expiry (nearest weekly)
        expiry = datetime.now() + timedelta(days=3)
        
        # Create signal with REAL price
        signal = Signal(
            strategy_name=strategy['name'],
            symbol=symbol,
            direction=direction,
            action='BUY',
            strike=strike,
            expiry=expiry.strftime('%Y-%m-%d'),
            entry_price=entry_price,
            strength=75,
            reason=f"SAC {strategy['name']}: Real price ₹{entry_price:.2f} from option chain",
            strategy_id=f"sac_{strategy['id']}",
            metadata={
                'pcr': pcr,
                'iv_rank': iv_rank,
                'spot_price': spot_price,
                'allocation': strategy['allocation'],
                'real_price': True,
                'price_source': 'option_chain'
            }
        )
        
        # Set targets
        signal.target_price = target_price
        signal.stop_loss = stop_loss
        
        signals.append(signal)
        logger.info(f"Generated signal: {symbol} {direction} {strike} @ ₹{entry_price:.2f} (REAL option chain price)")
        
        return signals
    
    def _get_option_price_from_chain(self, option_chain: List[Dict], strike: float, direction: str) -> float:
        """
        Get ACTUAL option price from option chain data
        Returns 0 if not found - NO FAKE CALCULATIONS EVER
        """
        try:
            for entry in option_chain:
                if entry.get('strike_price') == strike:
                    # Get CE or PE data
                    option_data = entry.get('CE' if direction == 'CALL' else 'PE', {})
                    if option_data:
                        ltp = option_data.get('ltp', 0)
                        if ltp > 0:
                            logger.debug(f"Found {strike} {direction} LTP: ₹{ltp}")
                            return float(ltp)
            
            logger.warning(f"Strike {strike} {direction} not found in option chain with {len(option_chain)} strikes")
            return 0.0
            
        except Exception as e:
            logger.error(f"Error getting option price from chain: {e}")
            return 0.0
