"""
Market Data API - Live market indices, breadth, and sentiment
"""
from fastapi import APIRouter, HTTPException, Depends
from backend.core.timezone_utils import now_ist
from datetime import datetime, time
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from backend.core.upstox_client import UpstoxClient
from backend.core.config import config
from backend.core.logger import logger

# IST timezone for market hours
IST = ZoneInfo("Asia/Kolkata")

router = APIRouter(prefix="/api/market", tags=["market"])

# Cache for market data to reduce API calls
_market_cache = {}
_market_cache_timeout = 30  # 30 seconds cache (increased from 15)

# Cache for Upstox client to prevent multiple initializations
_upstox_client_cache = None
_upstox_client_token = None

# Upstox instrument keys for indices
INSTRUMENT_KEYS = {
    "NIFTY": "NSE_INDEX|Nifty 50",
    "SENSEX": "BSE_INDEX|SENSEX",
    "INDIA_VIX": "NSE_INDEX|India VIX",
    "NIFTY_IT": "NSE_INDEX|Nifty IT",
    "NIFTY_BANK": "NSE_INDEX|Nifty Bank",
    "NIFTY_AUTO": "NSE_INDEX|Nifty Auto",
    "NIFTY_PHARMA": "NSE_INDEX|Nifty Pharma",
    "NIFTY_FMCG": "NSE_INDEX|Nifty FMCG",
    "NIFTY_METAL": "NSE_INDEX|Nifty Metal"
}

def get_upstox_client() -> Optional[UpstoxClient]:
    """Get Upstox client with valid token (cached to prevent multiple initializations)"""
    global _upstox_client_cache, _upstox_client_token
    
    try:
        # Load token from config file
        from pathlib import Path
        import json
        
        # Load from config file (mounted in Docker)
        config_token_path = Path(config.settings.upstox_token_file)
        if config_token_path.exists():
            with open(config_token_path, 'r') as f:
                token_data = json.load(f)
                access_token = token_data.get('access_token')
                
                if access_token:
                    # Return cached client if token hasn't changed
                    if _upstox_client_cache and _upstox_client_token == access_token:
                        return _upstox_client_cache
                    
                    # Create new client and cache it
                    _upstox_client_cache = UpstoxClient(access_token)
                    _upstox_client_token = access_token
                    return _upstox_client_cache
                    
    except Exception as e:
        print(f"Error loading Upstox client: {e}")
    
    return None

def is_market_open() -> bool:
    """Check if Indian market is open (9:15 AM to 3:25 PM IST, Mon-Fri)"""
    # Get current time in IST
    now = datetime.now(IST)
    
    # Weekend check
    if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
        return False
    
    market_open = time(9, 15)
    market_close = time(15, 25)  # 3:25 PM IST
    current_time = now.time()
    
    return market_open <= current_time <= market_close

