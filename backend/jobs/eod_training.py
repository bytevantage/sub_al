"""
End-of-Day Training Job
Schedules and runs ML model retraining at end of trading day
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, time as dt_time
import asyncio
from typing import Optional

from backend.core.logger import get_logger
from backend.ml.model_manager import ModelManager
from backend.ml.training_data_collector import TrainingDataCollector

logger = get_logger(__name__)


class EODTrainingJob:
    """Schedules and executes end-of-day ML training"""
    
    def __init__(
        self, 
        model_manager: ModelManager, 
        data_collector: TrainingDataCollector,
        eod_time: dt_time = dt_time(16, 0),  # 4:00 PM
        strategy_engine = None  # Optional: for weight adjustment
    ):
        self.model_manager = model_manager
        self.data_collector = data_collector
        self.strategy_engine = strategy_engine
        self.eod_time = eod_time
        self.scheduler = AsyncIOScheduler()
        self.is_running = False
        self.last_training_date: Optional[datetime] = None
        
    async def start(self):
        """Start the EOD training scheduler"""
        try:
            # Schedule for Monday to Friday at specified time
            self.scheduler.add_job(
                self.run_training,
                'cron',
                day_of_week='mon-fri',
                hour=self.eod_time.hour,
                minute=self.eod_time.minute,
                id='eod_training_job'
            )
            
            self.scheduler.start()
            self.is_running = True
            
            logger.info(f"✓ EOD training job scheduled for {self.eod_time.strftime('%H:%M')} (Mon-Fri)")
            
        except Exception as e:
            logger.error(f"Error starting EOD training job: {e}")
    
    async def stop(self):
        """Stop the EOD training scheduler"""
        try:
            if self.scheduler.running:
                self.scheduler.shutdown()
                self.is_running = False
                logger.info("EOD training job stopped")
        except Exception as e:
            logger.error(f"Error stopping EOD training job: {e}")
    
    async def run_training(self):
        """
        Execute the complete EOD training workflow
        
        Steps:
        1. Load existing training data or collect from database
        2. Retrain ML model if enough samples
        3. Save updated model
        """
        try:
            logger.info("=" * 60)
            logger.info("=== Starting End-of-Day Training Workflow ===")
            logger.info("=" * 60)
            
            today = datetime.now()
            self.last_training_date = today
            
            # Step 1: Try to load existing historical data first
            logger.info(f"Step 1: Loading existing training data")
            
            all_data = await self.data_collector.load_all_training_data()
            
            if all_data.empty:
                logger.info("No historical CSV data found - collecting from database")
                # Collect all available closed trades from database
                daily_df = await self.data_collector.collect_daily_data(lookback_days=0)  # 0 = all time
                
                if daily_df.empty:
                    logger.warning("No closed trades found in database - skipping training")
                    return
                
                logger.info(f"✓ Collected {len(daily_df)} trade samples from database")
                
                # Save to CSV for future use
                filename = f"trades_{today.strftime('%Y%m%d')}.csv"
                await self.data_collector.save_training_data(daily_df, filename)
                all_data = daily_df
            else:
                logger.info(f"✓ Loaded {len(all_data)} samples from existing CSV files")
            
            # Step 2: Get training statistics
            stats = await self.data_collector.get_training_statistics()
            
            logger.info("Training Data Statistics:")
            logger.info(f"  Total Samples: {stats.get('total_samples', 0)}")
            logger.info(f"  Winning Trades: {stats.get('winning_trades', 0)}")
            logger.info(f"  Losing Trades: {stats.get('losing_trades', 0)}")
            logger.info(f"  Win Rate: {stats.get('win_rate', 0):.1f}%")
            logger.info(f"  Avg P&L: {stats.get('avg_pnl_percent', 0):.2f}%")
            logger.info(f"  Avg Hold: {stats.get('avg_hold_duration', 0):.0f} minutes")
            
            # Step 3: Check if we should retrain
            min_samples = self.model_manager.min_training_samples
            
            if len(all_data) < min_samples:
                logger.info(f"Not enough data for retraining ({len(all_data)}/{min_samples})")
                logger.info(f"Need {min_samples - len(all_data)} more samples")
                return
            
            # Step 4: Train the model
            logger.info(f"Step 4: Training ML model with {len(all_data)} samples")
            
            success = await self.model_manager.train_model(all_data)
            
            if success:
                logger.info("✓ ML model training completed successfully")
                
                # Log model info
                model_info = self.model_manager.get_model_info()
                if model_info.get('model_loaded'):
                    metrics = model_info.get('metrics', {})
                    logger.info(f"Model Metrics:")
                    logger.info(f"  Accuracy: {metrics.get('accuracy', 0):.3f}")
                    logger.info(f"  AUC: {metrics.get('auc', 0):.3f}")
                    logger.info(f"  CV Score: {metrics.get('cv_mean', 0):.3f}")
                
                # Step 5: Adjust strategy weights based on performance (if strategy_engine available)
                if self.strategy_engine:
                    logger.info("\nStep 5: Adjusting strategy weights based on performance")
                    
                    adjustments = await self.strategy_engine.adjust_strategy_weights(lookback_days=30)
                    
                    if adjustments:
                        # Count significant adjustments
                        significant = sum(1 for a in adjustments.values() if abs(a.get('change', 0)) >= 5)
                        logger.info(f"✓ Adjusted weights for {significant} strategies")
                    else:
                        logger.info("No weight adjustments needed")
            else:
                logger.error("ML model training failed")
            
            logger.info("=" * 60)
            logger.info("=== End-of-Day Training Workflow Complete ===")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"Error in EOD training workflow: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    async def run_manual_training(self, date: Optional[datetime] = None):
        """
        Manually trigger training for a specific date or today
        
        Args:
            date: Date to collect data for (defaults to today)
        """
        try:
            if date is None:
                date = datetime.now()
            
            logger.info(f"Manual training triggered for {date.date()}")
            await self.run_training()
            
        except Exception as e:
            logger.error(f"Error in manual training: {e}")
    
    def get_status(self) -> dict:
        """Get status of EOD training job"""
        next_run = None
        
        if self.scheduler.running:
            job = self.scheduler.get_job('eod_training_job')
            if job and job.next_run_time:
                next_run = job.next_run_time.isoformat()
        
        return {
            'is_running': self.is_running,
            'scheduled_time': self.eod_time.strftime('%H:%M'),
            'next_run': next_run,
            'last_training_date': self.last_training_date.isoformat() if self.last_training_date else None,
            'scheduler_running': self.scheduler.running
        }


# Convenience function for testing
async def test_eod_training():
    """Test the EOD training workflow"""
    from backend.database.database import db
    
    logger.info("Testing EOD Training Workflow")
    
    # Initialize components
    model_manager = ModelManager()
    await model_manager.load_models()
    
    data_collector = TrainingDataCollector(db)
    
    # Create EOD job
    eod_job = EODTrainingJob(model_manager, data_collector)
    
    # Run training manually
    await eod_job.run_manual_training()
    
    logger.info("Test complete")


if __name__ == "__main__":
    # Run test
    asyncio.run(test_eod_training())
