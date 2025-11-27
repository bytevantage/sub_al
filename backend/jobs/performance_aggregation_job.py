"""
Performance Aggregation Job
End-of-day batch job to compute DailyPerformance and StrategyPerformance from trades
"""

import asyncio
from datetime import datetime, timedelta, time
from typing import Dict, List
from sqlalchemy import func
from backend.core.logger import get_execution_logger
from backend.database.database import db
from backend.database.models import Trade, DailyPerformance, StrategyPerformance
from backend.strategies.strategy_mappings import normalize_strategy_name

logger = get_execution_logger()


class PerformanceAggregationJob:
    """
    Aggregates trade data into DailyPerformance and StrategyPerformance tables
    Runs at end of day to compute daily/strategy summaries
    """
    
    def __init__(self):
        self.last_run_date = None
    
    async def run_aggregation(self, target_date: datetime = None):
        """
        Run performance aggregation for a specific date
        
        Args:
            target_date: Date to aggregate (defaults to today)
        """
        if target_date is None:
            target_date = datetime.now()
        
        date_str = target_date.strftime('%Y-%m-%d')
        logger.info(f"Starting performance aggregation for {date_str}")
        
        try:
            # Aggregate daily performance
            await self._aggregate_daily_performance(target_date)
            
            # Aggregate strategy performance
            await self._aggregate_strategy_performance(target_date)
            
            self.last_run_date = target_date
            logger.info(f"Performance aggregation completed for {date_str}")
            
        except Exception as e:
            logger.error(f"Performance aggregation failed for {date_str}: {e}", exc_info=True)
    
    async def _aggregate_daily_performance(self, target_date: datetime):
        """
        Aggregate daily performance from trades
        
        Computes:
        - Total P&L (gross and net)
        - Win rate
        - Profit factor
        - Average trade metrics
        - Max drawdown
        """
        session = db.get_session()
        if not session:
            logger.error("Failed to get database session for daily aggregation")
            return
        
        try:
            # Get date range (start to end of day)
            start_of_day = datetime.combine(target_date.date(), time.min)
            end_of_day = datetime.combine(target_date.date(), time.max)
            
            # Query all closed trades for the day
            trades = session.query(Trade).filter(
                Trade.entry_time >= start_of_day,
                Trade.entry_time <= end_of_day,
                Trade.status == 'CLOSED'
            ).all()
            
            if not trades:
                logger.info(f"No trades found for {target_date.strftime('%Y-%m-%d')}")
                session.close()
                return
            
            # Calculate aggregates
            total_trades = len(trades)
            winning_trades = sum(1 for t in trades if t.is_winning_trade)
            losing_trades = total_trades - winning_trades
            
            total_gross_pnl = sum(t.gross_pnl or 0 for t in trades)
            total_net_pnl = sum(t.net_pnl or 0 for t in trades)
            total_brokerage = sum(t.brokerage or 0 for t in trades)
            total_taxes = sum(t.taxes or 0 for t in trades)
            
            gross_profit = sum(t.gross_pnl or 0 for t in trades if (t.gross_pnl or 0) > 0)
            gross_loss = abs(sum(t.gross_pnl or 0 for t in trades if (t.gross_pnl or 0) < 0))
            
            net_profit = sum(t.net_pnl or 0 for t in trades if (t.net_pnl or 0) > 0)
            net_loss = abs(sum(t.net_pnl or 0 for t in trades if (t.net_pnl or 0) < 0))
            
            # Win rate
            win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0
            
            # Profit factor
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else (float('inf') if gross_profit > 0 else 0)
            
            # Average metrics
            avg_trade_pnl = total_net_pnl / total_trades if total_trades > 0 else 0
            avg_winning_trade = (net_profit / winning_trades) if winning_trades > 0 else 0
            avg_losing_trade = (net_loss / losing_trades) if losing_trades > 0 else 0
            avg_hold_duration = sum(t.hold_duration_minutes or 0 for t in trades) / total_trades if total_trades > 0 else 0
            
            # Max drawdown (simplified - based on cumulative P&L)
            cumulative_pnl = []
            running_pnl = 0
            for trade in sorted(trades, key=lambda t: t.entry_time):
                running_pnl += trade.net_pnl or 0
                cumulative_pnl.append(running_pnl)
            
            max_drawdown_amount = 0
            max_drawdown_pct = 0
            if cumulative_pnl:
                peak = cumulative_pnl[0]
                for pnl in cumulative_pnl:
                    if pnl > peak:
                        peak = pnl
                    drawdown = peak - pnl
                    if drawdown > max_drawdown_amount:
                        max_drawdown_amount = drawdown
                        if peak > 0:
                            max_drawdown_pct = (drawdown / peak) * 100
            
            # Check if record exists for this date
            existing = session.query(DailyPerformance).filter(
                DailyPerformance.trade_date == target_date.date()
            ).first()
            
            if existing:
                # Update existing record
                existing.total_trades = total_trades
                existing.winning_trades = winning_trades
                existing.losing_trades = losing_trades
                existing.win_rate = win_rate
                existing.total_gross_pnl = total_gross_pnl
                existing.total_net_pnl = total_net_pnl
                existing.total_brokerage = total_brokerage
                existing.total_taxes = total_taxes
                existing.profit_factor = profit_factor
                existing.avg_trade_pnl = avg_trade_pnl
                existing.avg_winning_trade = avg_winning_trade
                existing.avg_losing_trade = avg_losing_trade
                existing.avg_hold_duration_minutes = avg_hold_duration
                existing.max_drawdown_amount = max_drawdown_amount
                existing.max_drawdown_pct = max_drawdown_pct
                existing.updated_at = datetime.utcnow()
                
                logger.info(f"Updated daily performance for {target_date.strftime('%Y-%m-%d')}")
            else:
                # Create new record
                daily_perf = DailyPerformance(
                    trade_date=target_date.date(),
                    total_trades=total_trades,
                    winning_trades=winning_trades,
                    losing_trades=losing_trades,
                    win_rate=win_rate,
                    total_gross_pnl=total_gross_pnl,
                    total_net_pnl=total_net_pnl,
                    total_brokerage=total_brokerage,
                    total_taxes=total_taxes,
                    profit_factor=profit_factor,
                    avg_trade_pnl=avg_trade_pnl,
                    avg_winning_trade=avg_winning_trade,
                    avg_losing_trade=avg_losing_trade,
                    avg_hold_duration_minutes=avg_hold_duration,
                    max_drawdown_amount=max_drawdown_amount,
                    max_drawdown_pct=max_drawdown_pct
                )
                
                session.add(daily_perf)
                logger.info(f"Created daily performance for {target_date.strftime('%Y-%m-%d')}")
            
            session.commit()
            
        except Exception as e:
            logger.error(f"Failed to aggregate daily performance: {e}", exc_info=True)
            session.rollback()
        finally:
            session.close()
    
    async def _aggregate_strategy_performance(self, target_date: datetime):
        """
        Aggregate strategy-level performance from trades
        
        Computes per-strategy:
        - Total P&L
        - Win rate
        - Average trade metrics
        - Trade count
        """
        session = db.get_session()
        if not session:
            logger.error("Failed to get database session for strategy aggregation")
            return
        
        try:
            # Get date range
            start_of_day = datetime.combine(target_date.date(), time.min)
            end_of_day = datetime.combine(target_date.date(), time.max)
            
            # Query all closed trades for the day
            trades = session.query(Trade).filter(
                Trade.entry_time >= start_of_day,
                Trade.entry_time <= end_of_day,
                Trade.status == 'CLOSED'
            ).all()
            
            if not trades:
                session.close()
                return
            
            # Group trades by strategy
            strategy_groups: Dict[str, List[Trade]] = {}
            for trade in trades:
                # Normalize strategy name
                strategy_id = normalize_strategy_name(trade.strategy_name)
                if strategy_id not in strategy_groups:
                    strategy_groups[strategy_id] = []
                strategy_groups[strategy_id].append(trade)
            
            # Aggregate per strategy
            for strategy_id, strategy_trades in strategy_groups.items():
                total_trades = len(strategy_trades)
                winning_trades = sum(1 for t in strategy_trades if t.is_winning_trade)
                losing_trades = total_trades - winning_trades
                
                total_gross_pnl = sum(t.gross_pnl or 0 for t in strategy_trades)
                total_net_pnl = sum(t.net_pnl or 0 for t in strategy_trades)
                
                gross_profit = sum(t.gross_pnl or 0 for t in strategy_trades if (t.gross_pnl or 0) > 0)
                gross_loss = abs(sum(t.gross_pnl or 0 for t in strategy_trades if (t.gross_pnl or 0) < 0))
                
                # Win rate
                win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0
                
                # Profit factor
                profit_factor = gross_profit / gross_loss if gross_loss > 0 else (float('inf') if gross_profit > 0 else 0)
                
                # Average metrics
                avg_trade_pnl = total_net_pnl / total_trades if total_trades > 0 else 0
                avg_signal_strength = sum(t.signal_strength or 0 for t in strategy_trades) / total_trades if total_trades > 0 else 0
                avg_hold_duration = sum(t.hold_duration_minutes or 0 for t in strategy_trades) / total_trades if total_trades > 0 else 0
                
                # Check if record exists
                existing = session.query(StrategyPerformance).filter(
                    StrategyPerformance.trade_date == target_date.date(),
                    StrategyPerformance.strategy_name == strategy_id
                ).first()
                
                if existing:
                    # Update existing
                    existing.total_trades = total_trades
                    existing.winning_trades = winning_trades
                    existing.losing_trades = losing_trades
                    existing.win_rate = win_rate
                    existing.total_gross_pnl = total_gross_pnl
                    existing.total_net_pnl = total_net_pnl
                    existing.profit_factor = profit_factor
                    existing.avg_trade_pnl = avg_trade_pnl
                    existing.avg_signal_strength = avg_signal_strength
                    existing.avg_hold_duration_minutes = avg_hold_duration
                    existing.updated_at = datetime.utcnow()
                    
                    logger.debug(f"Updated strategy performance for {strategy_id}")
                else:
                    # Create new
                    strategy_perf = StrategyPerformance(
                        trade_date=target_date.date(),
                        strategy_name=strategy_id,
                        total_trades=total_trades,
                        winning_trades=winning_trades,
                        losing_trades=losing_trades,
                        win_rate=win_rate,
                        total_gross_pnl=total_gross_pnl,
                        total_net_pnl=total_net_pnl,
                        profit_factor=profit_factor,
                        avg_trade_pnl=avg_trade_pnl,
                        avg_signal_strength=avg_signal_strength,
                        avg_hold_duration_minutes=avg_hold_duration
                    )
                    
                    session.add(strategy_perf)
                    logger.debug(f"Created strategy performance for {strategy_id}")
            
            session.commit()
            logger.info(f"Aggregated performance for {len(strategy_groups)} strategies")
            
        except Exception as e:
            logger.error(f"Failed to aggregate strategy performance: {e}", exc_info=True)
            session.rollback()
        finally:
            session.close()
    
    async def schedule_daily_aggregation(self):
        """
        Schedule daily aggregation at 6:00 PM IST
        Runs continuously, checking every minute
        """
        logger.info("Daily performance aggregation scheduler started")
        
        while True:
            try:
                now = datetime.now()
                
                # Check if it's 6:00 PM and we haven't run today
                if (now.hour == 18 and now.minute == 0 and 
                    (self.last_run_date is None or self.last_run_date.date() < now.date())):
                    
                    logger.info("Triggering scheduled daily aggregation")
                    await self.run_aggregation(now)
                
                # Sleep for 60 seconds
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error(f"Error in aggregation scheduler: {e}", exc_info=True)
                await asyncio.sleep(60)
    
    async def backfill_aggregations(self, start_date: datetime, end_date: datetime):
        """
        Backfill performance aggregations for a date range
        
        Args:
            start_date: Start date
            end_date: End date
        """
        logger.info(f"Starting backfill from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        
        current_date = start_date
        while current_date <= end_date:
            await self.run_aggregation(current_date)
            current_date += timedelta(days=1)
        
        logger.info("Backfill completed")


# Global instance
performance_aggregator = PerformanceAggregationJob()


def get_performance_aggregator() -> PerformanceAggregationJob:
    """Get the global performance aggregator instance"""
    return performance_aggregator
