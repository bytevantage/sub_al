"""
Trade Reconciliation Job

Background job to reconcile local trades with broker statements.
Identifies discrepancies in trades, P&L, and executions.
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
import asyncio
import logging
from collections import defaultdict

from backend.database.database import db
from backend.database.models import Trade
from backend.core.upstox_client import UpstoxClient

logger = logging.getLogger(__name__)


class TradeReconciliationJob:
    """
    Reconciles local trade records with broker statements.
    
    Checks for:
    - Missing trades (broker has, we don't)
    - Extra trades (we have, broker doesn't)
    - P&L discrepancies
    - Price discrepancies
    """
    
    def __init__(self, upstox_client: UpstoxClient):
        self.upstox_client = upstox_client
        self.last_reconciliation = None
        self.discrepancies = []
        self.reconciliation_stats = {
            'total_broker_trades': 0,
            'total_local_trades': 0,
            'matched_trades': 0,
            'missing_trades': 0,
            'extra_trades': 0,
            'pnl_discrepancies': 0,
            'price_discrepancies': 0
        }
    
    async def run_reconciliation(self, date: datetime = None) -> Dict:
        """
        Run reconciliation for a specific date.
        
        Args:
            date: Date to reconcile (default: yesterday)
        
        Returns:
            Reconciliation report
        """
        if date is None:
            # Default to yesterday
            date = datetime.now() - timedelta(days=1)
        
        logger.info(f"Starting trade reconciliation for {date.date()}")
        
        try:
            # Fetch broker trades
            broker_trades = await self.fetch_broker_trades(date)
            if broker_trades is None:
                logger.error("Failed to fetch broker trades")
                return {'error': 'Failed to fetch broker trades'}
            
            # Fetch local trades
            local_trades = self.fetch_local_trades(date)
            
            # Compare trades
            report = self.compare_trades(broker_trades, local_trades, date)
            
            # Update stats
            self.last_reconciliation = datetime.now()
            
            logger.info(
                f"Reconciliation complete: {report['matched_trades']} matched, "
                f"{report['discrepancies_found']} discrepancies"
            )
            
            return report
            
        except Exception as e:
            logger.error(f"Error during reconciliation: {e}")
            return {'error': str(e)}
    
    async def fetch_broker_trades(self, date: datetime) -> Optional[List[Dict]]:
        """
        Fetch trades from broker for a specific date.
        
        Args:
            date: Date to fetch trades for
        
        Returns:
            List of broker trade dictionaries
        """
        try:
            # Upstox API: Get trade history
            # Note: Actual API endpoint may vary - this is a placeholder
            from_date = date.strftime('%Y-%m-%d')
            to_date = date.strftime('%Y-%m-%d')
            
            # Try to fetch trade book
            trades = await self._fetch_upstox_tradebook(from_date, to_date)
            
            if trades is None:
                logger.warning(f"No broker trades found for {date.date()}")
                return []
            
            return trades
            
        except Exception as e:
            logger.error(f"Error fetching broker trades: {e}")
            return None
    
    async def _fetch_upstox_tradebook(self, from_date: str, to_date: str) -> Optional[List[Dict]]:
        """
        Fetch tradebook from Upstox API.
        
        Note: This uses a hypothetical API endpoint. Actual implementation
        depends on Upstox API documentation.
        """
        try:
            # Placeholder - actual API call would be:
            # response = await self.upstox_client.get_tradebook(from_date, to_date)
            
            # For now, return empty list (implement when API is available)
            logger.warning("Broker trade fetching not yet implemented - requires Upstox API integration")
            return []
            
        except Exception as e:
            logger.error(f"Error calling Upstox tradebook API: {e}")
            return None
    
    def fetch_local_trades(self, date: datetime) -> List[Trade]:
        """
        Fetch trades from local database for a specific date.
        
        Args:
            date: Date to fetch trades for
        
        Returns:
            List of Trade model objects
        """
        try:
            session = db.get_session()
            if not session:
                logger.error("Database session not available")
                return []
            
            # Query trades for the date
            start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = date.replace(hour=23, minute=59, second=59, microsecond=999999)
            
            trades = session.query(Trade).filter(
                Trade.entry_time >= start_of_day,
                Trade.entry_time <= end_of_day
            ).all()
            
            session.close()
            
            logger.info(f"Found {len(trades)} local trades for {date.date()}")
            return trades
            
        except Exception as e:
            logger.error(f"Error fetching local trades: {e}")
            return []
    
    def compare_trades(
        self, 
        broker_trades: List[Dict], 
        local_trades: List[Trade],
        date: datetime
    ) -> Dict:
        """
        Compare broker trades with local trades.
        
        Args:
            broker_trades: Trades from broker
            local_trades: Trades from database
            date: Reconciliation date
        
        Returns:
            Reconciliation report
        """
        discrepancies = []
        matched_count = 0
        
        # Create lookups for efficient matching
        broker_by_id = {t.get('trade_id'): t for t in broker_trades}
        local_by_id = {t.trade_id: t for t in local_trades}
        
        # Check for missing trades (in broker, not in local)
        missing_trades = []
        for trade_id, broker_trade in broker_by_id.items():
            if trade_id not in local_by_id:
                missing_trades.append({
                    'trade_id': trade_id,
                    'type': 'missing_local',
                    'broker_data': broker_trade
                })
        
        # Check for extra trades (in local, not in broker)
        extra_trades = []
        for trade_id, local_trade in local_by_id.items():
            if trade_id not in broker_by_id:
                extra_trades.append({
                    'trade_id': trade_id,
                    'type': 'extra_local',
                    'local_data': self._trade_to_dict(local_trade)
                })
        
        # Check for P&L and price discrepancies in matched trades
        pnl_discrepancies = []
        price_discrepancies = []
        
        for trade_id in set(broker_by_id.keys()) & set(local_by_id.keys()):
            broker_trade = broker_by_id[trade_id]
            local_trade = local_by_id[trade_id]
            matched_count += 1
            
            # Check P&L discrepancy (tolerance: ₹1)
            broker_pnl = broker_trade.get('pnl', 0)
            local_pnl = local_trade.net_pnl
            
            if abs(broker_pnl - local_pnl) > 1.0:
                pnl_discrepancies.append({
                    'trade_id': trade_id,
                    'type': 'pnl_mismatch',
                    'broker_pnl': broker_pnl,
                    'local_pnl': local_pnl,
                    'difference': broker_pnl - local_pnl
                })
            
            # Check price discrepancies (tolerance: 0.5%)
            broker_entry = broker_trade.get('entry_price', 0)
            local_entry = local_trade.entry_price
            
            if broker_entry > 0:
                price_diff_pct = abs((broker_entry - local_entry) / broker_entry * 100)
                if price_diff_pct > 0.5:
                    price_discrepancies.append({
                        'trade_id': trade_id,
                        'type': 'price_mismatch',
                        'broker_entry': broker_entry,
                        'local_entry': local_entry,
                        'diff_pct': round(price_diff_pct, 2)
                    })
        
        # Combine all discrepancies
        all_discrepancies = missing_trades + extra_trades + pnl_discrepancies + price_discrepancies
        
        # Update stats
        self.reconciliation_stats = {
            'total_broker_trades': len(broker_trades),
            'total_local_trades': len(local_trades),
            'matched_trades': matched_count,
            'missing_trades': len(missing_trades),
            'extra_trades': len(extra_trades),
            'pnl_discrepancies': len(pnl_discrepancies),
            'price_discrepancies': len(price_discrepancies)
        }
        
        self.discrepancies = all_discrepancies
        
        # Build report
        report = {
            'date': date.date().isoformat(),
            'reconciliation_time': datetime.now().isoformat(),
            'summary': self.reconciliation_stats,
            'discrepancies_found': len(all_discrepancies),
            'discrepancies': all_discrepancies[:100],  # Limit to first 100
            'status': 'clean' if len(all_discrepancies) == 0 else 'discrepancies_found'
        }
        
        return report
    
    def _trade_to_dict(self, trade: Trade) -> Dict:
        """Convert Trade model to dictionary"""
        return {
            'trade_id': trade.trade_id,
            'symbol': trade.symbol,
            'entry_price': trade.entry_price,
            'exit_price': trade.exit_price,
            'quantity': trade.quantity,
            'pnl': trade.net_pnl,
            'entry_time': trade.entry_time.isoformat() if trade.entry_time else None,
            'exit_time': trade.exit_time.isoformat() if trade.exit_time else None
        }
    
    def get_latest_report(self) -> Dict:
        """Get the most recent reconciliation report"""
        if not self.last_reconciliation:
            return {'status': 'no_reconciliation_run'}
        
        return {
            'last_run': self.last_reconciliation.isoformat(),
            'stats': self.reconciliation_stats,
            'discrepancies_count': len(self.discrepancies)
        }
    
    async def schedule_daily_reconciliation(self, run_time: str = "18:00"):
        """
        Schedule daily reconciliation at a specific time.
        
        Args:
            run_time: Time to run (HH:MM format, default: 18:00)
        """
        logger.info(f"Daily reconciliation scheduled for {run_time}")
        
        while True:
            try:
                now = datetime.now()
                target_hour, target_minute = map(int, run_time.split(':'))
                
                # Calculate next run time
                next_run = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
                if next_run <= now:
                    next_run += timedelta(days=1)
                
                # Wait until next run
                sleep_seconds = (next_run - now).total_seconds()
                logger.info(f"Next reconciliation in {sleep_seconds/3600:.1f} hours")
                await asyncio.sleep(sleep_seconds)
                
                # Run reconciliation for yesterday
                await self.run_reconciliation()
                
            except Exception as e:
                logger.error(f"Error in scheduled reconciliation: {e}")
                await asyncio.sleep(3600)  # Wait 1 hour on error
