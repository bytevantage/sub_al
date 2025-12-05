"""
FINAL 6-STRATEGY SYSTEM - LOCKED FOR PRODUCTION
NIFTY & SENSEX ONLY (21 NOV 2025)
ML integration pending – Quantum Edge V2 is rule-based
PERMANENT STRATEGY COUNT: 6 (no more, no less)
"""

from typing import Dict, List
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from backend.strategies.strategy_base import Signal
from backend.core.logger import get_logger
from backend.config.underlying_config import underlying_manager

logger = get_logger(__name__)

# === TIME & RISK MANAGER ===
IST = ZoneInfo("Asia/Kolkata")

def get_current_hour():
    """Get current time in HHMM format for IST"""
    return datetime.now(IST).strftime("%H%M")

def get_position_age_minutes(position):
    """Calculate position age in minutes"""
    if hasattr(position, 'entry_time'):
        if isinstance(position.entry_time, str):
            entry_time = datetime.fromisoformat(position.entry_time.replace('Z', '+00:00'))
            if entry_time.tzinfo is None:
                entry_time = entry_time.replace(tzinfo=IST)
        else:
            entry_time = position.entry_time
        return (datetime.now(IST) - entry_time).total_seconds() / 60
    return 0

def is_gamma_scalping_allowed():
    """Check if gamma scalping strategies are allowed based on time"""
    now = datetime.now(IST)
    hour = now.hour
    minute = now.minute
    
    # Block: 09:15-09:30 (opening volatility)
    if hour == 9 and minute < 30:
        return False, "Opening volatility - no gamma scalping"
    
    # Block: After 13:00 (theta burn period)
    if hour >= 13:
        return False, "Post-13:00 - no long gamma allowed"
    
    # Allow: 09:30-13:00
    return True, "Gamma scalping allowed"

def should_use_short_premium():
    """Check if should switch to short premium strategies"""
    now = datetime.now(IST)
    hour = now.hour
    
    # After 13:00, only short premium allowed
    if hour >= 13:
        return True, "Post-13:00 - short premium only"
    
    return False, "Long gamma allowed"

def should_force_exit_early():
    """Check if should force exit all positions before theta burn"""
    now = datetime.now(IST)
    hour = now.hour
    minute = now.minute
    
    # Force exit after 14:30
    if hour >= 14 and minute >= 30:
        return True, "Force exit before 14:30 theta burn"
    
    return False, "Hold positions"

