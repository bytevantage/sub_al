"""
Position Persistence Service
Manages saving and restoring open positions across restarts
"""

from datetime import datetime
from typing import List, Dict, Optional
from sqlalchemy.orm import Session

# Import timezone utilities for consistent time handling
from backend.core.timezone_utils import now_utc, to_ist

from backend.core.logger import get_logger
from backend.database.database import get_db
from backend.database.models import Position

logger = get_logger(__name__)


class PositionPersistenceService:
    """
    Handles position persistence to database
    - Save positions when opened
    - Restore positions on startup
    - Update positions with current prices
    - Remove positions when closed
    """
    
    def __init__(self):
        self.logger = logger
    
    def _convert_numpy_types(self, data: Dict) -> Dict:
        """Convert numpy types to Python native types for PostgreSQL compatibility"""
        import numpy as np
        converted = {}
        for key, value in data.items():
            if isinstance(value, (np.floating, np.float32, np.float64)):
                converted[key] = float(value)
            elif isinstance(value, (np.integer, np.int32, np.int64)):
                converted[key] = int(value)
            elif isinstance(value, np.ndarray):
                converted[key] = value.tolist()
            else:
                converted[key] = value
        return converted
    
    def save_position(self, position_data: Dict, db: Session = None) -> bool:
        """
        Save an open position to database
        
        Args:
            position_data: Dictionary with position details
            db: Database session (optional)
        
        Returns:
            True if saved successfully
        """
        try:
            # Convert numpy types to Python native types
            position_data = self._convert_numpy_types(position_data)
            
            should_close = False
            if db is None:
                db = next(get_db())
                should_close = True
            
            try:
                # Ensure instrument_key is preserved via metadata for restoration
                instrument_key = position_data.get('instrument_key')
                metadata = dict(position_data.get('position_metadata') or {})
                if instrument_key:
                    metadata['instrument_key'] = instrument_key
                if metadata:
                    position_data['position_metadata'] = metadata
                
                # Check if position already exists
                existing = db.query(Position).filter(
                    Position.position_id == position_data.get('position_id')
                ).first()
                
                if existing:
                    # Update existing position
                    for key, value in position_data.items():
                        # Skip 'id' field as it's the primary key and should not be updated
                        if key != 'id' and hasattr(existing, key):
                            setattr(existing, key, value)
                    existing.last_updated = now_utc()
                    self.logger.info(f"✓ Updated position: {position_data.get('position_id')}")
                else:
                    # Create new position
                    position = Position(
                        position_id=position_data.get('position_id'),
                        symbol=position_data.get('symbol'),
                        instrument_type=position_data.get('instrument_type'),
                        strike_price=position_data.get('strike_price'),
                        expiry=position_data.get('expiry'),
                        direction=position_data.get('direction'),
                        entry_price=position_data.get('entry_price'),
                        quantity=position_data.get('quantity'),
                        entry_value=position_data.get('entry_value'),
                        stop_loss=position_data.get('stop_loss'),
                        target=position_data.get('target_price'),  # Fixed: database column is 'target' but position dict has 'target_price'
                        trailing_sl=position_data.get('trailing_sl'),
                        current_price=position_data.get('current_price'),
                        unrealized_pnl=position_data.get('unrealized_pnl', 0.0),
                        unrealized_pnl_pct=position_data.get('unrealized_pnl_pct', 0.0),
                        strategy_name=position_data.get('strategy_name'),
                        signal_strength=position_data.get('signal_strength'),
                        ml_score=position_data.get('ml_score'),
                        entry_time=position_data.get('entry_time') or now_utc(),
                        order_id=position_data.get('order_id'),
                        instrument_token=position_data.get('instrument_token'),
                        delta_entry=position_data.get('delta_entry'),
                        gamma_entry=position_data.get('gamma_entry'),
                        theta_entry=position_data.get('theta_entry'),
                        vega_entry=position_data.get('vega_entry'),
                        position_metadata=position_data.get('position_metadata', {})
                    )
                    db.add(position)
                    self.logger.info(f"✓ Saved new position: {position_data.get('position_id')}")
                
                db.commit()
                return True
                
            finally:
                if should_close:
                    db.close()
        
        except Exception as e:
            self.logger.error(f"Error saving position: {e}")
            if db and should_close:
                db.rollback()
                db.close()
            return False
    
    def restore_positions(self, db: Session = None) -> List[Dict]:
        """
        Restore all open positions from database
        Called on system startup
        
        Returns:
            List of position dictionaries
        """
        try:
            should_close = False
            if db is None:
                db = next(get_db())
                should_close = True
            
            try:
                # Get all positions ordered by entry time
                positions = db.query(Position).order_by(Position.entry_time).all()
                
                position_list = [pos.to_dict() for pos in positions]
                
                if position_list:
                    self.logger.info(f"✓ Restored {len(position_list)} open positions from database")
                else:
                    self.logger.info("No open positions to restore")
                
                return position_list
                
            finally:
                if should_close:
                    db.close()
        
        except Exception as e:
            self.logger.error(f"Error restoring positions: {e}")
            if db and should_close:
                db.close()
            return []
    
    def update_position_price(self, position_id: str, current_price: float, 
                             unrealized_pnl: float = None, db: Session = None) -> bool:
        """
        Update position with current market price and P&L
        
        Args:
            position_id: Position identifier
            current_price: Current market price
            unrealized_pnl: Calculated unrealized P&L (optional)
            db: Database session (optional)
        
        Returns:
            True if updated successfully
        """
        try:
            should_close = False
            if db is None:
                db = next(get_db())
                should_close = True
            
            try:
                position = db.query(Position).filter(
                    Position.position_id == position_id
                ).first()
                
                if position:
                    position.current_price = current_price
                    position.last_updated = now_utc()
                    
                    # Calculate unrealized P&L if not provided
                    if unrealized_pnl is not None:
                        position.unrealized_pnl = unrealized_pnl
                    else:
                        # Calculate based on direction
                        if position.direction == 'BUY':
                            position.unrealized_pnl = (current_price - position.entry_price) * position.quantity
                        else:  # SELL
                            position.unrealized_pnl = (position.entry_price - current_price) * position.quantity
                    
                    # Calculate percentage
                    if position.entry_value > 0:
                        position.unrealized_pnl_pct = (position.unrealized_pnl / position.entry_value) * 100
                    
                    db.commit()
                    return True
                else:
                    self.logger.warning(f"Position not found: {position_id}")
                    return False
                
            finally:
                if should_close:
                    db.close()
        
        except Exception as e:
            self.logger.error(f"Error updating position price: {e}")
            if db and should_close:
                db.rollback()
                db.close()
            return False
    
    def update_position_metadata(self, position_id: str, trailing_sl: float = None, 
                                 position_metadata: dict = None, db: Session = None) -> bool:
        """
        Update position trailing SL and metadata (for target hit flags)
        
        Args:
            position_id: Position identifier
            trailing_sl: New trailing stop loss value (optional)
            position_metadata: Updated metadata dict (optional)
            db: Database session (optional)
        
        Returns:
            True if updated successfully
        """
        try:
            should_close = False
            if db is None:
                db = next(get_db())
                should_close = True
            
            try:
                position = db.query(Position).filter(
                    Position.position_id == position_id
                ).first()
                
                if position:
                    if trailing_sl is not None:
                        position.trailing_sl = trailing_sl
                    if position_metadata is not None:
                        position.position_metadata = position_metadata
                    position.last_updated = now_utc()
                    
                    db.commit()
                    return True
                else:
                    self.logger.warning(f"Position not found: {position_id}")
                    return False
                
            finally:
                if should_close:
                    db.close()
        
        except Exception as e:
            self.logger.error(f"Error updating position metadata: {e}")
            if db and should_close:
                db.rollback()
                db.close()
            return False
    
    def remove_position(self, position_id: str, db: Session = None) -> bool:
        """
        Remove a position from database (when closed)
        
        Args:
            position_id: Position identifier
            db: Database session (optional)
        
        Returns:
            True if removed successfully
        """
        try:
            should_close = False
            if db is None:
                db = next(get_db())
                should_close = True
            
            try:
                position = db.query(Position).filter(
                    Position.position_id == position_id
                ).first()
                
                if position:
                    db.delete(position)
                    db.commit()
                    self.logger.info(f"✓ Removed closed position: {position_id}")
                    return True
                else:
                    self.logger.warning(f"Position not found for removal: {position_id}")
                    return False
                
            finally:
                if should_close:
                    db.close()
        
        except Exception as e:
            self.logger.error(f"Error removing position: {e}")
            if db and should_close:
                db.rollback()
                db.close()
            return False
    
    def get_all_positions(self, db: Session = None) -> List[Dict]:
        """
        Get all current open positions
        
        Returns:
            List of position dictionaries
        """
        try:
            should_close = False
            if db is None:
                db = next(get_db())
                should_close = True
            
            try:
                positions = db.query(Position).order_by(Position.entry_time).all()
                return [pos.to_dict() for pos in positions]
            finally:
                if should_close:
                    db.close()
        
        except Exception as e:
            self.logger.error(f"Error getting positions: {e}")
            if db and should_close:
                db.close()
            return []
    
    async def get_all_open_positions(self, db: Session = None) -> List[Dict]:
        """
        Alias for get_all_positions to maintain compatibility
        
        Returns:
            List of position dictionaries
        """
        return self.get_all_positions(db)
    
    def get_position_by_id(self, position_id: str, db: Session = None) -> Optional[Dict]:
        """
        Get a specific position by ID
        
        Args:
            position_id: Position identifier
            db: Database session (optional)
        
        Returns:
            Position dictionary or None
        """
        try:
            should_close = False
            if db is None:
                db = next(get_db())
                should_close = True
            
            try:
                position = db.query(Position).filter(
                    Position.position_id == position_id
                ).first()
                
                return position.to_dict() if position else None
            finally:
                if should_close:
                    db.close()
        
        except Exception as e:
            self.logger.error(f"Error getting position: {e}")
            if db and should_close:
                db.close()
            return None


# Singleton instance
_position_service = None

def get_position_service() -> PositionPersistenceService:
    """Get singleton instance of position persistence service"""
    global _position_service
    if _position_service is None:
        _position_service = PositionPersistenceService()
    return _position_service
