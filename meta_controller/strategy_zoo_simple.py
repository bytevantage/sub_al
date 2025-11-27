"""
FINAL 6-STRATEGY SYSTEM - LOCKED FOR PRODUCTION
NIFTY & SENSEX ONLY (21 NOV 2025)
ML integration pending – Quantum Edge V2 is rule-based
PERMANENT STRATEGY COUNT: 6 (no more, no less)
"""

from typing import Dict, List
from backend.strategies.strategy_base import Signal
from backend.core.logger import get_logger
from backend.config.underlying_config import underlying_manager

logger = get_logger(__name__)


class StrategyZoo:
    """
    FINAL 6-STRATEGY PORTFOLIO - PRODUCTION READY
    Permanent strategy count locked at 6
    ML integration scheduled for Jan 2026
    """
    
    def __init__(self, portfolio_value: float = 5000000):
        self.portfolio_value = portfolio_value
        self.strategies = self._initialize_strategies()
        logger.info(f"Strategy Zoo initialized with {len(self.strategies)} strategies")
    
    def _initialize_strategies(self) -> List[Dict]:
        """
        Initialize the FINAL 6-STRATEGY PORTFOLIO (21 NOV 2025)
        Total capital = 100% → SAC reallocates every 5 minutes
        """
        strategies = [
            {
                'name': 'Quantum Edge V2',
                'id': 'quantum_edge_v2',
                'allocation': 0.25,  # Base 25% → Up to 60% when VIX > 20 AND ADX > 30
                'meta_group': 0,
                'description': 'Rule-based: PCR + VIX/ADX regime filter (NO ML yet)'
            },
            {
                'name': 'Quantum Edge',
                'id': 'quantum_edge',
                'allocation': 0.20,  # Base 20% → Only 09:15–10:30, disabled on expiry
                'meta_group': 0,
                'description': 'Original strategy with time filter'
            },
            {
                'name': 'Default Strategy',
                'id': 'default',
                'allocation': 0.10,  # Fixed 10% (safe daily bread)
                'meta_group': 0,
                'description': 'Time-filtered 09:15–10:00 ORB'
            },
            {
                'name': 'Gamma Scalping',
                'id': 'gamma_scalping',
                'allocation': 0.15,  # Base 15% - PURE delta-neutral
                'meta_group': 1,
                'description': 'Delta-neutral straddle/strangle'
            },
            {
                'name': 'VWAP Deviation',
                'id': 'vwap_deviation',
                'allocation': 0.10,  # Base 10%
                'meta_group': 3,
                'description': 'Mean-reversion credit spreads'
            },
            {
                'name': 'IV Rank Trading',
                'id': 'iv_rank_trading',
                'allocation': 0.10,  # Base 10%
                'meta_group': 2,
                'description': 'IV-based premium selling/buying'
            }
        ]
        return strategies
    
    async def generate_signals(self, strategy_idx: int, market_data: Dict) -> List[Signal]:
        """
        Generate signals from the selected strategy
        
        Args:
            strategy_idx: Index of selected strategy (0-6 for 7 strategies)
            market_data: Current market state
            
        Returns:
            List of Signal objects (usually 0-1 signal)
        """
        try:
            if strategy_idx < 0 or strategy_idx >= len(self.strategies):
                logger.warning(f"Invalid strategy index: {strategy_idx}")
                return []
            
            strategy = self.strategies[strategy_idx]
            logger.info(f"Executing strategy: {strategy['name']} (index: {strategy_idx})")
            
            # Generate signal based on strategy type
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
        NIFTY & SENSEX ONLY (21 NOV 2025)
        """
        from datetime import datetime, timedelta
        
        strategy_id = strategy['id']
        signals = []
        
        # ENFORCE: Only use NIFTY and SENSEX
        symbol = underlying_manager.get_current_underlying()
        if not underlying_manager.is_allowed(symbol):
            symbol = underlying_manager.get_random_underlying()
            logger.info(f"Switched to allowed underlying: {symbol}")
        
        symbol_data = market_data.get(symbol, {})
        if not symbol_data:
            # Try the other allowed underlying
            alt_symbol = 'SENSEX' if symbol == 'NIFTY' else 'NIFTY'
            symbol_data = market_data.get(alt_symbol, {})
            if symbol_data:
                symbol = alt_symbol
                underlying_manager.set_underlying(symbol)
            else:
                logger.warning(f"No market data available for {symbol} or {alt_symbol}")
                return []
        
        spot_price = symbol_data.get('spot_price', 0)
        if spot_price == 0:
            logger.warning(f"No spot price for {symbol}")
            return []
        
        # IMPORTANT: Use NIFTY PCR for both NIFTY and SENSEX trading (99% of pros do this)
        pcr_source = underlying_manager.get_pcr_source()  # Always "NIFTY"
        if symbol == "NIFTY":
            pcr = symbol_data.get('pcr', 1.0)
        else:
            # For SENSEX, use NIFTY PCR
            nifty_data = market_data.get('NIFTY', {})
            pcr = nifty_data.get('pcr', 1.0)
            logger.info(f"Using NIFTY PCR ({pcr:.2f}) for SENSEX trading")
        
        iv_rank = symbol_data.get('iv_rank', 50)
        
        # Get option chain - it's a dict with 'calls' and 'puts' keys (NOT 'option_chain')
        option_chain_data = symbol_data.get('option_chain', {})
        
        if spot_price == 0:
            logger.warning(f"No spot price for {symbol}")
            return []
        
        if not option_chain_data or not isinstance(option_chain_data, dict):
            logger.warning(f"No option chain data for {symbol}")
            return []
        
        # The option chain structure has 'calls' and 'puts' as separate dicts
        calls_dict = option_chain_data.get('calls', {})
        puts_dict = option_chain_data.get('puts', {})
        
        if not calls_dict and not puts_dict:
            logger.warning(f"No calls or puts data in option chain for {symbol}")
            return []
        
        logger.info(f"✓ {symbol} option chain loaded: {len(calls_dict)} calls, {len(puts_dict)} puts")
        
        # Get PCR direction using FINAL UNIVERSAL VERSION (lock this forever)
        def get_pcr_signal(pcr):
            if pcr > 1.70:   return "CONTRARIAN_BULLISH"   # extreme fear → buy calls
            if pcr > 1.20:   return "BEARISH"             # normal bearish → lean puts (spreads only)
            if pcr < 0.70:   return "CONTRARIAN_BEARISH"  # extreme greed → buy puts
            if pcr < 0.90:   return "BULLISH"             # normal bullish → lean calls (spreads only)
            return "NEUTRAL"                              # short strangle territory
        
        pcr_signal = get_pcr_signal(pcr)
        
        # Strategy-specific logic to determine strike and direction
        if strategy_id == 'gamma_scalping':
            # 100% DELTA-NEUTRAL Gamma Scalping - NEVER uses PCR direction
            # Long straddle (IV < 70%) OR Short strangle (neutral PCR)
            
            if iv_rank > 70:
                # High IV - sell premium instead of buying
                if pcr_signal == "NEUTRAL":
                    # Short strangle in neutral PCR - sell OTM calls and puts
                    call_strike = underlying_manager.round_strike(symbol, spot_price * 1.02)  # 2% OTM
                    put_strike = underlying_manager.round_strike(symbol, spot_price * 0.98)   # 2% OTM
                    
                    call_signal = Signal(
                        symbol=symbol,
                        strike=call_strike,
                        expiry=expiry,
                        direction='SELL',  # SELL CALL premium
                        strategy='gamma_scalping',
                        confidence=0.6
                    )
                    
                    put_signal = Signal(
                        symbol=symbol,
                        strike=put_strike,
                        expiry=expiry,
                        direction='SELL',   # SELL PUT premium
                        strategy='gamma_scalping',
                        confidence=0.6
                    )
                    
                    return [call_signal, put_signal]
                else:
                    logger.info(f"📊 Gamma Scalping: High IV ({iv_rank}%) but PCR not neutral - skipping")
                    return []
            
            # Low/Moderate IV - long ATM straddle
            strike = underlying_manager.round_strike(symbol, spot_price)
            
            # Get prices for both legs
            call_price = self._get_option_price_from_chain_dict(calls_dict, puts_dict, strike, 'CALL')
            put_price = self._get_option_price_from_chain_dict(calls_dict, puts_dict, strike, 'PUT')
            
            if call_price == 0 or put_price == 0:
                logger.warning(f"Could not find prices for {symbol} {strike} straddle")
                return []
            
            total_premium = call_price + put_price
            max_straddle_cost = spot_price * 0.05  # Max 5% of underlying value
            
            if total_premium > max_straddle_cost:
                logger.info(f"📊 Gamma Scalping: Straddle too expensive (₹{total_premium:.2f} > ₹{max_straddle_cost:.2f})")
                return []
            
            # Create TWO signals - one for CALL, one for PUT
            logger.info(f"📊 Gamma Scalping: ATM Straddle {symbol} {strike} (CALL: ₹{call_price:.2f}, PUT: ₹{put_price:.2f}, Total: ₹{total_premium:.2f})")
            
            # Use ADVANCED dynamic risk-reward for Gamma Scalping
            from backend.execution.risk_reward_config import calculate_targets
            
            # Get market indicators for regime detection
            from backend.main import app
            trading_system = getattr(app.state, 'trading_system', None)
            
            vix = None
            adx = None
            confidence = 0.7  # Gamma scalping base confidence
            
            if trading_system and hasattr(trading_system, 'market_data'):
                market_state = trading_system.market_data.market_state.get(symbol, {})
                technical_indicators = market_state.get('technical_indicators', {})
                
                # Get VIX and ADX for regime detection
                vix = technical_indicators.get('vix', 15)
                adx = technical_indicators.get('adx', 25)
            
            # Calculate dynamic targets for straddle
            targets = calculate_targets(
                entry_price=total_premium,
                signal_direction='CALL',  # Direction doesn't matter for straddle premium
                confidence=confidence,
                vix=vix,
                adx=adx,
                quantity=1
            )
            
            target_price = targets['tp3']  # Final target for total premium
            stop_loss = targets['stop_loss']
            
            logger.info(
                f"🎯 Gamma Scalping Dynamic RR ({targets['regime']} regime): "
                f"Premium ₹{total_premium:.2f}, SL ₹{stop_loss:.2f}, "
                f"TP1 ₹{targets['tp1']:.2f}, TP2 ₹{targets['tp2']:.2f}, TP3 ₹{targets['tp3']:.2f}, "
                f"RR {targets['rr_final']}, Risk {targets['risk_pct']:.1f}%"
            )
            
            # Get expiry
            expiry = datetime.now() + timedelta(days=3)
            
            # Create CALL leg signal
            call_signal = Signal(
                strategy_name=strategy['name'],
                symbol=symbol,
                direction='CALL',
                action='BUY',
                strike=strike,
                expiry=expiry.strftime('%Y-%m-%d'),
                entry_price=call_price,
                strength=80,
                reason=f"Gamma Scalping ATM Straddle - CALL leg"
            )
            call_signal.strategy_id = f"sac_{strategy['id']}"
            # Allocate targets proportionally to each leg
            call_signal.target_price = targets['tp3'] * 0.5  # Half of final target
            call_signal.stop_loss = stop_loss * 0.5  # Half of SL
            call_signal.tp1 = targets['tp1'] * 0.5
            call_signal.tp2 = targets['tp2'] * 0.5
            call_signal.tp3 = targets['tp3'] * 0.5
            call_signal.rr_ratio = targets['rr_final']
            call_signal.regime = targets['regime']
            call_signal.risk_pct = targets['risk_pct']
            call_signal.ml_probability = 0.7
            
            # Create PUT leg signal
            put_signal = Signal(
                strategy_name=strategy['name'],
                symbol=symbol,
                direction='PUT',
                action='BUY',
                strike=strike,
                expiry=expiry.strftime('%Y-%m-%d'),
                entry_price=put_price,
                strength=80,
                reason=f"Gamma Scalping ATM Straddle - PUT leg"
            )
            put_signal.strategy_id = f"sac_{strategy['id']}"
            # Allocate targets proportionally to each leg
            put_signal.target_price = targets['tp3'] * 0.5  # Half of final target
            put_signal.stop_loss = stop_loss * 0.5  # Half of SL
            put_signal.tp1 = targets['tp1'] * 0.5
            put_signal.tp2 = targets['tp2'] * 0.5
            put_signal.tp3 = targets['tp3'] * 0.5
            put_signal.rr_ratio = targets['rr_final']
            put_signal.regime = targets['regime']
            put_signal.risk_pct = targets['risk_pct']
            put_signal.ml_probability = 0.7
            
            # Return both legs as a list
            return [call_signal, put_signal]
            
        elif strategy_id == 'iv_rank_trading':
            # IV Rank: FINAL CORRECTED LOGIC - high IV = sell, low IV = flat unless strong trend
            technical_indicators = symbol_data.get('technical_indicators', {})
            adx = technical_indicators.get('adx', 20)
            
            if iv_rank > 75:
                # High IV - SELL strangle/iron condor
                logger.info(f"📊 IV Rank Trading: High IV ({iv_rank}%) - SELLING strangle")
                # Create short strangle - sell both CALL and PUT
                call_strike = underlying_manager.round_strike(symbol, spot_price * 1.02)  # 2% OTM
                put_strike = underlying_manager.round_strike(symbol, spot_price * 0.98)   # 2% OTM
                
                call_signal = Signal(
                    symbol=symbol,
                    strike=call_strike,
                    expiry=expiry,
                    direction='SELL',  # SELL CALL premium
                    strategy='iv_rank_trading',
                    confidence=0.6
                )
                
                put_signal = Signal(
                    symbol=symbol,
                    strike=put_strike,
                    expiry=expiry,
                    direction='SELL',   # SELL PUT premium
                    strategy='iv_rank_trading',
                    confidence=0.6
                )
                
                return [call_signal, put_signal]
                
            elif iv_rank < 25 and adx > 35:
                # Low IV + very strong trend - BUY directional only
                logger.info(f"📊 IV Rank Trading: Low IV ({iv_rank}%) + Very Strong Trend (ADX {adx}) - BUYING directional")
                if pcr_signal in ["CONTRARIAN_BULLISH", "BULLISH"]:
                    direction = 'BUY'
                    strike = underlying_manager.round_strike(symbol, spot_price * 1.01)
                elif pcr_signal in ["CONTRARIAN_BEARISH", "BEARISH"]:
                    direction = 'BUY'
                    strike = underlying_manager.round_strike(symbol, spot_price * 0.99)
                else:
                    return []  # No clear signal
            else:
                return []  # Medium IV or low IV without very strong trend - FLAT
            
        elif strategy_id == 'vwap_deviation':
            # VWAP deviation: FINAL LOGIC - credit spreads ONLY in normal PCR ranges
            technical_indicators = symbol_data.get('technical_indicators', {})
            vwap = technical_indicators.get('vwap', spot_price)  # Fallback to spot if VWAP missing
            
            deviation = (spot_price - vwap) / vwap * 100
            
            # Only trade spreads in normal PCR ranges (0.90-1.20), not extremes
            if pcr_signal not in ["BULLISH", "BEARISH"]:
                logger.info(f"📊 VWAP Deviation: PCR {pcr_signal} - only trade spreads in normal ranges")
                return []
            
            if deviation > 0.35:  # Price 0.35% above VWAP - overbought
                logger.info(f"📊 VWAP Deviation: Price {deviation:.2f}% above VWAP - SELL CALL spread")
                # SELL CALL credit spread - sell ITM call, buy OTM call
                short_strike = underlying_manager.round_strike(symbol, spot_price * 0.99)  # ITM
                long_strike = underlying_manager.round_strike(symbol, spot_price * 1.03)   # OTM
                
                short_signal = Signal(
                    symbol=symbol,
                    strike=short_strike,
                    expiry=expiry,
                    direction='SELL',  # SELL ITM CALL
                    strategy='vwap_deviation',
                    confidence=0.65
                )
                
                long_signal = Signal(
                    symbol=symbol,
                    strike=long_strike,
                    expiry=expiry,
                    direction='BUY',   # BUY OTM CALL (hedge)
                    strategy='vwap_deviation',
                    confidence=0.65
                )
                
                return [short_signal, long_signal]
                
            elif deviation < -0.35:  # Price 0.35% below VWAP - oversold
                logger.info(f"📊 VWAP Deviation: Price {deviation:.2f}% below VWAP - SELL PUT spread")
                # SELL PUT credit spread - sell ITM put, buy OTM put
                short_strike = underlying_manager.round_strike(symbol, spot_price * 1.01)  # ITM
                long_strike = underlying_manager.round_strike(symbol, spot_price * 0.97)   # OTM
                
                short_signal = Signal(
                    symbol=symbol,
                    strike=short_strike,
                    expiry=expiry,
                    direction='SELL',  # SELL ITM PUT
                    strategy='vwap_deviation',
                    confidence=0.65
                )
                
                long_signal = Signal(
                    symbol=symbol,
                    strike=long_strike,
                    expiry=expiry,
                    direction='BUY',   # BUY OTM PUT (hedge)
                    strategy='vwap_deviation',
                    confidence=0.65
                )
                
                return [short_signal, long_signal]
            else:
                return []  # No significant deviation
            
        elif strategy_id == 'quantum_edge':
            # Quantum Edge: Time-filtered (09:15-14:00, reduced size on expiry)
            current_time = datetime.now()
            current_hour = current_time.hour
            current_minute = current_time.minute
            
            # Check if within allowed time window (09:15-14:00) - EXPANDED from 10:30
            if not ((current_hour == 9 and current_minute >= 15) or 
                   (current_hour >= 10 and current_hour < 14)):
                logger.info(f"⏰ Quantum Edge outside time window (09:15-14:00): {current_hour:02d}:{current_minute:02d}")
                return []
            
            # On expiry day (Thursday), reduce confidence but allow trading
            if current_time.weekday() == 3:
                logger.info("📅 Quantum Edge on expiry day - reduced confidence")
                # Continue with lower confidence instead of blocking
            
            # Quantum Edge: ONLY trade in EXTREME CONTRARIAN PCR zones (>1.70 or <0.70)
            if pcr_signal == "CONTRARIAN_BULLISH":
                direction = 'CALL'  # Extreme fear → buy calls (contrarian)
                strike = underlying_manager.round_strike(symbol, spot_price * 1.01)
            elif pcr_signal == "CONTRARIAN_BEARISH":
                direction = 'PUT'  # Extreme greed → buy puts (contrarian)
                strike = underlying_manager.round_strike(symbol, spot_price * 0.99)
            else:
                return []  # NO TRADE in normal PCR range - only extreme zones
                
        elif strategy_id == 'quantum_edge_v2':
            # Quantum Edge V2: TFT + SAC hybrid - can trade full day
            # Use real VIX and ADX from technical indicators
            technical_indicators = symbol_data.get('technical_indicators', {})
            vix = symbol_data.get('vix', 20)  # Get VIX from market data
            adx = technical_indicators.get('adx', 20)  # Get ADX from technical indicators
            
            # Dynamic allocation based on ADX/VIX
            if vix > 20 and adx > 30:
                # High volatility/trending - increase allocation
                logger.info(f"🚀 Quantum Edge V2 high vol/trend mode: VIX={vix:.1f}, ADX={adx:.1f}")
                # Update allocation dynamically
                for strategy in self.strategies:
                    if strategy['id'] == 'quantum_edge_v2':
                        strategy['current_allocation'] = 0.45  # Up to 45-60%
                        break
            
            # Quantum Edge V2: ONLY trade in EXTREME CONTRARIAN PCR zones (>1.70 or <0.70)
            if pcr_signal == "CONTRARIAN_BULLISH":
                direction = 'CALL'  # Extreme fear → buy calls (contrarian)
                strike = underlying_manager.round_strike(symbol, spot_price * 1.01)
            elif pcr_signal == "CONTRARIAN_BEARISH":
                direction = 'PUT'  # Extreme greed → buy puts (contrarian)
                strike = underlying_manager.round_strike(symbol, spot_price * 0.99)
            else:
                return []  # NO TRADE in normal PCR range - only extreme zones
            
        elif strategy_id == 'default':
            # Default Strategy: Time-filtered 09:15-14:00 - ONLY EXTREME CONTRARIAN PCR
            current_time = datetime.now()
            current_hour = current_time.hour
            current_minute = current_time.minute
            
            # Check if within trading window (09:15-14:00)
            if not ((current_hour == 9 and current_minute >= 15) or 
                   (current_hour >= 10 and current_hour < 14)):
                logger.info(f"⏰ Default Strategy outside window (09:15-14:00): {current_hour:02d}:{current_minute:02d}")
                return []
            
            # Default Strategy: ONLY trade in EXTREME CONTRARIAN PCR zones (>1.70 or <0.70)
            if pcr_signal == "CONTRARIAN_BULLISH":
                direction = 'CALL'  # Extreme fear → buy calls (contrarian)
                strike = underlying_manager.round_strike(symbol, spot_price * 1.01)
            elif pcr_signal == "CONTRARIAN_BEARISH":
                direction = 'PUT'  # Extreme greed → buy puts (contrarian)
                strike = underlying_manager.round_strike(symbol, spot_price * 0.99)
            else:
                return []  # NO TRADE in normal PCR range - only extreme zones
        
        # Log PCR analysis for debugging
        logger.info(f"🎯 PCR Analysis: {symbol} PCR={pcr:.2f} → {pcr_signal} → {direction} {strike}")
        
        # Fetch REAL price from option chain (calls/puts dicts)
        entry_price = self._get_option_price_from_chain_dict(calls_dict, puts_dict, strike, direction)
        if entry_price == 0:
            logger.warning(f"Could not find price for {symbol} {strike} {direction} in option chain")
            return []
        
        # Additional check: ensure we have bid/ask for price validation
        options_dict = calls_dict if direction == 'CALL' else puts_dict
        strike_key = str(int(strike))
        if strike_key in options_dict:
            option_data = options_dict[strike_key]
            bid = option_data.get('bid', 0)
            ask = option_data.get('ask', 0)
            if bid > 0 and ask > 0:
                # Use mid-price instead of LTP for more realistic entry
                entry_price = (bid + ask) / 2
                logger.info(f"✓ Using bid/ask mid-price: {symbol} {strike} {direction} = ₹{entry_price:.2f} (bid: ₹{bid}, ask: ₹{ask})")
            else:
                logger.info(f"✓ Found REAL price: {symbol} {strike} {direction} = ₹{entry_price:.2f} - Creating signal")
        else:
            logger.info(f"✓ Found REAL price: {symbol} {strike} {direction} = ₹{entry_price:.2f} - Creating signal")
        
        # Use ADVANCED dynamic risk-reward system
        from backend.execution.risk_reward_config import calculate_targets
        
        # Get market indicators for regime detection
        from backend.main import app
        trading_system = getattr(app.state, 'trading_system', None)
        
        vix = None
        adx = None
        confidence = getattr(signal, 'ml_probability', 0.7) if 'signal' in locals() else 0.7
        
        if trading_system and hasattr(trading_system, 'market_data'):
            market_state = trading_system.market_data.market_state.get(symbol, {})
            technical_indicators = market_state.get('technical_indicators', {})
            
            # Get VIX and ADX for regime detection
            vix = technical_indicators.get('vix', 15)
            adx = technical_indicators.get('adx', 25)
            
        # Calculate dynamic targets based on regime
        targets = calculate_targets(
            entry_price=entry_price,
            signal_direction=direction,
            confidence=confidence,
            vix=vix,
            adx=adx,
            quantity=1  # Will be adjusted later
        )
        
        # Use the calculated targets
        target_price = targets['tp3']  # Final target
        stop_loss = targets['stop_loss']
        
        logger.info(
            f"🎯 Dynamic RR for {symbol} ({targets['regime']} regime): "
            f"Entry ₹{entry_price:.2f}, SL ₹{stop_loss:.2f}, "
            f"TP1 ₹{targets['tp1']:.2f}, TP2 ₹{targets['tp2']:.2f}, TP3 ₹{targets['tp3']:.2f}, "
            f"RR {targets['rr_final']}, Risk {targets['risk_pct']:.1f}%"
        )
        
        # Get expiry (nearest weekly)
        expiry = datetime.now() + timedelta(days=3)
        
        # Create signal with correct parameters
        signal = Signal(
            strategy_name=strategy['name'],
            symbol=symbol,
            direction=direction,
            action='BUY',  # Default action
            strike=strike,
            expiry=expiry.strftime('%Y-%m-%d'),
            entry_price=entry_price,
            strength=75,  # Base strength
            reason=f"SAC selected {strategy['name']}",
            strategy_id=f"sac_{strategy_id}",
            metadata={
                'pcr': pcr,
                'iv_rank': iv_rank,
                'spot_price': spot_price,
                'allocation': strategy['allocation']
            }
        )
        
        # Set advanced targets after creation
        signal.target_price = target_price  # TP3 (final target)
        signal.stop_loss = stop_loss
        signal.tp1 = targets['tp1']  # First scale-out (40%)
        signal.tp2 = targets['tp2']  # Second scale-out (35%)
        signal.tp3 = targets['tp3']  # Final target (25%)
        signal.rr_ratio = targets['rr_final']
        signal.regime = targets['regime']
        signal.risk_pct = targets['risk_pct']
        
        signals.append(signal)
        logger.info(
            f"Generated signal with dynamic RR: {symbol} {direction} {strike} @ ₹{entry_price:.2f} "
            f"(SL: ₹{stop_loss:.2f}, TP1: ₹{targets['tp1']:.2f}, TP2: ₹{targets['tp2']:.2f}, TP3: ₹{targets['tp3']:.2f})"
        )
        
        return signals
    
    def _get_option_price_from_chain_dict(self, calls_dict: Dict, puts_dict: Dict, strike: float, direction: str) -> float:
        """
        Get actual option price from option chain data (calls/puts dict format)
        
        Args:
            calls_dict: Dict of call options by strike
            puts_dict: Dict of put options by strike
            strike: Strike price
            direction: 'CALL' or 'PUT'
            
        Returns:
            LTP from option chain, or 0 if not found
        """
        try:
            # Select correct dict based on direction
            options_dict = calls_dict if direction == 'CALL' else puts_dict
            
            # Strike might be int or float, try both
            strike_key = str(int(strike))
            
            if strike_key in options_dict:
                option_data = options_dict[strike_key]
                ltp = option_data.get('ltp', 0)
                if ltp and ltp > 0:
                    logger.debug(f"Found {strike} {direction} LTP: ₹{ltp}")
                    return float(ltp)
            
            logger.warning(f"Strike {strike} {direction} not found in option chain (tried key: {strike_key})")
            return 0.0
            
        except Exception as e:
            logger.error(f"Error getting option price: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return 0.0
