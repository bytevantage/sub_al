"""
Option Chain Persistence Service
Stores historical option chain snapshots with Greeks for ML training
STORAGE: All timestamps stored in UTC (raw)
"""

from datetime import datetime, timedelta
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_

# Import timezone utilities for consistent time handling
from backend.core.timezone_utils import now_utc, to_ist, to_utc

from backend.core.logger import get_logger
from backend.database.database import get_db
from backend.database.models import OptionSnapshot

logger = get_logger(__name__)


class OptionChainPersistenceService:
    """Service for persisting option chain snapshots"""
    
    def __init__(self):
        self.logger = logger
        self._last_save_time = {}  # Track last save per symbol to avoid duplicates
    
    def should_save_snapshot(self, symbol: str, interval_seconds: int = 60) -> bool:
        """
        Check if enough time has passed since last snapshot
        
        Args:
            symbol: NIFTY, SENSEX, etc.
            interval_seconds: Minimum seconds between snapshots (default: 60)
        
        Returns:
            True if should save new snapshot
        """
        now = now_utc()  # Use UTC for consistent comparison
        last_save = self._last_save_time.get(symbol)
        
        if not last_save:
            return True
        
        return (now - last_save).seconds >= interval_seconds
    
    def save_option_chain_snapshot(self, symbol: str, option_chain: Dict, spot_price: float, db: Session = None) -> bool:
        """
        Save option chain snapshot to database for ML training
        
        Args:
            symbol: NIFTY, SENSEX, etc.
            option_chain: Option chain dict with calls/puts
            spot_price: Current spot price
            db: Database session (optional)
        
        Returns:
            True if saved successfully
        """
        try:
            # Check if should save (rate limiting)
            if not self.should_save_snapshot(symbol, interval_seconds=60):
                return False
            
            should_close = False
            if db is None:
                db = next(get_db())
                should_close = True
            
            try:
                from backend.core.timezone_utils import now_ist
                timestamp = now_utc()  # Store in UTC
                saved_count = 0
                
                # Save call options
                for strike_str, call_data in option_chain.get('calls', {}).items():
                    strike_price = float(strike_str)
                    
                    snapshot = OptionSnapshot(
                        timestamp=timestamp,
                        symbol=symbol,
                        strike_price=strike_price,
                        option_type='CALL',
                        expiry=call_data.get('expiry_date') or (datetime.now() + timedelta(days=7)),
                        ltp=call_data.get('ltp', 0),
                        bid=call_data.get('bid', 0),
                        ask=call_data.get('ask', 0),
                        volume=call_data.get('volume', 0),
                        oi=call_data.get('oi', 0),
                        oi_change=call_data.get('oi_change', 0),
                        delta=call_data.get('delta', 0),
                        gamma=call_data.get('gamma', 0),
                        theta=call_data.get('theta', 0),
                        vega=call_data.get('vega', 0),
                        iv=call_data.get('iv', 0),
                        spot_price=spot_price
                    )
                    db.add(snapshot)
                    saved_count += 1
                
                # Save put options
                for strike_str, put_data in option_chain.get('puts', {}).items():
                    strike_price = float(strike_str)
                    
                    snapshot = OptionSnapshot(
                        timestamp=timestamp,
                        symbol=symbol,
                        strike_price=strike_price,
                        option_type='PUT',
                        expiry=put_data.get('expiry_date') or (datetime.now() + timedelta(days=7)),
                        ltp=put_data.get('ltp', 0),
                        bid=put_data.get('bid', 0),
                        ask=put_data.get('ask', 0),
                        volume=put_data.get('volume', 0),
                        oi=put_data.get('oi', 0),
                        oi_change=put_data.get('oi_change', 0),
                        delta=put_data.get('delta', 0),
                        gamma=put_data.get('gamma', 0),
                        theta=put_data.get('theta', 0),
                        vega=put_data.get('vega', 0),
                        iv=put_data.get('iv', 0),
                        spot_price=spot_price
                    )
                    db.add(snapshot)
                    saved_count += 1
                
                db.commit()
                self._last_save_time[symbol] = timestamp  # Store in UTC
                self.logger.info(f"✓ Saved {saved_count} option chain entries for {symbol}")
                return True
                
            finally:
                if should_close:
                    db.close()
        
        except Exception as e:
            self.logger.error(f"Error saving option chain snapshot: {e}")
            if db and should_close:
                db.rollback()
                db.close()
            return False
    
    def get_historical_snapshots(self, symbol: str, strike: float, option_type: str, 
                                  hours_back: int = 24, db: Session = None) -> List[Dict]:
        """
        Get historical option chain snapshots for ML training
        
        Args:
            symbol: NIFTY, SENSEX, etc.
            strike: Strike price
            option_type: CALL or PUT
            hours_back: How many hours of history to fetch
            db: Database session (optional)
        
        Returns:
            List of snapshot dictionaries
        """
        try:
            should_close = False
            if db is None:
                db = next(get_db())
                should_close = True
            
            try:
                from backend.core.timezone_utils import now_ist
                cutoff_time = now_utc() - timedelta(hours=hours_back)
                
                snapshots = db.query(OptionSnapshot).filter(
                    and_(
                        OptionSnapshot.symbol == symbol,
                        OptionSnapshot.strike_price == strike,
                        OptionSnapshot.option_type == option_type,
                        OptionSnapshot.timestamp >= cutoff_time
                    )
                ).order_by(OptionSnapshot.timestamp.desc()).all()
                
                return [{
                    'timestamp': s.timestamp,
                    'ltp': s.ltp,
                    'delta': s.delta,
                    'gamma': s.gamma,
                    'theta': s.theta,
                    'vega': s.vega,
                    'iv': s.iv,
                    'oi': s.oi,
                    'oi_change': s.oi_change,
                    'volume': s.volume,
                    'spot_price': s.spot_price
                } for s in snapshots]
                
            finally:
                if should_close:
                    db.close()
        
        except Exception as e:
            self.logger.error(f"Error fetching historical snapshots: {e}")
            if db and should_close:
                db.close()
            return []
    
    def get_snapshot_at_time(self, symbol: str, strike: float, option_type: str, 
                             target_time: datetime, tolerance_minutes: int = 5, 
                             db: Session = None) -> Optional[Dict]:
        """
        Get option chain snapshot closest to a specific time
        Useful for correlating with trade entry/exit times
        
        Args:
            symbol: NIFTY, SENSEX, etc.
            strike: Strike price
            option_type: CALL or PUT
            target_time: The time to search near
            tolerance_minutes: How many minutes before/after to search
            db: Database session (optional)
        
        Returns:
            Snapshot dictionary or None
        """
        try:
            should_close = False
            if db is None:
                db = next(get_db())
                should_close = True
            
            try:
                time_min = target_time - timedelta(minutes=tolerance_minutes)
                time_max = target_time + timedelta(minutes=tolerance_minutes)
                
                snapshot = db.query(OptionSnapshot).filter(
                    and_(
                        OptionSnapshot.symbol == symbol,
                        OptionSnapshot.strike_price == strike,
                        OptionSnapshot.option_type == option_type,
                        OptionSnapshot.timestamp >= time_min,
                        OptionSnapshot.timestamp <= time_max
                    )
                ).order_by(
                    # Get closest to target time
                    OptionSnapshot.timestamp.desc()
                ).first()
                
                if snapshot:
                    return {
                        'timestamp': snapshot.timestamp,
                        'ltp': snapshot.ltp,
                        'delta': snapshot.delta,
                        'gamma': snapshot.gamma,
                        'theta': snapshot.theta,
                        'vega': snapshot.vega,
                        'iv': snapshot.iv,
                        'oi': snapshot.oi,
                        'oi_change': snapshot.oi_change,
                        'volume': snapshot.volume,
                        'spot_price': snapshot.spot_price
                    }
                return None
                
            finally:
                if should_close:
                    db.close()
        
        except Exception as e:
            self.logger.error(f"Error fetching snapshot at time: {e}")
            if db and should_close:
                db.close()
            return None
    
    def cleanup_old_snapshots(self, days_to_keep: int = 30, db: Session = None) -> int:
        """
        Clean up old option chain snapshots
        
        Args:
            days_to_keep: Number of days of data to retain
            db: Database session (optional)
        
        Returns:
            Number of records deleted
        """
        try:
            should_close = False
            if db is None:
                db = next(get_db())
                should_close = True
            
            try:
                from backend.core.timezone_utils import now_ist
                cutoff_date = now_utc() - timedelta(days=days_to_keep)
                
                deleted = db.query(OptionSnapshot).filter(
                    OptionSnapshot.timestamp < cutoff_date
                ).delete()
                
                db.commit()
                self.logger.info(f"✓ Cleaned up {deleted} old option chain snapshots (kept last {days_to_keep} days)")
                return deleted
                
            finally:
                if should_close:
                    db.close()
        
        except Exception as e:
            self.logger.error(f"Error cleaning up snapshots: {e}")
            if db and should_close:
                db.rollback()
                db.close()
            return 0
