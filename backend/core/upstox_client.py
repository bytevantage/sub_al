"""
Upstox API Client
Wrapper for Upstox v2 API with rate limiting and error handling
"""

import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import json
from pathlib import Path

from backend.core.logger import logger


class UpstoxClient:
    """Upstox API Client with rate limiting"""
    
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.base_url = "https://api.upstox.com"
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json"
        }
        self.rate_limiter = RateLimiter(max_calls=10, time_window=1)
        
        # Create session with connection pooling and DNS caching
        self.session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        
        # Configure HTTP adapter with connection pooling
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,  # Number of connection pools
            pool_maxsize=20,      # Maximum number of connections in each pool
            pool_block=False
        )
        
        # Mount adapters for both HTTP and HTTPS
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Set default headers
        self.session.headers.update(self.headers)
        
        logger.info("Upstox client initialized with connection pooling and DNS caching")
        
    def _make_request(self, method: str, endpoint: str, params: dict = None, data: dict = None, retry_count: int = 0, max_retries: int = 3):
        """Make HTTP request to Upstox API with rate limiting"""
        url = f"{self.base_url}{endpoint}"
        
        try:
            if method.upper() == "GET":
                response = self.session.get(url, params=params, timeout=10)
            elif method.upper() == "POST":
                response = self.session.post(url, json=data, timeout=10)
            elif method.upper() == "PUT":
                response = self.session.put(url, json=data, timeout=10)
            elif method.upper() == "DELETE":
                response = self.session.delete(url, timeout=10)
            else:
                logger.error(f"Unsupported HTTP method: {method}")
                return None
                
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                if retry_count >= max_retries:
                    logger.error(f"Rate limit exceeded, max retries ({max_retries}) reached for {endpoint}")
                    return None
                    
                wait_time = min(5 * (2 ** retry_count), 30)  # Exponential backoff, max 30s
                logger.warning(f"Rate limit exceeded, waiting {wait_time}s (retry {retry_count + 1}/{max_retries})...")
                time.sleep(wait_time)
                return self._make_request(method, endpoint, params, data, retry_count + 1, max_retries)
            else:
                logger.error(f"API request failed: {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.Timeout:
            logger.error(f"Request timeout for {endpoint}")
            if retry_count < max_retries:
                wait_time = 2 ** retry_count  # Exponential backoff for timeouts
                logger.warning(f"Retrying after timeout in {wait_time}s (retry {retry_count + 1}/{max_retries})...")
                time.sleep(wait_time)
                return self._make_request(method, endpoint, params, data, retry_count + 1, max_retries)
            return None
        except requests.exceptions.ConnectionError as e:
            # Handle DNS resolution failures specifically
            if "NameResolutionError" in str(e) or "Temporary failure in name resolution" in str(e):
                if retry_count < max_retries:
                    wait_time = 3 + (2 ** retry_count)  # Longer backoff for DNS issues
                    logger.warning(f"DNS resolution failed for {endpoint}, retrying in {wait_time}s (retry {retry_count + 1}/{max_retries})...")
                    time.sleep(wait_time)
                    return self._make_request(method, endpoint, params, data, retry_count + 1, max_retries)
                logger.error(f"DNS resolution failed permanently for {endpoint}: {e}")
            else:
                logger.error(f"Connection error for {endpoint}: {e}")
            return None
        except Exception as e:
            logger.error(f"Request error for {endpoint}: {e}")
            return None
    
    # ========== Market Data APIs ==========
    
    def get_historical_candles(
        self,
        instrument_key: str,
        interval: str,
        from_date: str,
        to_date: str
    ) -> Optional[Dict]:
        """
        Get historical candle data
        interval: 1minute, 30minute, day, week, month
        """
        endpoint = f"/v2/historical-candle/{instrument_key}/{interval}/{to_date}/{from_date}"
        return self._make_request("GET", endpoint)
    
    def get_intraday_candles(
        self,
        instrument_key: str,
        interval: str
    ) -> Optional[Dict]:
        """
        Get intraday candle data (V3 API)
        interval: 1minute, 5minute, 15minute, 30minute, 1hour, 1day
        
        Maps to V3 API: /v3/historical-candle/intraday/{instrument_key}/{unit}/{interval}
        """
        # Map interval to unit and interval for V3 API
        interval_map = {
            '1minute': ('minutes', 1),
            '5minute': ('minutes', 5),
            '15minute': ('minutes', 15),
            '30minute': ('minutes', 30),
            '1hour': ('hours', 1),
            '1day': ('days', 1)
        }
        
        if interval not in interval_map:
            logger.error(f"Unsupported interval: {interval}")
            return None
        
        unit, interval_value = interval_map[interval]
        endpoint = f"/v3/historical-candle/intraday/{instrument_key}/{unit}/{interval_value}"
        return self._make_request("GET", endpoint)
    
    def get_historical_candle_data(
        self,
        instrument_key: str,
        timeframe: str,
        start_date: str = None,
        end_date: str = None
    ) -> Optional[Dict]:
        """
        Get historical candle data (V3 API)
        timeframe: 1minute, 5minute, 15minute, 30minute, 1hour, 1day
        start_date/end_date: Format YYYY-MM-DD (optional for intraday)
        
        Maps to V3 API: /v3/historical-candle/intraday/{instrument_key}/{unit}/{interval}
        or /v3/historical-candle/day/{instrument_key}/{interval} for daily data
        """
        # Map timeframe to unit and interval
        timeframe_map = {
            '1minute': ('intraday', 'minutes', 1),
            '5minute': ('intraday', 'minutes', 5),
            '15minute': ('intraday', 'minutes', 15),
            '30minute': ('intraday', 'minutes', 30),
            '1hour': ('intraday', 'hours', 1),
            '1day': ('day', 'days', 1)
        }
        
        if timeframe not in timeframe_map:
            logger.error(f"Unsupported timeframe: {timeframe}")
            return None
        
        api_type, unit, interval = timeframe_map[timeframe]
        
        if api_type == 'intraday':
            endpoint = f"/v3/historical-candle/intraday/{instrument_key}/{unit}/{interval}"
        else:  # daily
            endpoint = f"/v3/historical-candle/day/{instrument_key}/{interval}"
            if start_date and end_date:
                endpoint += f"?from={start_date}&to={end_date}"
        
        result = self._make_request("GET", endpoint)
        
        # Transform V3 response to match expected format
        if result and 'data' in result:
            return result
        
        return None
    
    def get_multi_day_historical_data(
        self,
        instrument_key: str,
        days: int = 30,
        timeframe: str = '1day'
    ) -> Optional[Dict]:
        """
        Get multiple days of historical data for ML training
        
        Args:
            instrument_key: The instrument key
            days: Number of days to fetch (max 365)
            timeframe: Data timeframe (1day recommended for multi-day)
        
        Returns:
            Historical candle data
        """
        from datetime import datetime, timedelta
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        return self.get_historical_candle_data(
            instrument_key,
            timeframe,
            start_date.strftime('%Y-%m-%d'),
            end_date.strftime('%Y-%m-%d')
        )
    
    def get_full_market_quote(self, instrument_keys: List[str]) -> Optional[Dict]:
        """Get full market quotes for instruments"""
        symbol_string = ",".join(instrument_keys)
        endpoint = "/v2/market-quote/quotes"
        params = {"symbol": symbol_string}
        return self._make_request("GET", endpoint, params=params)
    
    def get_ohlc(self, instrument_keys: List[str]) -> Optional[Dict]:
        """Get OHLC data for instruments"""
        symbol_string = ",".join(instrument_keys)
        endpoint = "/v2/market-quote/ohlc"
        params = {"symbol": symbol_string}
        return self._make_request("GET", endpoint, params=params)
    
    def get_ltp(self, instrument_keys: List[str]) -> Optional[Dict]:
        """Get Last Traded Price for instruments"""
        symbol_string = ",".join(instrument_keys)
        endpoint = "/v2/market-quote/ltp"
        params = {"symbol": symbol_string}
        return self._make_request("GET", endpoint, params=params)
    
    def get_option_chain(
        self,
        instrument_key: str,
        expiry_date: str
    ) -> Optional[Dict]:
        """
        Get option chain data
        instrument_key: e.g., NSE_INDEX|Nifty 50
        expiry_date: YYYY-MM-DD
        """
        endpoint = "/v2/option/chain"
        params = {
            "instrument_key": instrument_key,
            "expiry_date": expiry_date
        }
        return self._make_request("GET", endpoint, params=params)
    
    def get_option_contracts(
        self,
        symbol: str,
        instrument_key: str
    ) -> Optional[Dict]:
        """
        Get available option contracts for a symbol
        symbol: e.g., NIFTY, BANKNIFTY
        instrument_key: e.g., NSE_INDEX|Nifty 50
        Returns list of available option contracts with expiries
        """
        endpoint = "/v2/option/contract"
        params = {
            "symbol": symbol,
            "instrument_key": instrument_key
        }
        return self._make_request("GET", endpoint, params=params)
    
    # ========== Order Management APIs ==========
    
    def place_order(
        self,
        instrument_token: str,
        quantity: int,
        transaction_type: str,  # BUY or SELL
        order_type: str,  # MARKET or LIMIT
        price: float = 0,
        product: str = "I",  # I=Intraday, D=Delivery
        validity: str = "DAY",
        disclosed_quantity: int = 0,
        trigger_price: float = 0
    ) -> Optional[Dict]:
        """Place an order"""
        endpoint = "/v2/order/place"
        
        data = {
            "quantity": quantity,
            "product": product,
            "validity": validity,
            "price": price,
            "tag": "algo_trading",
            "instrument_token": instrument_token,
            "order_type": order_type,
            "transaction_type": transaction_type,
            "disclosed_quantity": disclosed_quantity,
            "trigger_price": trigger_price,
            "is_amo": False
        }
        
        return self._make_request("POST", endpoint, data=data)
    
    def modify_order(
        self,
        order_id: str,
        quantity: Optional[int] = None,
        price: Optional[float] = None,
        order_type: Optional[str] = None,
        validity: Optional[str] = None,
        trigger_price: Optional[float] = None
    ) -> Optional[Dict]:
        """Modify an existing order"""
        endpoint = f"/v2/order/modify"
        
        data = {"order_id": order_id}
        if quantity is not None:
            data["quantity"] = quantity
        if price is not None:
            data["price"] = price
        if order_type is not None:
            data["order_type"] = order_type
        if validity is not None:
            data["validity"] = validity
        if trigger_price is not None:
            data["trigger_price"] = trigger_price
            
        return self._make_request("PUT", endpoint, data=data)
    
    def cancel_order(self, order_id: str) -> Optional[Dict]:
        """Cancel an order"""
        endpoint = f"/v2/order/cancel"
        data = {"order_id": order_id}
        return self._make_request("DELETE", endpoint, data=data)
    
    def get_order_details(self, order_id: str) -> Optional[Dict]:
        """Get order details"""
        endpoint = f"/v2/order/details"
        params = {"order_id": order_id}
        return self._make_request("GET", endpoint, params=params)
    
    def get_order_book(self) -> Optional[Dict]:
        """Get all orders for the day"""
        endpoint = "/v2/order/retrieve-all"
        return self._make_request("GET", endpoint)
    
    # ========== Position & Portfolio APIs ==========
    
    def get_positions(self) -> Optional[Dict]:
        """Get current positions"""
        endpoint = "/v2/portfolio/short-term-positions"
        return self._make_request("GET", endpoint)
    
    def get_holdings(self) -> Optional[Dict]:
        """Get holdings"""
        endpoint = "/v2/portfolio/long-term-holdings"
        return self._make_request("GET", endpoint)
    
    # ========== Account & Margin APIs ==========
    
    def get_funds(self) -> Optional[Dict]:
        """Get fund and margin details"""
        endpoint = "/v2/user/get-funds-and-margin"
        return self._make_request("GET", endpoint)
    
    def get_profile(self) -> Optional[Dict]:
        """Get user profile"""
        endpoint = "/v2/user/profile"
        return self._make_request("GET", endpoint)
    
    # ========== Utility Methods ==========
    
    def get_instrument_key(self, exchange: str, symbol: str, expiry: str, strike: float, option_type: str) -> str:
        """
        Generate instrument key for options
        Format: NSE_FO|NIFTY24DEC2024C24000
        """
        # Format expiry as DDMMMYYYY
        expiry_dt = datetime.strptime(expiry, "%Y-%m-%d")
        expiry_str = expiry_dt.strftime("%d%b%Y").upper()
        
        # Format strike price (remove decimal if whole number)
        strike_str = str(int(strike)) if strike == int(strike) else str(strike)
        
        return f"{exchange}_FO|{symbol}{expiry_str}{option_type}{strike_str}"
    
    def test_connection(self, max_retries: int = 3, retry_delay: float = 2.0) -> bool:
        """
        Test API connection with retry logic for container startup
        
        Args:
            max_retries: Maximum number of retry attempts
            retry_delay: Delay in seconds between retries
            
        Returns:
            bool: True if connection successful, False otherwise
        """
        for attempt in range(1, max_retries + 1):
            try:
                profile = self.get_profile()
                if profile and profile.get('status') == 'success':
                    logger.info("✓ Upstox API connection successful")
                    return True
                logger.warning(f"Upstox API returned unexpected response (attempt {attempt}/{max_retries})")
            except Exception as e:
                if attempt < max_retries:
                    logger.warning(f"Connection attempt {attempt}/{max_retries} failed: {e}")
                    logger.info(f"Retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                else:
                    logger.error(f"✗ Upstox API test failed after {max_retries} attempts: {e}")
                    return False
        
        logger.error("✗ Upstox API connection failed")
        return False
    
    def close(self):
        """Close the session and cleanup resources"""
        if hasattr(self, 'session'):
            self.session.close()
            logger.info("Upstox client session closed")


class RateLimiter:
    """Simple rate limiter for API calls"""
    
    def __init__(self, max_calls: int = 10, time_window: float = 1.0):
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls = []
        
    def wait_if_needed(self):
        """Wait if rate limit would be exceeded"""
        now = time.time()
        
        # Remove old calls outside time window
        self.calls = [call_time for call_time in self.calls if now - call_time < self.time_window]
        
        if len(self.calls) >= self.max_calls:
            sleep_time = self.time_window - (now - self.calls[0]) + 0.1
            if sleep_time > 0:
                time.sleep(sleep_time)
                self.calls = []
        
        self.calls.append(time.time())
