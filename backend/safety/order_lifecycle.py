"""
Order Lifecycle Manager
Handles partial fills, order cancellations, and re-entry logic
"""

import asyncio
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict

from backend.core.logger import get_logger

logger = get_logger(__name__)


class OrderState(Enum):
    """Order lifecycle states"""
    PENDING = "pending"             # Order created, not yet submitted
    SUBMITTED = "submitted"         # Submitted to exchange
    ACKNOWLEDGED = "acknowledged"   # Exchange acknowledged
    PARTIAL = "partial"             # Partially filled
    FILLED = "filled"               # Completely filled
    CANCELLING = "cancelling"       # Cancel request sent
    CANCELLED = "cancelled"         # Successfully cancelled
    REJECTED = "rejected"           # Rejected by exchange
    EXPIRED = "expired"             # Order expired


class OrderLifecycleManager:
    """
    Manages order lifecycle including partial fills and cancellations
    
    Features:
    - Order state tracking
    - Partial fill handling
    - Cancellation retry (3 attempts)
    - Re-entry cooldown after stop-out
    - Signal conflict resolution
    """
    
    def __init__(self, config: Dict):
        self.config = config
        
        # Order tracking
        self.orders: Dict[str, Dict] = {}
        
        # Cancellation settings
        self.max_cancel_attempts = config.get('max_cancel_attempts', 3)
        self.cancel_retry_delay = config.get('cancel_retry_delay', 2)  # seconds
        
        # Re-entry settings
        self.stop_out_cooldown_minutes = config.get('stop_out_cooldown_minutes', 5)
        self.stop_out_cooldowns: Dict[str, datetime] = {}  # symbol -> cooldown_until
        
        # Signal conflict resolution
        self.signal_priority_order = config.get('signal_priority_order', [
            'stop_loss', 'take_profit', 'trailing_stop', 'strategy_signal'
        ])
        
    def create_order(
        self,
        order_id: str,
        symbol: str,
        quantity: int,
        price: float,
        side: str,
        order_type: str = 'LIMIT',
        **kwargs
    ) -> Dict:
        """
        Create new order
        
        Args:
            order_id: Unique order ID
            symbol: Instrument symbol
            quantity: Order quantity
            price: Order price
            side: BUY or SELL
            order_type: LIMIT, MARKET, etc.
            **kwargs: Additional order parameters
            
        Returns:
            Order dict
        """
        order = {
            'id': order_id,
            'symbol': symbol,
            'quantity': quantity,
            'filled_quantity': 0,
            'remaining_quantity': quantity,
            'price': price,
            'side': side,
            'order_type': order_type,
            'state': OrderState.PENDING,
            'created_at': datetime.now(),
            'updated_at': datetime.now(),
            'fills': [],
            'cancel_attempts': 0,
            'exchange_order_id': None,
            **kwargs
        }
        
        self.orders[order_id] = order
        
        logger.info(
            f"Order created: {order_id} - {side} {quantity} {symbol} @ {price}"
        )
        
        return order
        
    def update_order_state(
        self,
        order_id: str,
        new_state: OrderState,
        exchange_order_id: Optional[str] = None
    ):
        """Update order state"""
        if order_id not in self.orders:
            logger.warning(f"Order {order_id} not found")
            return
            
        order = self.orders[order_id]
        old_state = order['state']
        order['state'] = new_state
        order['updated_at'] = datetime.now()
        
        if exchange_order_id:
            order['exchange_order_id'] = exchange_order_id
            
        logger.info(
            f"Order {order_id} state: {old_state.value} → {new_state.value}"
        )
        
    def add_fill(
        self,
        order_id: str,
        filled_quantity: int,
        fill_price: float,
        fill_time: Optional[datetime] = None
    ) -> bool:
        """
        Add fill to order
        
        Args:
            order_id: Order ID
            filled_quantity: Quantity filled in this fill
            fill_price: Price of this fill
            fill_time: Time of fill
            
        Returns:
            True if order completely filled
        """
        if order_id not in self.orders:
            logger.warning(f"Order {order_id} not found")
            return False
            
        order = self.orders[order_id]
        
        # Add fill
        fill = {
            'quantity': filled_quantity,
            'price': fill_price,
            'time': fill_time or datetime.now()
        }
        order['fills'].append(fill)
        
        # Update quantities
        order['filled_quantity'] += filled_quantity
        order['remaining_quantity'] = order['quantity'] - order['filled_quantity']
        order['updated_at'] = datetime.now()
        
        # Calculate average fill price
        total_value = sum(f['quantity'] * f['price'] for f in order['fills'])
        order['avg_fill_price'] = total_value / order['filled_quantity']
        
        # Update state
        if order['remaining_quantity'] == 0:
            order['state'] = OrderState.FILLED
            logger.info(
                f"✅ Order {order_id} FILLED: "
                f"{order['filled_quantity']} @ avg ₹{order['avg_fill_price']:.2f}"
            )
            return True
        else:
            order['state'] = OrderState.PARTIAL
            logger.info(
                f"⚠️ Order {order_id} PARTIAL: "
                f"{order['filled_quantity']}/{order['quantity']} filled "
                f"@ avg ₹{order['avg_fill_price']:.2f}"
            )
            return False
            
    async def cancel_order(
        self,
        order_id: str,
        cancel_func: callable,
        reason: str = "Manual cancellation"
    ) -> bool:
        """
        Cancel order with retry logic
        
        Args:
            order_id: Order ID to cancel
            cancel_func: Async function to call exchange cancel API
            reason: Cancellation reason
            
        Returns:
            True if successfully cancelled
        """
        if order_id not in self.orders:
            logger.warning(f"Order {order_id} not found")
            return False
            
        order = self.orders[order_id]
        
        # Check if order can be cancelled
        if order['state'] in [OrderState.FILLED, OrderState.CANCELLED, OrderState.REJECTED]:
            logger.info(f"Order {order_id} cannot be cancelled (state: {order['state'].value})")
            return False
            
        # Update state
        order['state'] = OrderState.CANCELLING
        order['cancel_reason'] = reason
        
        # Retry cancellation up to max attempts
        for attempt in range(1, self.max_cancel_attempts + 1):
            try:
                logger.info(
                    f"Cancelling order {order_id} (attempt {attempt}/{self.max_cancel_attempts})"
                )
                
                # Call exchange cancel function
                success = await cancel_func(
                    order_id=order['exchange_order_id'] or order_id
                )
                
                if success:
                    order['state'] = OrderState.CANCELLED
                    order['cancelled_at'] = datetime.now()
                    order['cancel_attempts'] = attempt
                    
                    logger.info(f"✅ Order {order_id} cancelled successfully")
                    return True
                    
            except Exception as e:
                logger.error(f"Cancel attempt {attempt} failed: {e}")
                
            # Wait before retry (unless last attempt)
            if attempt < self.max_cancel_attempts:
                await asyncio.sleep(self.cancel_retry_delay)
                
        # All attempts failed
        logger.error(
            f"❌ Failed to cancel order {order_id} after {self.max_cancel_attempts} attempts"
        )
        order['cancel_attempts'] = self.max_cancel_attempts
        
        return False
        
    def start_stop_out_cooldown(self, symbol: str):
        """
        Start cooldown period after stop-out
        
        Args:
            symbol: Symbol that was stopped out
        """
        cooldown_until = datetime.now() + timedelta(minutes=self.stop_out_cooldown_minutes)
        self.stop_out_cooldowns[symbol] = cooldown_until
        
        logger.warning(
            f"⏳ Stop-out cooldown started for {symbol}\n"
            f"No re-entry until {cooldown_until.strftime('%H:%M:%S')}"
        )
        
    def is_in_cooldown(self, symbol: str) -> bool:
        """
        Check if symbol is in stop-out cooldown
        
        Args:
            symbol: Symbol to check
            
        Returns:
            True if in cooldown
        """
        if symbol not in self.stop_out_cooldowns:
            return False
            
        cooldown_until = self.stop_out_cooldowns[symbol]
        
        if datetime.now() < cooldown_until:
            remaining = (cooldown_until - datetime.now()).total_seconds()
            return True
        else:
            # Cooldown expired
            del self.stop_out_cooldowns[symbol]
            logger.info(f"✅ Cooldown expired for {symbol}")
            return False
            
    def resolve_signal_conflict(self, signals: List[Dict]) -> Optional[Dict]:
        """
        Resolve conflicts when multiple signals for same symbol
        
        Args:
            signals: List of signal dicts (each must have 'type' field)
            
        Returns:
            Highest priority signal or None
        """
        if not signals:
            return None
            
        if len(signals) == 1:
            return signals[0]
            
        # Sort by priority
        prioritized = []
        for signal in signals:
            signal_type = signal.get('type', 'strategy_signal')
            
            if signal_type in self.signal_priority_order:
                priority = self.signal_priority_order.index(signal_type)
            else:
                priority = len(self.signal_priority_order)  # Lowest priority
                
            prioritized.append((priority, signal))
            
        # Sort by priority (lower number = higher priority)
        prioritized.sort(key=lambda x: x[0])
        
        winning_signal = prioritized[0][1]
        
        logger.info(
            f"Signal conflict resolved: {len(signals)} signals, "
            f"winner: {winning_signal.get('type', 'unknown')}"
        )
        
        return winning_signal
        
    def get_order_status(self, order_id: str) -> Optional[Dict]:
        """Get order status"""
        return self.orders.get(order_id)
        
    def get_orders_by_state(self, state: OrderState) -> List[Dict]:
        """Get all orders in a specific state"""
        return [
            order for order in self.orders.values()
            if order['state'] == state
        ]
        
    def get_partial_fills(self) -> List[Dict]:
        """Get all partially filled orders"""
        return self.get_orders_by_state(OrderState.PARTIAL)
        
    def get_pending_cancellations(self) -> List[Dict]:
        """Get orders being cancelled"""
        return self.get_orders_by_state(OrderState.CANCELLING)
        
    def cleanup_old_orders(self, hours: int = 24):
        """Remove old completed orders"""
        cutoff = datetime.now() - timedelta(hours=hours)
        
        terminal_states = [
            OrderState.FILLED,
            OrderState.CANCELLED,
            OrderState.REJECTED,
            OrderState.EXPIRED
        ]
        
        to_remove = [
            order_id for order_id, order in self.orders.items()
            if order['state'] in terminal_states and order['updated_at'] < cutoff
        ]
        
        for order_id in to_remove:
            del self.orders[order_id]
            
        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} old orders")
            
    def get_lifecycle_stats(self) -> Dict:
        """Get order lifecycle statistics"""
        state_counts = defaultdict(int)
        
        for order in self.orders.values():
            state_counts[order['state'].value] += 1
            
        partial_fills = self.get_partial_fills()
        partial_fill_rates = [
            order['filled_quantity'] / order['quantity']
            for order in partial_fills
        ]
        
        return {
            'total_orders': len(self.orders),
            'by_state': dict(state_counts),
            'partial_fills': {
                'count': len(partial_fills),
                'avg_fill_rate': sum(partial_fill_rates) / len(partial_fill_rates)
                if partial_fill_rates else 0
            },
            'active_cooldowns': len(self.stop_out_cooldowns),
            'cooldown_symbols': list(self.stop_out_cooldowns.keys())
        }
