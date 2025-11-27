"""
Entry Timing Module - Wait for optimal entry points (pullbacks/bounces)
"""

from typing import Dict, Optional, List
from datetime import datetime, timedelta
from backend.core.logger import get_logger

logger = get_logger(__name__)


class EntryTimingManager:
    """
    Manages entry timing for signals - waits for pullbacks/bounces
    before entering positions
    """
    
    def __init__(self):
        self.pending_signals = []  # Signals waiting for better entry
        self.signal_timeouts = {}  # Track when signals expire
        self.max_wait_time = 120  # Max 2 minutes to wait for pullback
        
    def should_enter_now(self, signal: Dict, market_data: Dict) -> tuple[bool, str]:
        """
        OFFICIAL SPEC: ENTER IMMEDIATELY
        NO waiting, NO filters, NO timing checks
        
        Args:
            signal: Trading signal
            market_data: Current market state (ignored)
            
        Returns:
            (True, "ENTER IMMEDIATELY") - Always enter immediately
        """
        return True, "ENTER IMMEDIATELY - OFFICIAL SPEC"
    
    def add_pending_signal(self, signal: Dict):
        """DISABLED - No pending queue per official spec"""
        pass
    
    def check_pending_signals(self, market_data: Dict) -> List[Dict]:
        """DISABLED - No pending queue per official spec"""
        return []
    
    def clear_pending_signals(self):
        """Clear all pending signals"""
        self.pending_signals = []
        self.signal_timeouts = {}
        logger.info("Cleared all pending signals")
