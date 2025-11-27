"""
Upstox WebSocket Market Feed Manager
Handles real-time market data streaming to eliminate REST API rate limits
"""

import asyncio
import json
import ssl
import websockets
from typing import Dict, List, Callable, Optional
from datetime import datetime
from google.protobuf.json_format import MessageToDict

from backend.core.logger import get_data_logger
from backend.core.upstox_client import UpstoxClient
from backend.data.proto import MarketDataFeedV3_pb2 as pb

logger = get_data_logger()


class MarketFeedManager:
    """Manages WebSocket connection to Upstox market data feed"""
    
    _instance = None
    _lock = asyncio.Lock()
    
    def __new__(cls, access_token: str):
        if cls._instance is None:
            cls._instance = super(MarketFeedManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self, access_token: str):
        # Only initialize once
        if hasattr(self, '_initialized'):
            return
        
        self.access_token = access_token
        self.websocket = None
        self.is_connected = False
        self.subscribers: Dict[str, List[Callable]] = {}
        self.latest_data: Dict[str, Dict] = {}
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 5
        self._reconnect_delay = 5
        # Add lock to prevent WebSocket concurrency issues
        self._websocket_lock = asyncio.Lock()
        # Initialize UpstoxClient for connection pooling
        self.upstox_client = UpstoxClient(access_token)
        self._initialized = True
        
    def get_market_data_feed_authorize(self):
        """Get authorization for market data feed"""
        url = '/v3/feed/market-data-feed/authorize'
        
        try:
            response = self.upstox_client.session.get(url=f"https://api.upstox.com{url}", timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to authorize market feed: {e}")
            raise
    
    def decode_protobuf(self, buffer):
        """Decode protobuf message"""
        feed_response = pb.FeedResponse()
        feed_response.ParseFromString(buffer)
        return feed_response
    
    async def connect(self, instrument_keys: List[str], mode: str = "full"):
        """
        Connect to WebSocket and subscribe to instruments
        
        Args:
            instrument_keys: List of instrument keys (e.g., ["NSE_INDEX|Nifty 50", "NSE_INDEX|Nifty Bank"])
            mode: Data mode - "full" or "quote"
        """
        # Prevent multiple connection attempts
        async with self._websocket_lock:
            if self.is_connected and self.websocket:
                logger.info("WebSocket already connected, skipping duplicate connection")
                return
            
            max_attempts = 3
            for attempt in range(max_attempts):
                try:
                    logger.info(f"WebSocket connection attempt {attempt + 1}/{max_attempts}")
                    
                    # Create SSL context
                    ssl_context = ssl.create_default_context()
                    ssl_context.check_hostname = False
                    ssl_context.verify_mode = ssl.CERT_NONE
                    
                    # Get authorization
                    auth_response = self.get_market_data_feed_authorize()
                    ws_url = auth_response["data"]["authorized_redirect_uri"]
                    logger.info(f"WebSocket URL: {ws_url}")
                    
                    # Connect to WebSocket
                    self.websocket = await websockets.connect(ws_url, ssl=ssl_context, ping_interval=20, ping_timeout=10)
                    self.is_connected = True
                    logger.info("✓ WebSocket market feed connected")
                    
                    await asyncio.sleep(1)  # Wait for connection to stabilize
                    
                    # Subscribe to instruments
                    await self.subscribe(instrument_keys, mode)
                    
                    # Start listening for data
                    asyncio.create_task(self._listen())
                    
                    self._reconnect_attempts = 0  # Reset on successful connection
                    return  # Success, exit retry loop
                    
                except Exception as e:
                    logger.error(f"WebSocket connection attempt {attempt + 1} failed: {e}")
                    self.is_connected = False
                    if self.websocket:
                        try:
                            await self.websocket.close()
                        except:
                            pass
                        self.websocket = None
                    
                    if attempt < max_attempts - 1:
                        logger.info(f"Retrying WebSocket connection in 5 seconds...")
                        await asyncio.sleep(5)
                    else:
                        logger.error("All WebSocket connection attempts failed")
                        raise
    
    async def subscribe(self, instrument_keys: List[str], mode: str = "full"):
        """Subscribe to instrument keys"""
        if not self.is_connected or not self.websocket:
            logger.warning("Not connected to WebSocket")
            return
        
        # Store for reconnection
        if not hasattr(self, '_last_subscribed_instruments'):
            self._last_subscribed_instruments = []
        
        # Add new instruments to the list
        for key in instrument_keys:
            if key not in self._last_subscribed_instruments:
                self._last_subscribed_instruments.append(key)
        
        data = {
            "guid": "trading_system",
            "method": "sub",
            "data": {
                "mode": mode,
                "instrumentKeys": instrument_keys
            }
        }
        
        binary_data = json.dumps(data).encode('utf-8')
        await self.websocket.send(binary_data)
        logger.info(f"✓ Subscribed to {len(instrument_keys)} instruments: {instrument_keys}")
    
    async def unsubscribe(self, instrument_keys: List[str]):
        """Unsubscribe from instrument keys"""
        if not self.is_connected or not self.websocket:
            return
        
        data = {
            "guid": "trading_system",
            "method": "unsub",
            "data": {
                "instrumentKeys": instrument_keys
            }
        }
        
        binary_data = json.dumps(data).encode('utf-8')
        await self.websocket.send(binary_data)
        logger.info(f"Unsubscribed from {len(instrument_keys)} instruments")
    
    async def _listen(self):
        """Listen for incoming market data"""
        message_count = 0
        try:
            while self.is_connected and self.websocket:
                # Add lock to prevent concurrent recv calls
                async with self._websocket_lock:
                    if not self.is_connected or not self.websocket:
                        break
                    message = await self.websocket.recv()
                
                decoded_data = self.decode_protobuf(message)
                data_dict = MessageToDict(decoded_data)
                
                # Process and store the data
                await self._process_data(data_dict)
                
                message_count += 1
                # Log every 500 messages to confirm feed is active
                if message_count % 500 == 0:
                    logger.info(f"✓ Processed {message_count} market data messages")
                
        except websockets.exceptions.ConnectionClosed as e:
            logger.warning(f"WebSocket connection closed: {e}. Will attempt reconnection.")
            self.is_connected = False
            # Auto-reconnect with last known instruments
            if hasattr(self, '_last_subscribed_instruments'):
                asyncio.create_task(self._handle_reconnect(self._last_subscribed_instruments, "full"))
        except Exception as e:
            logger.error(f"Error in WebSocket listener: {e}")
            self.is_connected = False
            if hasattr(self, '_last_subscribed_instruments'):
                asyncio.create_task(self._handle_reconnect(self._last_subscribed_instruments, "full"))
    
    async def _process_data(self, data_dict: Dict):
        """Process incoming market data and notify subscribers"""
        try:
            # Extract feed data
            if "feeds" not in data_dict:
                return
            
            for instrument_key, feed_data in data_dict["feeds"].items():
                # Store latest data
                self.latest_data[instrument_key] = {
                    **feed_data,
                    "timestamp": datetime.now(),
                    "instrument_key": instrument_key
                }
                
                # Notify subscribers
                if instrument_key in self.subscribers:
                    for callback in self.subscribers[instrument_key]:
                        try:
                            await callback(instrument_key, feed_data)
                        except Exception as e:
                            logger.error(f"Error in subscriber callback: {e}")
                            
        except Exception as e:
            logger.error(f"Error processing market data: {e}")
    
    def register_callback(self, instrument_key: str, callback: Callable):
        """Register a callback for specific instrument updates"""
        if instrument_key not in self.subscribers:
            self.subscribers[instrument_key] = []
        self.subscribers[instrument_key].append(callback)
    
    def get_latest_data(self, instrument_key: str) -> Optional[Dict]:
        """Get latest data for an instrument"""
        return self.latest_data.get(instrument_key)
    
    def get_spot_price(self, instrument_key: str) -> Optional[float]:
        """Get current spot price for an instrument"""
        data = self.latest_data.get(instrument_key)
        if not data:
            return None
        
        # Try different price fields based on data type
        if "ff" in data and "marketFF" in data["ff"]:
            market_ff = data["ff"]["marketFF"]
            if "ltpc" in market_ff and "ltp" in market_ff["ltpc"]:
                return float(market_ff["ltpc"]["ltp"])
        
        # Fallback to last traded price if available
        if "ltp" in data:
            return float(data["ltp"])
        
        return None
    
    async def _handle_reconnect(self, instrument_keys: List[str], mode: str):
        """Handle reconnection logic"""
        if self._reconnect_attempts >= self._max_reconnect_attempts:
            logger.error("Max reconnection attempts reached. Giving up.")
            return
        
        self._reconnect_attempts += 1
        delay = self._reconnect_delay * (2 ** (self._reconnect_attempts - 1))  # Exponential backoff
        
        logger.info(f"Attempting reconnection {self._reconnect_attempts}/{self._max_reconnect_attempts} in {delay}s...")
        await asyncio.sleep(delay)
        
        await self.connect(instrument_keys, mode)
    
    async def disconnect(self):
        """Disconnect from WebSocket"""
        self.is_connected = False
        if self.websocket:
            await self.websocket.close()
            logger.info("WebSocket disconnected")
        # Close UpstoxClient session
        if hasattr(self, 'upstox_client'):
            self.upstox_client.close()
    
    def is_alive(self) -> bool:
        """Check if connection is alive"""
        return self.is_connected and self.websocket is not None