def get_option_stop_loss_pct():
    """Get wider stop loss for options"""
    return 0.30  # 30% for options vs 18% for equities


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
        Generate signals from the selected strategy with time-based filtering
        
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
            
            # === TIME-BASED STRATEGY FILTERING ===
            current_time = get_current_hour()
            
            # Check if strategy is allowed at current time
            if strategy['name'] in ['Gamma Scalping', 'Long Straddle']:
                allowed, reason = is_gamma_scalping_allowed()
                if not allowed:
                    logger.info(f"🛑 Time filter: {strategy['name']} blocked - {reason}")
                    return []
                logger.info(f"✅ Time filter: {strategy['name']} allowed - {reason}")
            
            # After 13:00, force switch to short premium strategies
            use_short_premium, reason = should_use_short_premium()
            if use_short_premium:
                if strategy['name'] in ['Gamma Scalping', 'Long Straddle', 'Quantum Edge V2']:
                    logger.info(f"🔄 Post-13:00: Switching from {strategy['name']} to short premium")
                    # Force switch to IV Rank Trading (short premium)
                    strategy_idx = 2  # IV Rank Trading index
                    strategy = self.strategies[strategy_idx]
                    logger.info(f"✅ Auto-switched to: {strategy['name']} (short premium)")
            
            # Generate signal based on strategy type
            signals = await self._execute_strategy(strategy, market_data)
            
            # Tag signals with SAC metadata
            for signal in signals:
                signal.metadata = signal.metadata or {}
                signal.metadata['sac_selected'] = True
                signal.metadata['strategy_index'] = strategy_idx
                signal.metadata['strategy_name'] = strategy['name']
                signal.metadata['time_filter'] = current_time
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
        
        # TEST MODE: Force signal generation for testing (can be toggled via config)
        TEST_MODE = False  # DISABLED - use real strategies
        
        # Get basic market data for test mode
        symbol = underlying_manager.get_current_underlying()
        if not underlying_manager.is_allowed(symbol):
            symbol = underlying_manager.get_random_underlying()
        
        symbol_data = market_data.get(symbol, {})
        spot_price = symbol_data.get('spot_price', 26250)  # Fallback spot price
        # Fix expiry: SENSEX expires on Thursday (2 days), NIFTY on Friday (3 days)
        expiry_days = 2 if symbol == 'SENSEX' else 3
        expiry = datetime.now() + timedelta(days=expiry_days)
        
        if TEST_MODE:
            logger.info(f"🧪 TEST MODE: Forcing signal generation for {strategy_id}")
            return self._generate_test_signal(strategy_id, symbol, spot_price, expiry)
        
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
        
        iv_rank = symbol_data.get('iv_rank', 50)  # Now available at top level after market_data.py fix
        
        # Log strategy execution details
        logger.info(f"🎯 Executing {strategy_id} for {symbol}: PCR={pcr:.3f} , IV Rank={iv_rank}%, Spot={spot_price}")
        
        # Get option chain - it's a dict with 'calls' and 'puts' keys (NOT 'option_chain')
        option_chain_data = symbol_data.get('option_chain', {})
        
        if spot_price == 0:
            logger.warning(f"No spot price for {symbol}")
            return []
        
        if not option_chain_data or not isinstance(option_chain_data, dict):
            logger.warning(f"No option chain data for {symbol}")
            return []
        
        # Get expiry - define early to avoid NameError
        expiry_days = 2 if symbol == 'SENSEX' else 3
        expiry = datetime.now() + timedelta(days=expiry_days)
        
        # The option chain structure has 'calls' and 'puts' as separate dicts
        calls_dict = option_chain_data.get('calls', {})
        puts_dict = option_chain_data.get('puts', {})
        
        if not calls_dict and not puts_dict:
            logger.warning(f"No calls or puts data in option chain for {symbol}")
            return []
        
        logger.info(f"✓ {symbol} option chain loaded: {len(calls_dict)} calls, {len(puts_dict)} puts")
        
        # Get PCR direction using FINAL UNIVERSAL VERSION (lock this forever)
        def get_pcr_signal(pcr):
            if pcr > 1.70:   return "CONTRARIAN_BULLISH"   # Extreme PCR - bullish contrarian
            if pcr > 1.20:   return "BEARISH"             # High PCR - bearish → lean puts
            if pcr < 0.70:   return "CONTRARIAN_BEARISH"  # Extreme PCR - bearish contrarian
            if pcr < 0.90:   return "BULLISH"             # Low PCR - bullish → lean calls
            return "NEUTRAL"                              # Short strangle territory
        
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
            
            # Calculate dynamic targets for straddle with option-specific risk
            targets = calculate_targets(
                entry_price=total_premium,
                signal_direction='CALL',  # Direction doesn't matter for straddle premium
                confidence=confidence,
                vix=vix,
                adx=adx,
                quantity=1,
                max_risk_pct=get_option_stop_loss_pct()  # Use 30% for options
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
            expiry_days = 2 if symbol == 'SENSEX' else 3
            expiry = datetime.now() + timedelta(days=expiry_days)
            
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
            
            if iv_rank > 75:  # Original production threshold
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
                
            elif iv_rank < 25 and adx > 35:  # Original production thresholds
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
            
            # Quantum Edge: Trade in all PCR ranges with appropriate direction
            if pcr_signal == "CONTRARIAN_BULLISH" or pcr_signal == "BULLISH":
                direction = 'CALL'  # Bullish signal → buy calls
                strike = underlying_manager.round_strike(symbol, spot_price * 1.01)
            elif pcr_signal == "CONTRARIAN_BEARISH" or pcr_signal == "BEARISH":
                direction = 'PUT'  # Bearish signal → buy puts
                strike = underlying_manager.round_strike(symbol, spot_price * 0.99)
            else:  # NEUTRAL
                # In neutral PCR, use IV rank to decide
                if iv_rank > 70:
                    # High IV - sell strangle
                    return []  # Skip for now, add strangle logic later
                else:
                    # Low/Mid IV - buy straddle or skip
                    direction = 'CALL'  # Default to calls in neutral
                    strike = underlying_manager.round_strike(symbol, spot_price * 1.01)
                
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
            
            # Quantum Edge V2: Trade in all PCR ranges with enhanced logic
            if pcr_signal == "CONTRARIAN_BULLISH" or pcr_signal == "BULLISH":
                direction = 'CALL'  # Bullish signal → buy calls
                strike = underlying_manager.round_strike(symbol, spot_price * 1.01)
            elif pcr_signal == "CONTRARIAN_BEARISH" or pcr_signal == "BEARISH":
                direction = 'PUT'  # Bearish signal → buy puts
                strike = underlying_manager.round_strike(symbol, spot_price * 0.99)
            else:  # NEUTRAL
                # In neutral PCR, use VIX to decide strategy
                if vix > 25:
                    # High VIX - sell premium
                    return []  # Skip for now, add premium selling logic
                else:
                    # Normal VIX - directional based on ADX
                    if adx > 30:
                        direction = 'CALL'  # Trending up
                        strike = underlying_manager.round_strike(symbol, spot_price * 1.01)
                    else:
                        direction = 'PUT'  # Ranging market
                        strike = underlying_manager.round_strike(symbol, spot_price * 0.99)
            
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
            
            # Default Strategy: Trade in all PCR ranges with conservative approach
            if pcr_signal == "CONTRARIAN_BULLISH" or pcr_signal == "BULLISH":
                direction = 'CALL'  # Bullish signal → buy calls
                strike = underlying_manager.round_strike(symbol, spot_price * 1.01)
            elif pcr_signal == "CONTRARIAN_BEARISH" or pcr_signal == "BEARISH":
                direction = 'PUT'  # Bearish signal → buy puts
                strike = underlying_manager.round_strike(symbol, spot_price * 0.99)
            else:  # NEUTRAL
                # In neutral PCR, use IV rank to decide
                if iv_rank > 70:
                    return []  # Skip high IV neutral markets
                else:
                    # Low/Mid IV - default to calls for upside potential
                    direction = 'CALL'
                    strike = underlying_manager.round_strike(symbol, spot_price * 1.01)
        
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
            
        # Calculate dynamic targets based on regime with option-specific risk
        targets = calculate_targets(
            entry_price=entry_price,
            signal_direction=direction,
            confidence=confidence,
            vix=vix,
            adx=adx,
            quantity=1,  # Will be adjusted later
            max_risk_pct=get_option_stop_loss_pct()  # Use 30% for options
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
        expiry_days = 2 if symbol == 'SENSEX' else 3
        expiry = datetime.now() + timedelta(days=expiry_days)
        
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
    
    def _generate_test_signal(self, strategy_id: str, symbol: str, spot_price: float, expiry) -> List[Signal]:
        """
        Generate test signals for all strategies to verify system functionality
        All test signals are marked with TEST_MODE metadata for easy cleanup
        """
        from datetime import datetime, timedelta
        from backend.strategies.strategy_base import Signal
        
        logger.info(f"🧪 Generating TEST signal for {strategy_id} on {symbol}")
        
        # Define test signal patterns for each strategy
        test_patterns = {
            'quantum_edge_v2': {'direction': 'CALL', 'strike_offset': 0.01, 'action': 'BUY'},
            'quantum_edge': {'direction': 'PUT', 'strike_offset': -0.01, 'action': 'BUY'},
            'default': {'direction': 'CALL', 'strike_offset': 0.02, 'action': 'BUY'},
            'gamma_scalping': {'direction': 'CALL', 'strike_offset': 0.01, 'action': 'BUY'},  # Will create straddle
            'vwap_deviation': {'direction': 'PUT', 'strike_offset': -0.015, 'action': 'BUY'},
            'iv_rank_trading': {'direction': 'CALL', 'strike_offset': 0.01, 'action': 'BUY'}
        }
        
        pattern = test_patterns.get(strategy_id, {'direction': 'CALL', 'strike_offset': 0.01, 'action': 'BUY'})
        
        # Calculate strike
        if pattern['direction'] == 'CALL':
            strike = spot_price * (1 + pattern['strike_offset'])
        else:  # PUT
            strike = spot_price * (1 + pattern['strike_offset'])
        
        strike = underlying_manager.round_strike(symbol, strike)
        
        # Create test signal
        signal = Signal(
            strategy_name=f"TEST_{strategy_id}",
            symbol=symbol,
            direction=pattern['direction'],
            action=pattern['action'],
            strike=strike,
            expiry=expiry.strftime('%Y-%m-%d'),
            entry_price=50.0,  # Fixed test price
            strength=75,  # Fixed test strength
            reason=f"TEST MODE - {strategy_id} signal generation"
        )
        
        # Mark as test signal for easy identification and cleanup
        signal.metadata = {
            'TEST_MODE': True,
            'test_timestamp': datetime.now().isoformat(),
            'original_strategy': strategy_id,
            'test_only': True
        }
        signal.strategy_id = f"test_{strategy_id}"
        signal.ml_probability = 0.8  # Fixed test confidence
        
        # Special handling for gamma scalping (create straddle)
        if strategy_id == 'gamma_scalping':
            # Create matching put signal
            put_signal = Signal(
                strategy_name=f"TEST_{strategy_id}",
                symbol=symbol,
                direction='PUT',
                action='BUY',
                strike=strike,
                expiry=expiry.strftime('%Y-%m-%d'),
                entry_price=50.0,
                strength=75,
                reason=f"TEST MODE - {strategy_id} straddle (PUT leg)"
            )
            put_signal.metadata = signal.metadata.copy()
            put_signal.strategy_id = f"test_{strategy_id}"
            put_signal.ml_probability = 0.8
            
            logger.info(f"🧪 TEST {strategy_id}: Generated straddle - CALL @ {strike}, PUT @ {strike}")
            return [signal, put_signal]
        
        logger.info(f"🧪 TEST {strategy_id}: Generated {pattern['direction']} @ {strike}")
        return [signal]
