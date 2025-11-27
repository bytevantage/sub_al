"""
Rate Limiter
Handles API rate limiting and throttling with exponential backoff
"""

import asyncio
import time
from typing import Dict, Optional, Callable, Any
from collections import deque
from datetime import datetime, timedelta

from backend.core.logger import get_logger

logger = get_logger(__name__)


class RateLimiter:
    """
    Token bucket rate limiter with exponential backoff
    
    Features:
    - Token bucket algorithm
    - Per-second rate limiting
    - Exponential backoff on 429 errors
    - Order queue management
    - Request prioritization
    """
    
    def __init__(self, config: Dict):
        self.config = config
        
        # Rate limit parameters
        self.max_requests_per_second = config.get('max_requests_per_second', 10)
        self.max_orders_per_second = config.get('max_orders_per_second', 5)
        
        # Token buckets
        self.request_tokens = self.max_requests_per_second
        self.order_tokens = self.max_orders_per_second
        self.last_refill = time.time()
        
        # Request history (for monitoring)
        self.request_history = deque(maxlen=1000)
        self.order_history = deque(maxlen=100)
        
        # Backoff state
        self.backoff_until = None
        self.consecutive_429s = 0
        self.backoff_multiplier = config.get('backoff_multiplier', 2)
        self.max_backoff_seconds = config.get('max_backoff_seconds', 60)
        
        # Queue for pending requests
        self.request_queue = []
        self.is_processing_queue = False
        
    async def acquire_token(self, token_type: str = 'request') -> bool:
        """
        Acquire a token for API call
        
        Args:
            token_type: 'request' or 'order'
            
        Returns:
            True if token acquired (may wait)
        """
        
        # Check if in backoff period
        if self.backoff_until:
            wait_time = (self.backoff_until - datetime.now()).total_seconds()
            if wait_time > 0:
                logger.warning(
                    f"⏳ Rate limit backoff active. Waiting {wait_time:.1f}s..."
                )
                await asyncio.sleep(wait_time)
                self.backoff_until = None
                
        # Refill tokens
        self._refill_tokens()
        
        # Get appropriate bucket
        if token_type == 'order':
            tokens = self.order_tokens
            max_tokens = self.max_orders_per_second
        else:
            tokens = self.request_tokens
            max_tokens = self.max_requests_per_second
            
        # Wait if no tokens available
        while tokens <= 0:
            wait_time = 1.0 / max_tokens  # Wait for next token
            logger.debug(f"No {token_type} tokens available. Waiting {wait_time:.2f}s...")
            await asyncio.sleep(wait_time)
            self._refill_tokens()
            tokens = self.order_tokens if token_type == 'order' else self.request_tokens
            
        # Consume token
        if token_type == 'order':
            self.order_tokens -= 1
            self.order_history.append(datetime.now())
        else:
            self.request_tokens -= 1
            self.request_history.append(datetime.now())
            
        return True
        
    def _refill_tokens(self):
        """Refill tokens based on elapsed time"""
        now = time.time()
        elapsed = now - self.last_refill
        
        if elapsed >= 1.0:
            # Refill full bucket every second
            self.request_tokens = self.max_requests_per_second
            self.order_tokens = self.max_orders_per_second
            self.last_refill = now
            
    async def execute_with_retry(
        self,
        func: Callable,
        *args,
        max_retries: int = 3,
        token_type: str = 'request',
        **kwargs
    ) -> Optional[Any]:
        """
        Execute function with rate limiting and retry logic
        
        Args:
            func: Async function to execute
            args: Function arguments
            max_retries: Maximum retry attempts
            token_type: Token type to acquire
            kwargs: Function keyword arguments
            
        Returns:
            Function result or None on failure
        """
        
        for attempt in range(max_retries):
            try:
                # Acquire token
                await self.acquire_token(token_type)
                
                # Execute function
                result = await func(*args, **kwargs)
                
                # Success - reset backoff
                self.consecutive_429s = 0
                
                return result
                
            except Exception as e:
                error_str = str(e).lower()
                
                # Check for rate limit error
                if '429' in error_str or 'rate limit' in error_str or 'too many' in error_str:
                    self.consecutive_429s += 1
                    backoff_seconds = self._calculate_backoff()
                    
                    logger.warning(
                        f"⚠️ Rate limit hit (attempt {attempt + 1}/{max_retries}). "
                        f"Backing off {backoff_seconds:.1f}s..."
                    )
                    
                    self.backoff_until = datetime.now() + timedelta(seconds=backoff_seconds)
                    await asyncio.sleep(backoff_seconds)
                    
                    continue
                    
                # Other error - don't retry
                logger.error(f"Error executing function: {e}")
                return None
                
        logger.error(f"Max retries ({max_retries}) exceeded")
        return None
        
    def _calculate_backoff(self) -> float:
        """Calculate exponential backoff delay"""
        # Exponential: 1s, 2s, 4s, 8s, 16s, ... up to max
        delay = min(
            2 ** (self.consecutive_429s - 1),
            self.max_backoff_seconds
        )
        
        # Add jitter (±20%)
        import random
        jitter = delay * random.uniform(-0.2, 0.2)
        
        return delay + jitter
        
    def report_429_error(self):
        """Manually report a 429 error (for non-exception cases)"""
        self.consecutive_429s += 1
        backoff_seconds = self._calculate_backoff()
        self.backoff_until = datetime.now() + timedelta(seconds=backoff_seconds)
        
        logger.warning(
            f"⚠️ Manual 429 reported. Backoff {backoff_seconds:.1f}s"
        )
        
    def get_stats(self) -> Dict:
        """Get rate limiter statistics"""
        now = datetime.now()
        
        # Count recent requests
        recent_requests = sum(
            1 for ts in self.request_history
            if (now - ts).total_seconds() < 60
        )
        
        recent_orders = sum(
            1 for ts in self.order_history
            if (now - ts).total_seconds() < 60
        )
        
        return {
            'request_tokens_available': self.request_tokens,
            'order_tokens_available': self.order_tokens,
            'max_requests_per_second': self.max_requests_per_second,
            'max_orders_per_second': self.max_orders_per_second,
            'requests_last_minute': recent_requests,
            'orders_last_minute': recent_orders,
            'consecutive_429s': self.consecutive_429s,
            'backoff_active': self.backoff_until is not None,
            'backoff_until': self.backoff_until.isoformat() if self.backoff_until else None
        }
        
    async def queue_order(self, order_func: Callable, *args, **kwargs):
        """
        Queue an order for execution with rate limiting
        
        Args:
            order_func: Async order function
            args: Function arguments
            kwargs: Function keyword arguments
        """
        
        order = {
            'func': order_func,
            'args': args,
            'kwargs': kwargs,
            'queued_at': datetime.now(),
            'priority': kwargs.pop('priority', 0)  # Higher priority = executed first
        }
        
        self.request_queue.append(order)
        
        # Sort by priority
        self.request_queue.sort(key=lambda x: x['priority'], reverse=True)
        
        logger.info(f"Order queued (queue size: {len(self.request_queue)})")
        
        # Start processing if not already running
        if not self.is_processing_queue:
            asyncio.create_task(self._process_queue())
            
    async def _process_queue(self):
        """Process queued orders with rate limiting"""
        self.is_processing_queue = True
        
        while self.request_queue:
            order = self.request_queue.pop(0)
            
            wait_time = (datetime.now() - order['queued_at']).total_seconds()
            logger.info(f"Processing queued order (waited {wait_time:.1f}s)")
            
            try:
                await self.execute_with_retry(
                    order['func'],
                    *order['args'],
                    token_type='order',
                    **order['kwargs']
                )
            except Exception as e:
                logger.error(f"Error processing queued order: {e}")
                
        self.is_processing_queue = False
        logger.info("Queue processing complete")
