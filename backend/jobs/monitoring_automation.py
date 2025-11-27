"""
Monitoring Automation
Daily performance review and automated alerts
"""

import asyncio
from datetime import datetime, time as dt_time
from typing import Dict, Optional
from backend.core.logger import get_logger
from backend.database.database import get_db
from backend.database.models import Trade, DailyPerformance
from sqlalchemy import func

logger = get_logger(__name__)


class MonitoringAutomation:
    """
    Automated monitoring and alerting system
    
    Features:
    - Daily performance review
    - Strategy health checks
    - Risk metric monitoring
    - Automated alerts on anomalies
    """
    
    def __init__(self, review_time: dt_time = dt_time(17, 0)):
        self.review_time = review_time
        self.is_running = False
        self.last_review = None
    
    async def start(self):
        """Start monitoring automation scheduler"""
        self.is_running = True
        logger.info(f"✓ Monitoring automation started (daily review at {self.review_time})")
        
        while self.is_running:
            try:
                await self._check_and_run_review()
                await asyncio.sleep(300)  # Check every 5 minutes
            except Exception as e:
                logger.error(f"Error in monitoring automation loop: {e}")
                await asyncio.sleep(60)
    
    async def _check_and_run_review(self):
        """Check if it's time to run daily review"""
        now = datetime.now()
        
        # Check if it's time for review
        if now.time() >= self.review_time:
            # Check if already reviewed today
            if self.last_review and self.last_review.date() == now.date():
                return
            
            logger.info("=" * 60)
            logger.info("📊 Starting daily performance review")
            logger.info("=" * 60)
            
            await self.run_daily_review()
            self.last_review = now
    
    async def run_daily_review(self):
        """Run comprehensive daily performance review"""
        try:
            today = datetime.now().date()
            
            # Get today's trades
            db = next(get_db())
            
            trades = db.query(Trade).filter(
                func.date(Trade.entry_time) == today,
                Trade.status == 'CLOSED'
            ).all()
            
            if not trades:
                logger.info("No trades closed today")
                db.close()
                return
            
            # Calculate daily metrics
            total_trades = len(trades)
            winning_trades = sum(1 for t in trades if t.is_winning_trade)
            losing_trades = total_trades - winning_trades
            
            total_pnl = sum(t.net_pnl or 0 for t in trades)
            total_profit = sum(t.net_pnl for t in trades if t.net_pnl and t.net_pnl > 0)
            total_loss = abs(sum(t.net_pnl for t in trades if t.net_pnl and t.net_pnl < 0))
            
            win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
            profit_factor = (total_profit / total_loss) if total_loss > 0 else 0
            
            avg_win = (total_profit / winning_trades) if winning_trades > 0 else 0
            avg_loss = (total_loss / losing_trades) if losing_trades > 0 else 0
            
            # Strategy breakdown
            strategy_stats = {}
            for trade in trades:
                strategy = trade.strategy_name
                if strategy not in strategy_stats:
                    strategy_stats[strategy] = {
                        'trades': 0,
                        'wins': 0,
                        'pnl': 0.0
                    }
                strategy_stats[strategy]['trades'] += 1
                if trade.is_winning_trade:
                    strategy_stats[strategy]['wins'] += 1
                strategy_stats[strategy]['pnl'] += trade.net_pnl or 0
            
            # Log review
            logger.info(f"\n📊 Daily Performance Review - {today}")
            logger.info("=" * 60)
            logger.info(f"Total Trades: {total_trades}")
            logger.info(f"Win Rate: {win_rate:.1f}% ({winning_trades}W / {losing_trades}L)")
            logger.info(f"Net P&L: ₹{total_pnl:,.2f}")
            logger.info(f"Profit Factor: {profit_factor:.2f}")
            logger.info(f"Avg Win: ₹{avg_win:,.2f} | Avg Loss: ₹{avg_loss:,.2f}")
            logger.info("")
            logger.info("Strategy Breakdown:")
            for strategy, stats in strategy_stats.items():
                strategy_wr = (stats['wins'] / stats['trades'] * 100) if stats['trades'] > 0 else 0
                logger.info(
                    f"  {strategy}: {stats['trades']} trades, "
                    f"{strategy_wr:.1f}% WR, ₹{stats['pnl']:,.2f}"
                )
            logger.info("=" * 60)
            
            # Check for anomalies and alerts
            await self._check_anomalies(
                win_rate=win_rate,
                total_pnl=total_pnl,
                profit_factor=profit_factor,
                strategy_stats=strategy_stats
            )
            
            db.close()
            
        except Exception as e:
            logger.error(f"Error in daily review: {e}")
    
    async def _check_anomalies(
        self,
        win_rate: float,
        total_pnl: float,
        profit_factor: float,
        strategy_stats: Dict
    ):
        """Check for anomalies and trigger alerts"""
        alerts = []
        
        # Check win rate
        if win_rate < 40:
            alerts.append(f"⚠️  Low win rate: {win_rate:.1f}% (target: >50%)")
        
        # Check profit factor
        if profit_factor < 1.0:
            alerts.append(f"⚠️  Profit factor below 1.0: {profit_factor:.2f}")
        
        # Check daily P&L
        if total_pnl < 0:
            alerts.append(f"⚠️  Negative daily P&L: ₹{total_pnl:,.2f}")
        
        # Check strategy performance
        for strategy, stats in strategy_stats.items():
            if stats['trades'] >= 3:  # Minimum trades for assessment
                strategy_wr = (stats['wins'] / stats['trades'] * 100)
                if strategy_wr < 30:
                    alerts.append(
                        f"⚠️  Strategy '{strategy}' underperforming: "
                        f"{strategy_wr:.1f}% WR, ₹{stats['pnl']:,.2f}"
                    )
        
        # Log alerts
        if alerts:
            logger.warning("\n🚨 Performance Alerts:")
            for alert in alerts:
                logger.warning(f"  {alert}")
        else:
            logger.info("✓ No performance anomalies detected")
    
    def stop(self):
        """Stop monitoring automation"""
        self.is_running = False
        logger.info("Monitoring automation stopped")


# Singleton instance
_monitoring_automation = None


def get_monitoring_automation() -> MonitoringAutomation:
    """Get singleton monitoring automation instance"""
    global _monitoring_automation
    if _monitoring_automation is None:
        _monitoring_automation = MonitoringAutomation()
    return _monitoring_automation
