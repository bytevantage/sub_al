"""
Data Quality Monitor
Automated checks for trade data completeness and ML training readiness
Runs daily after market close to verify data integrity
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List
from sqlalchemy import func

from backend.core.logger import get_logger
from backend.database.database import db
from backend.database.models import Trade
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = get_logger(__name__)


class DataQualityMonitor:
    """Monitor and alert on data quality issues"""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.is_running = False
        self.quality_threshold = 95.0  # Minimum % for data quality
        self.last_check_time = None
        self.issues_found = []
        
    async def start(self):
        """Start the data quality monitor"""
        try:
            # Schedule for 3:45 PM daily (after market close at 3:30)
            self.scheduler.add_job(
                self.run_quality_check,
                'cron',
                day_of_week='mon-fri',
                hour=15,
                minute=45,
                id='data_quality_check'
            )
            
            self.scheduler.start()
            self.is_running = True
            logger.info("✓ Data quality monitor started - scheduled for 3:45 PM daily")
            
        except Exception as e:
            logger.error(f"Error starting data quality monitor: {e}")
    
    async def stop(self):
        """Stop the data quality monitor"""
        try:
            if self.scheduler.running:
                self.scheduler.shutdown()
                self.is_running = False
                logger.info("Data quality monitor stopped")
        except Exception as e:
            logger.error(f"Error stopping data quality monitor: {e}")
    
    async def run_quality_check(self):
        """Execute comprehensive data quality check"""
        try:
            logger.info("=" * 70)
            logger.info("=== DATA QUALITY CHECK ===")
            logger.info("=" * 70)
            
            self.last_check_time = datetime.now()
            self.issues_found = []
            
            # Get today's closed trades
            today = datetime.now().date()
            start_of_day = datetime.combine(today, datetime.min.time())
            
            with db.get_session() as session:
                trades_today = session.query(Trade).filter(
                    Trade.entry_time >= start_of_day,
                    Trade.status == 'CLOSED'
                ).all()
                
                if not trades_today:
                    logger.warning("⚠️  No closed trades found for today")
                    return
                
                total_trades = len(trades_today)
                logger.info(f"Checking {total_trades} trades from today")
                
                # Check 1: Entry Greeks Completeness
                self._check_entry_greeks(trades_today, total_trades)
                
                # Check 2: Exit Greeks Completeness
                self._check_exit_greeks(trades_today, total_trades)
                
                # Check 3: ML Metadata Completeness
                self._check_ml_metadata(trades_today, total_trades)
                
                # Check 4: Market Context Completeness
                self._check_market_context(trades_today, total_trades)
                
                # Check 5: Option Chain Data
                self._check_option_chain_data(trades_today, total_trades)
                
                # Summary
                if not self.issues_found:
                    logger.info("\n✅ All data quality checks PASSED!")
                else:
                    logger.warning(f"\n⚠️  Found {len(self.issues_found)} data quality issues:")
                    for issue in self.issues_found:
                        logger.warning(f"  - {issue}")
                
                logger.info("=" * 70)
                
        except Exception as e:
            logger.error(f"Error in data quality check: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def _check_entry_greeks(self, trades: List[Trade], total: int):
        """Check completeness of entry Greeks"""
        missing_delta = sum(1 for t in trades if t.delta_entry is None or t.delta_entry == 0)
        missing_gamma = sum(1 for t in trades if t.gamma_entry is None or t.gamma_entry == 0)
        missing_theta = sum(1 for t in trades if t.theta_entry is None or t.theta_entry == 0)
        missing_vega = sum(1 for t in trades if t.vega_entry is None or t.vega_entry == 0)
        
        coverage = ((total - max(missing_delta, missing_gamma, missing_theta, missing_vega)) / total * 100)
        
        logger.info(f"\n1. Entry Greeks Coverage: {coverage:.1f}%")
        logger.info(f"   Delta: {total - missing_delta}/{total}")
        logger.info(f"   Gamma: {total - missing_gamma}/{total}")
        logger.info(f"   Theta: {total - missing_theta}/{total}")
        logger.info(f"   Vega: {total - missing_vega}/{total}")
        
        if coverage < self.quality_threshold:
            issue = f"Entry Greeks coverage ({coverage:.1f}%) below threshold ({self.quality_threshold}%)"
            self.issues_found.append(issue)
            logger.error(f"   ❌ {issue}")
        else:
            logger.info(f"   ✅ PASS")
    
    def _check_exit_greeks(self, trades: List[Trade], total: int):
        """Check completeness of exit Greeks"""
        missing_delta = sum(1 for t in trades if t.delta_exit is None)
        missing_gamma = sum(1 for t in trades if t.gamma_exit is None)
        missing_theta = sum(1 for t in trades if t.theta_exit is None)
        missing_vega = sum(1 for t in trades if t.vega_exit is None)
        
        coverage = ((total - max(missing_delta, missing_gamma, missing_theta, missing_vega)) / total * 100) if total > 0 else 0
        
        logger.info(f"\n2. Exit Greeks Coverage: {coverage:.1f}%")
        logger.info(f"   Delta: {total - missing_delta}/{total}")
        logger.info(f"   Gamma: {total - missing_gamma}/{total}")
        logger.info(f"   Theta: {total - missing_theta}/{total}")
        logger.info(f"   Vega: {total - missing_vega}/{total}")
        
        if coverage < self.quality_threshold:
            issue = f"Exit Greeks coverage ({coverage:.1f}%) below threshold ({self.quality_threshold}%)"
            self.issues_found.append(issue)
            logger.error(f"   ❌ {issue}")
        else:
            logger.info(f"   ✅ PASS")
    
    def _check_ml_metadata(self, trades: List[Trade], total: int):
        """Check ML metadata completeness"""
        missing_ml_score = sum(1 for t in trades if t.ml_score is None)
        missing_model_version = sum(1 for t in trades if t.model_version is None)
        missing_features = sum(1 for t in trades if t.features_snapshot is None or not t.features_snapshot)
        
        ml_score_coverage = ((total - missing_ml_score) / total * 100) if total > 0 else 0
        model_version_coverage = ((total - missing_model_version) / total * 100) if total > 0 else 0
        features_coverage = ((total - missing_features) / total * 100) if total > 0 else 0
        
        logger.info(f"\n3. ML Metadata Coverage:")
        logger.info(f"   ML Score: {ml_score_coverage:.1f}% ({total - missing_ml_score}/{total})")
        logger.info(f"   Model Version: {model_version_coverage:.1f}% ({total - missing_model_version}/{total})")
        logger.info(f"   Feature Snapshot: {features_coverage:.1f}% ({total - missing_features}/{total})")
        
        if ml_score_coverage < self.quality_threshold:
            issue = f"ML Score coverage ({ml_score_coverage:.1f}%) below threshold"
            self.issues_found.append(issue)
            logger.error(f"   ❌ {issue}")
        else:
            logger.info(f"   ✅ PASS")
    
    def _check_market_context(self, trades: List[Trade], total: int):
        """Check market context data"""
        missing_spot_entry = sum(1 for t in trades if t.spot_price_entry is None or t.spot_price_entry == 0)
        missing_spot_exit = sum(1 for t in trades if t.spot_price_exit is None or t.spot_price_exit == 0)
        
        entry_coverage = ((total - missing_spot_entry) / total * 100) if total > 0 else 0
        exit_coverage = ((total - missing_spot_exit) / total * 100) if total > 0 else 0
        
        logger.info(f"\n4. Market Context Coverage:")
        logger.info(f"   Spot @ Entry: {entry_coverage:.1f}% ({total - missing_spot_entry}/{total})")
        logger.info(f"   Spot @ Exit: {exit_coverage:.1f}% ({total - missing_spot_exit}/{total})")
        
        if entry_coverage < self.quality_threshold or exit_coverage < self.quality_threshold:
            issue = f"Market context incomplete (Entry: {entry_coverage:.1f}%, Exit: {exit_coverage:.1f}%)"
            self.issues_found.append(issue)
            logger.error(f"   ❌ {issue}")
        else:
            logger.info(f"   ✅ PASS")
    
    def _check_option_chain_data(self, trades: List[Trade], total: int):
        """Check option chain data (OI, Volume)"""
        missing_oi_entry = sum(1 for t in trades if t.oi_entry is None or t.oi_entry == 0)
        missing_oi_exit = sum(1 for t in trades if t.oi_exit is None or t.oi_exit == 0)
        missing_vol_entry = sum(1 for t in trades if t.volume_entry is None or t.volume_entry == 0)
        missing_vol_exit = sum(1 for t in trades if t.volume_exit is None or t.volume_exit == 0)
        
        oi_entry_coverage = ((total - missing_oi_entry) / total * 100) if total > 0 else 0
        oi_exit_coverage = ((total - missing_oi_exit) / total * 100) if total > 0 else 0
        
        logger.info(f"\n5. Option Chain Data Coverage:")
        logger.info(f"   OI @ Entry: {oi_entry_coverage:.1f}% ({total - missing_oi_entry}/{total})")
        logger.info(f"   OI @ Exit: {oi_exit_coverage:.1f}% ({total - missing_oi_exit}/{total})")
        logger.info(f"   Volume @ Entry: {((total - missing_vol_entry) / total * 100):.1f}%")
        logger.info(f"   Volume @ Exit: {((total - missing_vol_exit) / total * 100):.1f}%")
        
        # OI is important for ML, warn if below threshold
        if oi_entry_coverage < 80:  # Lower threshold for OI (80% instead of 95%)
            issue = f"OI data coverage low (Entry: {oi_entry_coverage:.1f}%)"
            self.issues_found.append(issue)
            logger.warning(f"   ⚠️  {issue}")
        else:
            logger.info(f"   ✅ PASS")
    
    async def run_manual_check(self, lookback_days: int = 1):
        """Run manual data quality check"""
        logger.info(f"Running manual data quality check (last {lookback_days} days)")
        await self.run_quality_check()
    
    def get_status(self) -> Dict:
        """Get status of data quality monitor"""
        next_run = None
        if self.scheduler.running:
            job = self.scheduler.get_job('data_quality_check')
            if job and job.next_run_time:
                next_run = job.next_run_time.isoformat()
        
        return {
            'is_running': self.is_running,
            'last_check': self.last_check_time.isoformat() if self.last_check_time else None,
            'next_run': next_run,
            'issues_found': len(self.issues_found),
            'quality_threshold': self.quality_threshold,
            'issues': self.issues_found
        }


# Global instance
data_quality_monitor = DataQualityMonitor()


# Convenience function for testing
async def test_data_quality():
    """Test the data quality monitor"""
    monitor = DataQualityMonitor()
    await monitor.run_quality_check()


if __name__ == "__main__":
    asyncio.run(test_data_quality())