def get_live_market_data():
    """
    Fetch REAL live market data from Upstox API
    """
    upstox = get_upstox_client()
    is_open = is_market_open()
    
    if not upstox:
        raise HTTPException(status_code=503, detail="Upstox client not available. Please refresh authentication token.")
    
    try:
        # Import market data module to get max pain data
        from backend.main import app
        market_data_service = getattr(app.state, 'market_data', None)
        
        # Fetch quotes for all indices
        all_instruments = list(INSTRUMENT_KEYS.values())
        quotes_response = upstox.get_full_market_quote(all_instruments)
        
        if not quotes_response or quotes_response.get('status') != 'success':
            raise HTTPException(status_code=503, detail="Failed to fetch market quotes from Upstox")
        
        quotes_data = quotes_response.get('data', {})
        
        # Extract data for each index
        def extract_index_data(key: str, display_name: str, is_index: bool = True):
            instrument_key = INSTRUMENT_KEYS[key]
            # Upstox returns keys with colon instead of pipe
            instrument_key_colon = instrument_key.replace('|', ':')
            quote = quotes_data.get(instrument_key_colon, quotes_data.get(instrument_key, {}))
            
            if not quote:
                return None
            
            ohlc = quote.get('ohlc', {})
            
            # For indices, Upstox returns current price in ohlc.close
            # For stocks, it's in last_price
            if is_index:
                ltp = ohlc.get('close', quote.get('last_price', 0))
                # For indices, prev_close is yesterday's close, use open as baseline
                prev_close = ohlc.get('open', ltp)
            else:
                ltp = quote.get('last_price', 0)
                prev_close = ohlc.get('close', ltp)
            
            change = ltp - prev_close
            change_percent = (change / prev_close * 100) if prev_close else 0
            
            return {
                "symbol": display_name,
                "price": round(ltp, 2),
                "change": round(change, 2),
                "change_percent": round(change_percent, 2),
                "open": round(ohlc.get('open', ltp), 2),
                "high": round(ohlc.get('high', ltp), 2),
                "low": round(ohlc.get('low', ltp), 2),
                "prev_close": round(prev_close, 2),
                "volume": quote.get('volume', 0),
                "last_updated": now_ist().isoformat()
            }
        
        nifty_data = extract_index_data("NIFTY", "NIFTY 50", True)
        sensex_data = extract_index_data("SENSEX", "SENSEX", True)
        vix_data = extract_index_data("INDIA_VIX", "INDIA VIX", True)

        # Sector indices
        sector_map = {
            "IT": ("NIFTY_IT", "NIFTY IT"),
            "BANK": ("NIFTY_BANK", "NIFTY BANK"),
            "AUTO": ("NIFTY_AUTO", "NIFTY AUTO"),
            "PHARMA": ("NIFTY_PHARMA", "NIFTY PHARMA"),
            "FMCG": ("NIFTY_FMCG", "NIFTY FMCG"),
            "METAL": ("NIFTY_METAL", "NIFTY METAL")
        }

        sector_performance = {}
        for label, (sector_key, display_name) in sector_map.items():
            sector_data = extract_index_data(sector_key, display_name, True)
            if sector_data:
                sector_performance[label] = {
                    "change_percent": sector_data.get("change_percent", 0.0),
                    "symbol": display_name
                }
            else:
                sector_performance[label] = {
                    "change_percent": 0.0,
                    "symbol": display_name
                }

        # Calculate VIX interpretation based on live change
        vix_value = vix_data['price'] if vix_data else 0.0
        vix_change = vix_data['change'] if vix_data else 0.0
        vix_change_percent = vix_data['change_percent'] if vix_data else 0.0

        if vix_value <= 0:
            vix_interpretation = "Unavailable"
        elif vix_value < 12:
            vix_interpretation = "Low"
        elif vix_value < 16:
            vix_interpretation = "Moderate"
        elif vix_value < 22:
            vix_interpretation = "Elevated"
        else:
            vix_interpretation = "High"

        indices_payload = {
            "NIFTY": nifty_data,
            "SENSEX": sensex_data
        }
        
        # Try to get max pain data from market data service if available
        if market_data_service:
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                market_state = loop.run_until_complete(market_data_service.get_current_state()) if hasattr(market_data_service, 'get_current_state') else {}
                
                # Add max pain to each index if available
                for symbol in ['NIFTY', 'SENSEX']:
                    if symbol in market_state and indices_payload.get(symbol):
                        option_chain = market_state[symbol].get('option_chain', {})
                        max_pain = option_chain.get('max_pain', 0)
                        if max_pain > 0:
                            indices_payload[symbol]['max_pain'] = round(max_pain, 2)
            except Exception:
                # Silently fail - max pain is optional
                pass

        return {
            "is_market_open": is_open,
            "timestamp": now_ist().isoformat(),
            "indices": indices_payload,
            "market_breadth": derive_market_breadth(indices_payload, sector_performance),
            "volatility": {
                "india_vix": round(vix_value, 2) if vix_value else None,
                "vix_change": round(vix_change, 2) if vix_data else None,
                "vix_change_percent": round(vix_change_percent, 2) if vix_data else None,
                "interpretation": vix_interpretation
            },
            "sector_performance": sector_performance,
            "top_movers": build_top_movers()
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching live market data: {e}")

def derive_market_breadth(indices: Dict[str, Optional[Dict]], sectors: Dict[str, Dict]) -> Dict[str, Optional[float]]:
    """Derive market breadth using live index and sector data."""
    changes: List[float] = []

    for data in indices.values():
        if data and data.get("change_percent") is not None:
            changes.append(data["change_percent"])

    for sector in sectors.values():
        change_percent = sector.get("change_percent")
        if change_percent is not None:
            changes.append(change_percent)

    advances = sum(1 for change in changes if change > 0)
    declines = sum(1 for change in changes if change < 0)
    unchanged = len(changes) - advances - declines

    if declines > 0:
        advance_decline_ratio = round(advances / declines, 2)
    elif advances > 0:
        advance_decline_ratio = float(advances)
    else:
        advance_decline_ratio = None

    return {
        "advances": advances,
        "declines": declines,
        "unchanged": unchanged,
        "advance_decline_ratio": advance_decline_ratio,
        "new_highs": None,
        "new_lows": None
    }


def build_top_movers() -> Dict[str, List[Dict]]:
    """Top movers placeholder until broker feed for constituents is available."""
    return {
        "gainers": [],
        "losers": []
    }

@router.get("/overview")
async def get_market_overview():
    """
    Get comprehensive market overview with indices, breadth, and sentiment
    
    **Returns:**
    - Market status (open/closed)
    - NIFTY, SENSEX, BANK NIFTY data (LIVE from Upstox)
    - Market breadth (advances/declines)
    - India VIX volatility
    - Sector performance
    - Top gainers/losers
    """
    try:
        # Check cache first
        cache_key = "market_overview"
        now = datetime.now()
        
        if cache_key in _market_cache:
            cached_data, cached_time = _market_cache[cache_key]
            if (now - cached_time).total_seconds() < _market_cache_timeout:
                return cached_data
        
        data = get_live_market_data()
        response = {
            "status": "success",
            "data": data
        }
        
        # Store in cache
        _market_cache[cache_key] = (response, now)
        
        return response
    except HTTPException as exc:
        raise exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch market data: {str(e)}")

@router.get("/indices")
async def get_indices():
    """
    Get real-time index prices (NIFTY, SENSEX, BANK NIFTY) - LIVE from Upstox
    """
    try:
        data = get_live_market_data()
        return {
            "status": "success",
            "data": {
                "is_market_open": data["is_market_open"],
                "timestamp": data["timestamp"],
                "indices": data["indices"]
            }
        }
    except HTTPException as exc:
        raise exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch indices: {str(e)}")

@router.get("/breadth")
async def get_market_breadth():
    """
    Get market breadth indicators for intraday trading
    """
    try:
        data = get_live_market_data()
        return {
            "status": "success",
            "data": {
                "timestamp": data["timestamp"],
                "breadth": data["market_breadth"],
                "volatility": data["volatility"]
            }
        }
    except HTTPException as exc:
        raise exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch market breadth: {str(e)}")

@router.get("/sectors")
async def get_sector_performance():
    """
    Get sectoral indices performance - LIVE from Upstox
    """
    try:
        data = get_live_market_data()
        return {
            "status": "success",
            "data": {
                "timestamp": data["timestamp"],
                "sectors": data["sector_performance"]
            }
        }
    except HTTPException as exc:
        raise exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch sector performance: {str(e)}")

@router.get("/movers")
async def get_top_movers():
    """
    Get top gaining and losing stocks
    """
    try:
        data = get_live_market_data()
        return {
            "status": "success",
            "data": {
                "timestamp": data["timestamp"],
                "movers": data["top_movers"]
            }
        }
    except HTTPException as exc:
        raise exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch top movers: {str(e)}")

@router.get("/option-chain/{symbol}")
async def get_option_chain_data(symbol: str, expiry: Optional[str] = None):
    """
    Get option chain data for analysis - from cached market data
    
    **Parameters:**
    - symbol: NIFTY, BANKNIFTY, SENSEX
    - expiry: Optional (not used, returns current cached data)
    
    **Returns:**
    - Complete option chain with calls and puts
    - PCR (Put-Call Ratio)
    - Max Pain analysis
    - OI distribution
    """
    try:
        # Get trading system instance to access market data
        from backend.main import app
        trading_system = getattr(app.state, 'trading_system', None)
        
        if not trading_system or not hasattr(trading_system, 'market_data') or trading_system.market_data is None:
            raise HTTPException(status_code=503, detail="Market data service not available - system running in dashboard-only mode")
        
        market_data_service = trading_system.market_data
        market_state = await market_data_service.get_current_state()
        
        # Get data for requested symbol
        symbol_upper = symbol.upper()
        if symbol_upper not in market_state:
            raise HTTPException(status_code=404, detail=f"No data available for {symbol}")
        
        symbol_data = market_state[symbol_upper]
        option_chain = symbol_data.get('option_chain', {})
        
        if not option_chain or not option_chain.get('calls') or not option_chain.get('puts'):
            return {
                "status": "success",
                "message": "Option chain data not yet loaded (loading in background)",
                "data": {
                    "symbol": symbol_upper,
                    "spot_price": symbol_data.get('spot_price'),
                    "expiry": symbol_data.get('expiry'),
                    "pcr": None,
                    "total_call_oi": None,
                    "total_put_oi": None,
                    "calls": {},
                    "puts": {}
                }
            }
        
        return {
            "status": "success",
            "data": {
                "symbol": symbol_upper,
                "spot_price": symbol_data.get('spot_price'),
                "expiry": symbol_data.get('expiry'),
                "pcr": option_chain.get('pcr'),
                "total_call_oi": option_chain.get('total_call_oi'),
                "total_put_oi": option_chain.get('total_put_oi'),
                "max_pain": option_chain.get('max_pain'),
                "calls": option_chain.get('calls', {}),
                "puts": option_chain.get('puts', {}),
                "technical_indicators": symbol_data.get('technical_indicators', {}),
                "iv_rank": symbol_data.get('iv_rank', 50),
                "multi_timeframe": symbol_data.get('multi_timeframe', {}),
                "historical_data": symbol_data.get('historical_data', [])  # Add historical data for ML Strategy
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching option chain for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching option chain: {str(e)}")


