"""
Smart Watchlist API
Combines 20+ strategies, ML predictions, and option chain analysis
to recommend high-probability profitable strikes
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from typing import List, Dict, Optional
from backend.core.timezone_utils import now_ist
from datetime import datetime, timedelta
from backend.core.logger import get_execution_logger
# from backend.strategies.strategy_engine import StrategyEngine  # DISABLED - Using SAC Meta-Controller only
from backend.ml.model_manager import ModelManager
from backend.api.market_data import get_live_market_data, get_option_chain_data
import asyncio

logger = get_execution_logger()

router = APIRouter(prefix="/api/watchlist", tags=["Watchlist"])

# Simple cache to prevent excessive API calls
_watchlist_cache = {}
_cache_timeout = 60  # 60 seconds cache timeout (increased from 30)


@router.get("/recommended-strikes")
async def get_recommended_strikes(
    symbol: str = Query("NIFTY", description="NIFTY, SENSEX, or BANKNIFTY"),
    min_ml_score: float = Query(0.0, description="Minimum ML confidence (0-1)"),
    min_strategy_strength: float = Query(75.0, description="Minimum strategy strength (0-100)"),
    min_strategies_agree: int = Query(1, description="Minimum strategies agreeing"),
    option_type: Optional[str] = Query(None, description="CALL or PUT (or both if None)"),
):
    """
    Get recommended strikes based on:
    - 20+ strategy signals
    - ML model predictions
    - Option chain analysis (PCR, OI, IV)
    - Market sentiment
    
    Returns ranked list of strikes with:
    - Entry price
    - Target price
    - Stop loss
    - Risk-reward ratio
    - Supporting strategies
    - ML confidence score
    - Market reasoning
    """
    
    try:
        # Check cache first to prevent excessive calls
        cache_key = f"{symbol}_{min_ml_score}_{min_strategy_strength}_{min_strategies_agree}_{option_type}"
        now = datetime.now()
        
        if cache_key in _watchlist_cache:
            cached_data, cached_time = _watchlist_cache[cache_key]
            if (now - cached_time).total_seconds() < _cache_timeout:
                logger.info(f"📋 Serving cached watchlist for {symbol}")
                return cached_data
        
        logger.info(f"🎯 Generating watchlist for {symbol}...")
        
        # Import here to avoid circular dependency
        from backend.main import trading_system
        
        # Use the same market data service as the main trading loop
        if not trading_system:
            raise HTTPException(status_code=503, detail="Trading system not initialized")
        
        # Check if market_data is available (system might be in minimal mode)
        if not hasattr(trading_system, 'market_data') or trading_system.market_data is None:
            raise HTTPException(status_code=503, detail="Market data not available - system running in dashboard-only mode. Please check Upstox connection.")
        
        # Get current market state (same as main trading loop)
        market_state = await trading_system.market_data.get_current_state()
        
        if not market_state or symbol not in market_state:
            raise HTTPException(status_code=404, detail=f"Market data not available for {symbol}")
        
        # 4. Strategy engine disabled - using SAC Meta-Controller only
        # model_manager = ModelManager()
        # strategy_engine = StrategyEngine(model_manager)
        
        # Generate signals from all strategies (using same data structure as main loop)
        # logger.info(f"🔄 Running {len(strategy_engine.strategies)} strategies...")
        # all_signals = await strategy_engine.generate_signals(market_state)
        all_signals = []  # No signals from old strategy engine
        
        # Filter signals for requested symbol
        symbol_signals = [s for s in all_signals if s.symbol == symbol]
        
        logger.info(f"✓ Generated {len(symbol_signals)} signals for {symbol}")
        
        # Extract market context from market_state
        symbol_data = market_state[symbol]
        spot_price = symbol_data.get('spot_price', 0)
        option_chain = symbol_data.get('option_chain', {})
        pcr = option_chain.get('pcr', 1.0) if option_chain else 1.0
        
        # Get VIX from market overview
        vix = 15.0
        try:
            market_overview = get_live_market_data()
            if 'volatility' in market_overview:
                vix = market_overview['volatility'].get('india_vix', 15.0)
        except Exception as e:
            logger.warning(f"Could not fetch VIX: {e}")
        
        # Get OI data from option chain
        calls_data = option_chain.get('calls', {}) if option_chain else {}
        puts_data = option_chain.get('puts', {}) if option_chain else {}
        
        # Calculate OI totals and changes
        total_call_oi = option_chain.get('total_call_oi', 0) if option_chain else 0
        total_put_oi = option_chain.get('total_put_oi', 0) if option_chain else 0
        total_call_oi_change = sum(strike.get('oi_change', 0) for strike in calls_data.values())
        total_put_oi_change = sum(strike.get('oi_change', 0) for strike in puts_data.values())
        
        # Helper function to calculate strike recommendations
        def get_strike_recommendations(spot, option_type, distance_pct=2.0):
            """Get 3 strike recommendations based on spot price"""
            if option_type == "CE":
                # For Calls: ATM, OTM1 (+1%), OTM2 (+2%)
                atm = round(spot / 50) * 50  # Round to nearest 50
                strikes = [atm, atm + spot * 0.01, atm + spot * 0.02]
            else:  # PE
                # For Puts: ATM, OTM1 (-1%), OTM2 (-2%)
                atm = round(spot / 50) * 50
                strikes = [atm, atm - spot * 0.01, atm - spot * 0.02]
            return [round(s / 50) * 50 for s in strikes]  # Round all to nearest 50
        
        def get_atm_strike(spot):
            """Get ATM strike for straddle selling"""
            return round(spot / 50) * 50
        
        # Analyze institutional activity based on OI changes and PCR
        institutional_activity = ""
        trading_suggestion = ""
        detailed_reasoning = ""
        recommended_strikes = []
        
        # OI Change Analysis
        if total_call_oi_change > 0 and total_put_oi_change > 0:
            if total_call_oi_change > total_put_oi_change * 1.5:
                institutional_activity = "📈 Heavy Call writing - Institutions expect resistance/sideways"
                if pcr > 1.0:
                    trading_suggestion = "💡 Sell OTM Calls (resistance likely) or Buy Puts if breakdown"
                    detailed_reasoning = "✓ Call OI building (resistance), ✓ PCR > 1.0 (Put buyers active), → Consider Puts on weakness"
                    recommended_strikes = get_strike_recommendations(spot_price, "PE")
                else:
                    trading_suggestion = "⚠️ Mixed signals - Wait for clarity before entry"
                    detailed_reasoning = "✗ Call OI building (bearish signal) BUT ✗ PCR < 1.0 (Call buyers active) → Conflicting OI vs PCR signals. WAIT for alignment."
                    recommended_strikes = []
            elif total_put_oi_change > total_call_oi_change * 1.5:
                institutional_activity = "📉 Heavy Put writing - Institutions expect support/upside"
                if pcr < 1.0:
                    trading_suggestion = "💡 Buy Calls on dips (support likely) or Sell OTM Puts"
                    detailed_reasoning = "✓ Put OI building (support), ✓ PCR < 1.0 (Call buyers active), ✓ Low VIX → Buy Calls" if vix < 12 else "✓ Put OI building (support), ✓ PCR < 1.0 (Call buyers active) → Buy Calls"
                    recommended_strikes = get_strike_recommendations(spot_price, "CE")
                else:
                    trading_suggestion = "⚠️ Mixed signals - Wait for clarity before entry"
                    detailed_reasoning = "✗ Put OI building (bullish signal) BUT ✗ PCR > 1.0 (Put buyers active) → Conflicting OI vs PCR signals. WAIT for alignment."
                    recommended_strikes = []
            else:
                institutional_activity = "⚖️ Balanced OI buildup - Institutions hedging, expect consolidation"
                atm_strike = get_atm_strike(spot_price)
                trading_suggestion = f"💡 Range-bound strategies (Sell {atm_strike} Straddle/Iron Condor)"
                detailed_reasoning = "Call OI ≈ Put OI (balanced hedging) → Sideways movement expected"
                recommended_strikes = [atm_strike]  # ATM strike for straddle
        elif total_call_oi_change > 0:
            institutional_activity = "🔴 Call OI building without Put OI - Bearish setup (Call writing)"
            trading_suggestion = "💡 Buy Puts or exit Long Call positions"
            detailed_reasoning = "✓ Call OI building alone (strong bearish), ✓ No Put hedge → Downside expected"
            recommended_strikes = get_strike_recommendations(spot_price, "PE")
        elif total_put_oi_change > 0:
            institutional_activity = "🟢 Put OI building without Call OI - Bullish setup (Put writing)"
            trading_suggestion = "💡 Buy Calls or exit Long Put positions"
            detailed_reasoning = "✓ Put OI building alone (strong bullish), ✓ No Call hedge → Upside expected"
            recommended_strikes = get_strike_recommendations(spot_price, "CE")
        elif total_call_oi_change < 0 and total_put_oi_change < 0:
            if abs(total_call_oi_change) > abs(total_put_oi_change) * 1.5:
                institutional_activity = "🚀 Call unwinding (covering shorts) - Bullish momentum expected"
                trading_suggestion = "💡 Strong Buy Calls - Ride the momentum"
                detailed_reasoning = f"✓ Call unwinding ({abs(total_call_oi_change)/100000:.1f}L), ✓ PCR {pcr:.2f}, ✓ Shorts covering → Strong upside"
                recommended_strikes = get_strike_recommendations(spot_price, "CE")
            elif abs(total_put_oi_change) > abs(total_call_oi_change) * 1.5:
                institutional_activity = "🔻 Put unwinding (covering protection) - Bearish momentum expected"
                trading_suggestion = "💡 Strong Buy Puts - Expect downside"
                detailed_reasoning = f"✓ Put unwinding ({abs(total_put_oi_change)/100000:.1f}L), ✓ PCR {pcr:.2f}, ✓ Protection removed → Strong downside"
                recommended_strikes = get_strike_recommendations(spot_price, "PE")
            else:
                institutional_activity = "📊 Both sides unwinding - Low conviction, expect volatility"
                trading_suggestion = "⚠️ Caution: Stay light or hedge existing positions"
                detailed_reasoning = "Both Call & Put OI unwinding → Low market conviction, high volatility risk"
                recommended_strikes = []
        elif total_call_oi_change < 0:
            institutional_activity = "🟢 Call OI unwinding alone - Covering shorts, bullish signal"
            trading_suggestion = "💡 Strong Buy Calls - Aggressive entry"
            detailed_reasoning = f"✓ Call unwinding alone ({abs(total_call_oi_change)/100000:.1f}L), ✓ Shorts covering, ✓ Low VIX → Best CE entry" if vix < 12 else f"✓ Call unwinding alone ({abs(total_call_oi_change)/100000:.1f}L), ✓ Shorts covering → Strong CE signal"
            recommended_strikes = get_strike_recommendations(spot_price, "CE")
        elif total_put_oi_change < 0:
            institutional_activity = "🔴 Put OI unwinding alone - Removing protection, bearish signal"
            trading_suggestion = "💡 Strong Buy Puts - Aggressive entry"
            detailed_reasoning = f"✓ Put unwinding alone ({abs(total_put_oi_change)/100000:.1f}L), ✓ Protection removed, ✓ Low VIX → Best PE entry" if vix < 12 else f"✓ Put unwinding alone ({abs(total_put_oi_change)/100000:.1f}L), ✓ Protection removed → Strong PE signal"
            recommended_strikes = get_strike_recommendations(spot_price, "PE")
        else:
            institutional_activity = "😴 No significant OI changes - Wait for market direction"
            trading_suggestion = "⏸️ Hold: Wait for clear signals before entering new positions"
            detailed_reasoning = "No major OI activity → Lack of institutional conviction, wait for setup"
            recommended_strikes = []
        
        # PCR-based sentiment refinement
        if pcr > 1.2:
            sentiment = "Bullish"
            sentiment_reason = f"PCR {pcr:.2f} - Put buyers outnumber Call buyers (expecting upside)"
        elif pcr < 0.8:
            sentiment = "Bearish"
            sentiment_reason = f"PCR {pcr:.2f} - Call buyers outnumber Put buyers (expecting downside)"
        else:
            sentiment = "Neutral"
            sentiment_reason = f"PCR {pcr:.2f} - Balanced demand, range-bound likely"
        
        # VIX interpretation with actionable advice (CE/PE specific based on sentiment)
        if vix > 20:
            vix_status = "High volatility - SELL premium (Straddles/Strangles), avoid buying options"
        elif vix < 12:
            # Low VIX - suggest buying based on market sentiment
            if sentiment == "Bullish":
                vix_status = "Low volatility - BUY CE (Call options cheap), expect volatility spike & upside"
            elif sentiment == "Bearish":
                vix_status = "Low volatility - BUY PE (Put options cheap), expect volatility spike & downside"
            else:
                vix_status = "Low volatility - BUY Straddle/Strangle (both CE+PE cheap), expect big move"
        else:
            # Normal VIX - directional based on sentiment
            if sentiment == "Bullish":
                vix_status = "Normal volatility - Directional BUY CE preferred (calls have edge)"
            elif sentiment == "Bearish":
                vix_status = "Normal volatility - Directional BUY PE preferred (puts have edge)"
            else:
                vix_status = "Normal volatility - Range-bound strategies or wait for direction"
        
        if not symbol_signals:
            logger.warning(f"No signals generated for {symbol}")
            return {
                "status": "success",
                "symbol": symbol,
                "timestamp": now_ist().isoformat(),
                "market_context": {
                    "spot_price": spot_price,
                    "pcr": pcr,
                    "sentiment": sentiment,
                    "sentiment_reason": sentiment_reason,
                    "vix": vix,
                    "vix_status": vix_status,
                    "expiry": option_chain.get('expiry'),
                    "total_call_oi": total_call_oi,
                    "total_put_oi": total_put_oi,
                    "total_call_oi_change": total_call_oi_change,
                    "total_put_oi_change": total_put_oi_change,
                    "institutional_activity": institutional_activity,
                    "trading_suggestion": trading_suggestion,
                    "detailed_reasoning": detailed_reasoning,
                    "recommended_strikes": recommended_strikes,
                },
                "analysis_summary": {
                    "total_signals_generated": 0,
                    "unique_strikes_analyzed": 0,
                    "strikes_passed_filters": 0,
                    "strategies_active": 0  # Old strategy engine disabled
                },
                "recommended_strikes": [],
                "message": f"No trading signals generated for {symbol}. Market conditions may not favor any strategies currently."
            }
        
        # 5. Analyze strikes (group by strike price)
        strike_analysis = {}
        
        for signal in symbol_signals:
            strike = str(signal.strike)
            
            if strike not in strike_analysis:
                strike_analysis[strike] = {
                    'strike': strike,
                    'direction': signal.direction,
                    'supporting_strategies': [],
                    'total_strength': 0,
                    'avg_strength': 0,
                    'entry_price': signal.entry_price,
                    'target_price': getattr(signal, 'target_price', None),
                    'stop_loss': getattr(signal, 'stop_loss', None),
                    'reasons': [],
                    'signals': []
                }
            
            # Aggregate signal data
            strike_analysis[strike]['supporting_strategies'].append(signal.strategy_name)
            strike_analysis[strike]['total_strength'] += signal.strength
            strike_analysis[strike]['reasons'].append(signal.reason)
            strike_analysis[strike]['signals'].append({
                'strategy': signal.strategy_name,
                'strength': signal.strength,
                'reason': signal.reason
            })
        
        # Calculate averages
        for strike, data in strike_analysis.items():
            num_strategies = len(data['supporting_strategies'])
            data['avg_strength'] = data['total_strength'] / num_strategies if num_strategies > 0 else 0
            data['num_strategies'] = num_strategies
        
        # 6. Apply filters
        filtered_strikes = []
        
        for strike, data in strike_analysis.items():
            # Check if minimum strategies agree
            if data['num_strategies'] >= min_strategies_agree:
                # Check strategy strength
                if data['avg_strength'] >= min_strategy_strength:
                    # Check option type filter
                    if option_type is None or data['direction'] == option_type:
                        filtered_strikes.append(data)
        
        logger.info(f"✓ {len(filtered_strikes)} strikes passed strategy filters")
        
        # 7. Score with ML model (using already initialized model_manager)
        for strike_data in filtered_strikes:
            # Get first signal for ML scoring
            if strike_data['signals']:
                # Create signal object for ML
                from backend.strategies.strategy_base import Signal
                ml_signal = Signal(
                    strategy_name="Watchlist",
                    symbol=symbol,
                    direction=strike_data['direction'],
                    action="BUY",
                    strike=strike_data['strike'],
                    expiry=option_chain.get('expiry'),
                    entry_price=strike_data['entry_price'],
                    strength=strike_data['avg_strength'],
                    reason="; ".join(strike_data['reasons'][:3])
                )
                
                # Score with ML (if model available)
                try:
                    scored = await model_manager.score_signals([ml_signal], market_state)
                    
                    if scored:
                        strike_data['ml_score'] = getattr(scored[0], 'ml_probability', strike_data['avg_strength'] / 100)
                        strike_data['ml_confidence'] = getattr(scored[0], 'ml_confidence', 0.5)
                    else:
                        # No ML score - use strategy strength as proxy
                        strike_data['ml_score'] = strike_data['avg_strength'] / 100
                        strike_data['ml_confidence'] = 0.5
                except Exception as ml_error:
                    logger.warning(f"ML scoring failed: {ml_error}")
                    strike_data['ml_score'] = strike_data['avg_strength'] / 100
                    strike_data['ml_confidence'] = 0.5
            else:
                strike_data['ml_score'] = 0
                strike_data['ml_confidence'] = 0
        
        # Filter by ML score
        filtered_strikes = [s for s in filtered_strikes if s.get('ml_score', 0) >= min_ml_score]
        
        logger.info(f"✓ {len(filtered_strikes)} strikes passed ML filter (score >= {min_ml_score})")
        
        # 8. Enrich with option chain data
        option_data_dict = option_chain.get('data', {})
        
        for strike_data in filtered_strikes:
            strike = strike_data['strike']
            direction = strike_data['direction']
            
            # Get option chain data for this strike
            if direction == "CALL":
                option_data = option_data_dict.get('calls', {}).get(strike, {})
            else:
                option_data = option_data_dict.get('puts', {}).get(strike, {})
            
            # Add option metrics
            strike_data['current_ltp'] = option_data.get('ltp', 0)
            strike_data['iv'] = option_data.get('iv', 0)
            strike_data['oi'] = option_data.get('oi', 0)
            strike_data['volume'] = option_data.get('volume', 0)
            strike_data['oi_change'] = option_data.get('oi_change_percentage', 0)
            
            # Calculate risk-reward
            if strike_data['target_price'] and strike_data['stop_loss'] and strike_data['entry_price']:
                potential_profit = strike_data['target_price'] - strike_data['entry_price']
                potential_loss = strike_data['entry_price'] - strike_data['stop_loss']
                
                if potential_loss > 0:
                    strike_data['risk_reward_ratio'] = round(potential_profit / potential_loss, 2)
                else:
                    strike_data['risk_reward_ratio'] = 0
            else:
                strike_data['risk_reward_ratio'] = 0
        
        # 9. Rank by composite score
        for strike_data in filtered_strikes:
            # Composite score = ML * 0.4 + Strategy Strength * 0.3 + Num Strategies * 0.2 + RR * 0.1
            composite = (
                strike_data.get('ml_score', 0) * 0.4 +
                (strike_data['avg_strength'] / 100) * 0.3 +
                (min(strike_data['num_strategies'] / 10, 1.0)) * 0.2 +
                (min(strike_data.get('risk_reward_ratio', 0) / 3, 1.0)) * 0.1
            )
            strike_data['composite_score'] = round(composite * 100, 2)
        
        # Sort by composite score descending
        filtered_strikes.sort(key=lambda x: x['composite_score'], reverse=True)
        
        # 10. Build response (market context already calculated above)
        response = {
            "status": "success",
            "timestamp": now_ist().isoformat(),
            "symbol": symbol,
            "filters_applied": {
                "min_ml_score": min_ml_score,
                "min_strategy_strength": min_strategy_strength,
                "min_strategies_agree": min_strategies_agree,
                "option_type": option_type or "BOTH"
            },
            "market_context": {
                "spot_price": spot_price,
                "pcr": pcr,
                "sentiment": sentiment,
                "sentiment_reason": sentiment_reason,
                "vix": vix,
                "vix_status": vix_status,
                "expiry": option_chain.get('expiry'),
                "total_call_oi": total_call_oi,
                "total_put_oi": total_put_oi,
                "total_call_oi_change": total_call_oi_change,
                "total_put_oi_change": total_put_oi_change,
                "institutional_activity": institutional_activity,
                "trading_suggestion": trading_suggestion,
                "detailed_reasoning": detailed_reasoning,
                "recommended_strikes": recommended_strikes,
            },
            "analysis_summary": {
                "total_signals_generated": len(symbol_signals),
                "unique_strikes_analyzed": len(strike_analysis),
                "strikes_passed_filters": len(filtered_strikes),
                "strategies_active": 0  # Old strategy engine disabled
            },
            "recommended_strikes": filtered_strikes[:20]  # Top 20
        }
        
        # Store in cache
        _watchlist_cache[cache_key] = (response, datetime.now())
        
        logger.info(f"✅ Watchlist generated: {len(filtered_strikes)} recommended strikes")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating watchlist: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/top-picks")
async def get_top_picks(
    symbols: str = Query("NIFTY,SENSEX", description="Comma-separated symbols"),
    limit: int = Query(5, description="Top N picks per symbol"),
):
    """
    Get top picks across multiple symbols
    
    Returns best 5 strikes per symbol based on highest composite scores
    """
    
    try:
        symbol_list = [s.strip().upper() for s in symbols.split(',')]
        all_picks = {}
        
        for symbol in symbol_list:
            # Get recommended strikes with default filters
            result = await get_recommended_strikes(
                symbol=symbol,
                min_ml_score=0.7,
                min_strategy_strength=75.0,
                min_strategies_agree=3
            )
            
            # Get top N
            top_strikes = result['recommended_strikes'][:limit]
            
            all_picks[symbol] = {
                'spot_price': result['market_context']['spot_price'],
                'sentiment': result['market_context']['sentiment'],
                'pcr': result['market_context']['pcr'],
                'top_picks': top_strikes
            }
        
        return {
            "status": "success",
            "timestamp": now_ist().isoformat(),
            "picks": all_picks
        }
        
    except Exception as e:
        logger.error(f"Error generating top picks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/strategy-consensus/{symbol}/{strike}")
async def get_strategy_consensus(
    symbol: str,
    strike: str,
    direction: str = Query("CALL", description="CALL or PUT")
):
    """
    Get detailed consensus for a specific strike
    
    Shows which strategies agree/disagree and why
    """
    
    try:
        # Get market data
        market_data = await get_live_market_data()
        
        # Get option chain
        option_chain_response = await get_option_chain_data(symbol)
        option_chain = option_chain_response['data']
        market_data[symbol]['option_chain'] = option_chain
        
        # Run strategies (disabled - old strategy engine removed)
        # strategy_engine = StrategyEngine(model_manager=None)
        # all_signals = await strategy_engine.generate_signals(market_data)
        all_signals = []  # No signals from old strategy engine
        
        # Filter for this strike and direction
        matching_signals = [
            s for s in all_signals 
            if s.symbol == symbol and str(s.strike) == strike and s.direction == direction
        ]
        
        # Build consensus
        consensus = {
            "strike": strike,
            "direction": direction,
            "supporting_strategies": len(matching_signals),
            "total_strategies": 0,  # Old strategy engine disabled
            "consensus_percentage": 0,  # No consensus from old strategy engine
            "signals": [
                {
                    "strategy": s.strategy_name,
                    "strength": s.strength,
                    "reason": s.reason,
                    "entry_price": s.entry_price,
                    "target": getattr(s, 'target_price', None),
                    "stop_loss": getattr(s, 'stop_loss', None)
                }
                for s in matching_signals
            ]
        }
        
        return {
            "status": "success",
            "consensus": consensus
        }
        
    except Exception as e:
        logger.error(f"Error getting consensus: {e}")
        raise HTTPException(status_code=500, detail=str(e))
