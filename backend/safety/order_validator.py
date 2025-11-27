"""
Order Validator - Fat-Finger Prevention
Validates all orders before submission to prevent costly errors
"""

from typing import Dict, Optional, Tuple
from datetime import datetime
from enum import Enum

from backend.core.logger import get_logger

logger = get_logger(__name__)


class ValidationResult(Enum):
    """Order validation results"""
    VALID = "valid"
    REJECTED_SIZE = "rejected_size"
    REJECTED_PRICE = "rejected_price"
    REJECTED_QUANTITY = "rejected_quantity"
    REJECTED_CAPITAL = "rejected_capital"
    REJECTED_DUPLICATE = "rejected_duplicate"


class OrderValidator:
    """
    Validates orders before submission to prevent fat-finger errors
    
    Validations:
    - Maximum order size (default 5 lots)
    - Price bands (±5% from LTP)
    - Quantity sanity checks
    - Self-trade prevention
    - Capital allocation limits
    """
    
    def __init__(self, config: Dict):
        self.config = config
        
        # Thresholds
        self.max_lots = config.get('max_lots_per_order', 5)
        self.price_band_percent = config.get('price_band_percent', 5)
        self.min_price = config.get('min_price', 0.05)  # ₹0.05
        self.max_price = config.get('max_price', 1000)  # ₹1000
        self.max_capital_per_trade = config.get('max_capital_per_trade', 50000)  # ₹50k
        
        # Track recent orders to prevent duplicates
        self.recent_orders = []
        self.duplicate_window_seconds = 5
        
    def validate_order(
        self,
        symbol: str,
        quantity: int,
        price: float,
        side: str,
        ltp: float,
        lot_size: int,
        available_capital: float
    ) -> Tuple[ValidationResult, Optional[str]]:
        """
        Validate order before submission
        
        Args:
            symbol: Instrument symbol
            quantity: Order quantity
            price: Order price
            side: BUY or SELL
            ltp: Last traded price
            lot_size: Lot size for symbol
            available_capital: Available capital for trading
            
        Returns:
            (ValidationResult, error_message)
        """
        
        # 1. Check lot size
        num_lots = quantity / lot_size
        if num_lots > self.max_lots:
            msg = (
                f"Order size {num_lots:.1f} lots exceeds maximum {self.max_lots} lots. "
                f"Possible fat-finger error!"
            )
            logger.error(f"❌ REJECTED: {msg}")
            return ValidationResult.REJECTED_SIZE, msg
            
        # 2. Check price bands
        if ltp > 0:
            price_deviation = abs((price - ltp) / ltp * 100)
            
            if price_deviation > self.price_band_percent:
                msg = (
                    f"Price {price:.2f} deviates {price_deviation:.1f}% from LTP {ltp:.2f}. "
                    f"Exceeds {self.price_band_percent}% band. Possible fat-finger error!"
                )
                logger.error(f"❌ REJECTED: {msg}")
                return ValidationResult.REJECTED_PRICE, msg
                
        # 3. Check absolute price sanity
        if price < self.min_price:
            msg = f"Price {price:.2f} below minimum {self.min_price}"
            logger.error(f"❌ REJECTED: {msg}")
            return ValidationResult.REJECTED_PRICE, msg
            
        if price > self.max_price:
            msg = f"Price {price:.2f} exceeds maximum {self.max_price}"
            logger.error(f"❌ REJECTED: {msg}")
            return ValidationResult.REJECTED_PRICE, msg
            
        # 4. Check quantity sanity
        if quantity <= 0:
            msg = f"Invalid quantity {quantity}"
            logger.error(f"❌ REJECTED: {msg}")
            return ValidationResult.REJECTED_QUANTITY, msg
            
        if quantity % lot_size != 0:
            msg = f"Quantity {quantity} not a multiple of lot size {lot_size}"
            logger.error(f"❌ REJECTED: {msg}")
            return ValidationResult.REJECTED_QUANTITY, msg
            
        # 5. Check capital requirement
        capital_required = quantity * price
        
        if capital_required > self.max_capital_per_trade:
            msg = (
                f"Capital required ₹{capital_required:,.0f} exceeds "
                f"maximum ₹{self.max_capital_per_trade:,.0f} per trade"
            )
            logger.error(f"❌ REJECTED: {msg}")
            return ValidationResult.REJECTED_CAPITAL, msg
            
        if side == "BUY" and capital_required > available_capital:
            msg = (
                f"Insufficient capital: required ₹{capital_required:,.0f}, "
                f"available ₹{available_capital:,.0f}"
            )
            logger.error(f"❌ REJECTED: {msg}")
            return ValidationResult.REJECTED_CAPITAL, msg
            
        # 6. Check for duplicate orders (self-trade prevention)
        if self._is_duplicate_order(symbol, quantity, price, side):
            msg = f"Duplicate order detected within {self.duplicate_window_seconds}s"
            logger.error(f"❌ REJECTED: {msg}")
            return ValidationResult.REJECTED_DUPLICATE, msg
            
        # All checks passed
        logger.info(
            f"✅ Order validated: {symbol} {side} {quantity}@{price:.2f} "
            f"({num_lots:.1f} lots, ₹{capital_required:,.0f})"
        )
        
        # Track this order
        self._track_order(symbol, quantity, price, side)
        
        return ValidationResult.VALID, None
        
    def _is_duplicate_order(
        self,
        symbol: str,
        quantity: int,
        price: float,
        side: str
    ) -> bool:
        """Check if this order was recently submitted"""
        now = datetime.now()
        
        # Clean old orders
        self.recent_orders = [
            o for o in self.recent_orders
            if (now - o['timestamp']).total_seconds() < self.duplicate_window_seconds
        ]
        
        # Check for duplicate
        for order in self.recent_orders:
            if (
                order['symbol'] == symbol and
                order['quantity'] == quantity and
                abs(order['price'] - price) < 0.01 and
                order['side'] == side
            ):
                return True
                
        return False
        
    def _track_order(self, symbol: str, quantity: int, price: float, side: str):
        """Track order to prevent duplicates"""
        self.recent_orders.append({
            'symbol': symbol,
            'quantity': quantity,
            'price': price,
            'side': side,
            'timestamp': datetime.now()
        })
        
    def validate_stop_loss(
        self,
        entry_price: float,
        stop_loss: float,
        side: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate stop-loss placement
        
        Args:
            entry_price: Entry price
            stop_loss: Stop-loss price
            side: BUY or SELL
            
        Returns:
            (is_valid, error_message)
        """
        
        # For BUY positions, stop should be below entry
        if side == "BUY":
            if stop_loss >= entry_price:
                msg = f"Stop-loss {stop_loss} must be below entry {entry_price} for BUY"
                logger.error(f"❌ Invalid stop-loss: {msg}")
                return False, msg
                
            loss_percent = (entry_price - stop_loss) / entry_price * 100
            
        # For SELL positions, stop should be above entry
        else:
            if stop_loss <= entry_price:
                msg = f"Stop-loss {stop_loss} must be above entry {entry_price} for SELL"
                logger.error(f"❌ Invalid stop-loss: {msg}")
                return False, msg
                
            loss_percent = (stop_loss - entry_price) / entry_price * 100
            
        # Check if stop is too wide (>20% loss)
        max_stop_percent = self.config.get('max_stop_loss_percent', 20)
        if loss_percent > max_stop_percent:
            msg = (
                f"Stop-loss {loss_percent:.1f}% too wide. "
                f"Maximum allowed: {max_stop_percent}%"
            )
            logger.error(f"❌ Invalid stop-loss: {msg}")
            return False, msg
            
        # Check if stop is too tight (<0.5% loss)
        min_stop_percent = self.config.get('min_stop_loss_percent', 0.5)
        if loss_percent < min_stop_percent:
            msg = (
                f"Stop-loss {loss_percent:.1f}% too tight. "
                f"Minimum recommended: {min_stop_percent}%"
            )
            logger.warning(f"⚠️ Tight stop-loss: {msg}")
            # Warning only, don't reject
            
        return True, None
        
    def get_validation_stats(self) -> Dict:
        """Get validation statistics"""
        return {
            'thresholds': {
                'max_lots_per_order': self.max_lots,
                'price_band_percent': self.price_band_percent,
                'min_price': self.min_price,
                'max_price': self.max_price,
                'max_capital_per_trade': self.max_capital_per_trade
            },
            'recent_orders_tracked': len(self.recent_orders),
            'duplicate_window_seconds': self.duplicate_window_seconds
        }
