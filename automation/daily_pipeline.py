#!/usr/bin/env python3
"""
DAILY PRODUCTION PIPELINE - Systems Operator
Runs every morning at 8:00 AM IST

Sequence:
1. Data Quality Check
2. QuantumEdge Incremental Train (new day's data only)
3. SAC Online Replay (today's decisions only, <60s)
4. Pre-Market Report
5. Start Paper/Live Engine

Author: AI Systems Operator
Last Modified: 2025-11-20
"""

import sys
import os
from datetime import datetime, timedelta
from pathlib import Path
import logging
import traceback

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core.config import config
from backend.core.logger import get_logger
from monitoring.alerts import TelegramAlerts

logger = get_logger(__name__)
alerts = TelegramAlerts()


class DailyPipeline:
    """Daily morning pipeline orchestrator"""
    
    def __init__(self):
        self.pipeline_start = datetime.now()
        self.results = {
            'data_quality': None,
            'quantum_edge': None,
            'sac_online': None,
            'pre_market': None,
            'engine_start': None
        }
        self.errors = []
        
        logger.info("="*80)
        logger.info("DAILY PRODUCTION PIPELINE - STARTING")
        logger.info(f"Time: {self.pipeline_start.strftime('%Y-%m-%d %H:%M:%S IST')}")
        logger.info("="*80)
    
    def run(self):
        """Execute complete daily pipeline"""
        try:
            # Step 1: Data Quality Check
            self._step_data_quality()
            
            # Step 2: QuantumEdge Incremental Training
            self._step_quantum_edge_incremental()
            
            # Step 3: SAC Online Learning (today's replay only)
            self._step_sac_online_update()
            
            # Step 4: Pre-Market Report
            self._step_pre_market_report()
            
            # Step 5: Start Trading Engine
            self._step_start_engine()
            
            # Final Report
            self._send_completion_report()
            
        except Exception as e:
            logger.error(f"CRITICAL: Pipeline failed: {e}")
            logger.error(traceback.format_exc())
            alerts.send_critical(
                f"🚨 DAILY PIPELINE FAILED\n\n"
                f"Error: {e}\n\n"
                f"Time: {datetime.now()}\n"
                f"Check logs immediately!"
            )
            sys.exit(1)
    
    def _step_data_quality(self):
        """Step 1: Check data quality from yesterday"""
        logger.info("\n" + "="*80)
        logger.info("STEP 1: DATA QUALITY CHECK")
        logger.info("="*80)
        
        try:
            import subprocess
            
            # Run quick data quality summary
            result = subprocess.run(
                ['bash', 'data_quality/summary_report.sh'],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                raise Exception(f"Data quality check failed: {result.stderr}")
            
            # Parse quality percentage
            output = result.stdout
            quality_pct = self._extract_quality_percentage(output)
            
            self.results['data_quality'] = {
                'status': 'success',
                'quality_pct': quality_pct,
                'timestamp': datetime.now()
            }
            
            logger.info(f"✅ Data quality: {quality_pct}%")
            
            # Alert if quality drops below 60%
            if quality_pct < 60:
                alerts.send_warning(
                    f"⚠️ DATA QUALITY LOW\n\n"
                    f"Quality: {quality_pct}%\n"
                    f"Threshold: 60%\n\n"
                    f"Consider running cleanup."
                )
            
        except Exception as e:
            logger.error(f"❌ Data quality check failed: {e}")
            self.errors.append(('data_quality', str(e)))
            self.results['data_quality'] = {'status': 'failed', 'error': str(e)}
    
    def _step_quantum_edge_incremental(self):
        """Step 2: QuantumEdge incremental training on yesterday's data"""
        logger.info("\n" + "="*80)
        logger.info("STEP 2: QUANTUMEDGE INCREMENTAL TRAINING")
        logger.info("="*80)
        
        try:
            from training.quantum_edge_v2.incremental_train import IncrementalTrainer
            
            # Get yesterday's data
            yesterday = datetime.now() - timedelta(days=1)
            
            logger.info(f"Training on: {yesterday.strftime('%Y-%m-%d')}")
            logger.info("Mode: Incremental (new data only)")
            
            trainer = IncrementalTrainer(
                model_path='models/quantum_edge_v2.pt',
                data_date=yesterday
            )
            
            # Quick incremental update (5-10 minutes)
            metrics = trainer.incremental_update()
            
            self.results['quantum_edge'] = {
                'status': 'success',
                'accuracy': metrics.get('accuracy', 0),
                'loss': metrics.get('loss', 0),
                'samples': metrics.get('samples', 0),
                'timestamp': datetime.now()
            }
            
            logger.info(f"✅ QuantumEdge updated: {metrics.get('accuracy', 0):.2%} accuracy")
            
            # Alert if accuracy drops below 80%
            if metrics.get('accuracy', 0) < 0.80:
                alerts.send_warning(
                    f"⚠️ QUANTUMEDGE ACCURACY DROP\n\n"
                    f"Accuracy: {metrics.get('accuracy', 0):.2%}\n"
                    f"Threshold: 80%\n\n"
                    f"Model may need full retrain."
                )
            
        except Exception as e:
            logger.error(f"❌ QuantumEdge training failed: {e}")
            logger.error(traceback.format_exc())
            self.errors.append(('quantum_edge', str(e)))
            self.results['quantum_edge'] = {'status': 'failed', 'error': str(e)}
    
    def _step_sac_online_update(self):
        """Step 3: SAC online learning from yesterday's decisions"""
        logger.info("\n" + "="*80)
        logger.info("STEP 3: SAC ONLINE LEARNING")
        logger.info("="*80)
        
        try:
            from meta_controller.sac_agent import SACAgent
            
            # Check if today is a full retrain day
            today = datetime.now().strftime('%A')
            full_retrain_days = config.get('sac_training', {}).get('full_retrain_days', ['Friday', 'Sunday'])
            
            if today in full_retrain_days:
                logger.info(f"⏭️  Skipping online update - Full retrain scheduled for {today}")
                self.results['sac_online'] = {
                    'status': 'skipped',
                    'reason': f'Full retrain day ({today})',
                    'timestamp': datetime.now()
                }
                return
            
            logger.info("Mode: Online learning only (experience replay)")
            logger.info("Target: <60 seconds")
            
            # Load agent
            agent = SACAgent(state_dim=35, action_dim=9)
            agent.load('models/sac_prod_latest.pth')
            
            # Get yesterday's experience buffer
            yesterday = datetime.now() - timedelta(days=1)
            experience_buffer = agent.load_experience_buffer(yesterday)
            
            if not experience_buffer or len(experience_buffer) == 0:
                logger.warning("⚠️  No experience buffer from yesterday")
                self.results['sac_online'] = {
                    'status': 'skipped',
                    'reason': 'No experience data',
                    'timestamp': datetime.now()
                }
                return
            
            logger.info(f"Experience samples: {len(experience_buffer)}")
            
            # Online update (fast, <60s)
            start_time = datetime.now()
            metrics = agent.online_update(experience_buffer)
            duration = (datetime.now() - start_time).total_seconds()
            
            self.results['sac_online'] = {
                'status': 'success',
                'critic_loss': metrics.get('critic_loss', 0),
                'actor_loss': metrics.get('actor_loss', 0),
                'samples': len(experience_buffer),
                'duration_seconds': duration,
                'timestamp': datetime.now()
            }
            
            logger.info(f"✅ SAC updated in {duration:.1f}s")
            logger.info(f"   Critic loss: {metrics.get('critic_loss', 0):.4f}")
            logger.info(f"   Actor loss: {metrics.get('actor_loss', 0):.4f}")
            
            # Critical: Monitor critic loss jump
            previous_loss = agent.get_previous_critic_loss()
            if previous_loss and metrics.get('critic_loss', 0) > previous_loss * 3.0:
                # >300% jump - CRITICAL!
                alerts.send_critical(
                    f"🚨 SAC CRITIC LOSS SPIKE!\n\n"
                    f"Previous: {previous_loss:.4f}\n"
                    f"Current: {metrics.get('critic_loss', 0):.4f}\n"
                    f"Jump: {(metrics.get('critic_loss', 0)/previous_loss - 1)*100:.1f}%\n\n"
                    f"⚠️  TRADING PAUSED\n"
                    f"Action required!"
                )
                # Pause trading
                self._pause_trading()
                raise Exception("Critic loss spike detected - trading paused")
            
        except Exception as e:
            logger.error(f"❌ SAC online update failed: {e}")
            logger.error(traceback.format_exc())
            self.errors.append(('sac_online', str(e)))
            self.results['sac_online'] = {'status': 'failed', 'error': str(e)}
    
    def _step_pre_market_report(self):
        """Step 4: Generate pre-market report"""
        logger.info("\n" + "="*80)
        logger.info("STEP 4: PRE-MARKET REPORT")
        logger.info("="*80)
        
        try:
            report = self._generate_pre_market_report()
            
            self.results['pre_market'] = {
                'status': 'success',
                'report': report,
                'timestamp': datetime.now()
            }
            
            logger.info("✅ Pre-market report generated")
            
            # Send to Telegram
            alerts.send_info(
                f"📊 PRE-MARKET REPORT\n"
                f"{'='*40}\n\n"
                f"{report}"
            )
            
        except Exception as e:
            logger.error(f"❌ Pre-market report failed: {e}")
            self.errors.append(('pre_market', str(e)))
            self.results['pre_market'] = {'status': 'failed', 'error': str(e)}
    
    def _step_start_engine(self):
        """Step 5: Start trading engine"""
        logger.info("\n" + "="*80)
        logger.info("STEP 5: START TRADING ENGINE")
        logger.info("="*80)
        
        try:
            # Check if already running
            import subprocess
            result = subprocess.run(
                ['ps', 'aux'],
                capture_output=True,
                text=True
            )
            
            if 'start_sac_paper_trading' in result.stdout:
                logger.info("✅ Trading engine already running")
                self.results['engine_start'] = {
                    'status': 'already_running',
                    'timestamp': datetime.now()
                }
                return
            
            # Start engine
            logger.info("Starting paper trading engine...")
            subprocess.Popen(
                ['nohup', 'python3', 'start_sac_paper_trading.py', '--capital', '5000000'],
                stdout=open('paper_trading_live.log', 'a'),
                stderr=subprocess.STDOUT
            )
            
            self.results['engine_start'] = {
                'status': 'started',
                'timestamp': datetime.now()
            }
            
            logger.info("✅ Trading engine started")
            
        except Exception as e:
            logger.error(f"❌ Engine start failed: {e}")
            self.errors.append(('engine_start', str(e)))
            self.results['engine_start'] = {'status': 'failed', 'error': str(e)}
    
    def _send_completion_report(self):
        """Send final pipeline completion report"""
        duration = (datetime.now() - self.pipeline_start).total_seconds()
        
        logger.info("\n" + "="*80)
        logger.info("DAILY PIPELINE COMPLETE")
        logger.info("="*80)
        logger.info(f"Duration: {duration:.1f}s")
        
        # Build report
        status_emoji = "✅" if len(self.errors) == 0 else "⚠️"
        
        report = (
            f"{status_emoji} DAILY PIPELINE COMPLETE\n"
            f"{'='*40}\n\n"
            f"⏱️  Duration: {duration:.1f}s\n\n"
        )
        
        # Results summary
        for step, result in self.results.items():
            if result:
                status = result.get('status', 'unknown')
                emoji = "✅" if status == 'success' else "⚠️" if status == 'skipped' else "❌"
                report += f"{emoji} {step.replace('_', ' ').title()}: {status}\n"
        
        # Errors
        if self.errors:
            report += f"\n⚠️  Errors: {len(self.errors)}\n"
            for step, error in self.errors:
                report += f"  • {step}: {error[:100]}\n"
        
        # Key metrics
        if self.results.get('data_quality', {}).get('quality_pct'):
            report += f"\n📊 Data Quality: {self.results['data_quality']['quality_pct']}%"
        
        if self.results.get('quantum_edge', {}).get('accuracy'):
            report += f"\n🤖 QuantumEdge: {self.results['quantum_edge']['accuracy']:.2%} accuracy"
        
        if self.results.get('sac_online', {}).get('critic_loss'):
            report += f"\n🎯 SAC Critic Loss: {self.results['sac_online']['critic_loss']:.4f}"
        
        logger.info(report)
        
        # Send to Telegram
        if len(self.errors) == 0:
            alerts.send_success(report)
        else:
            alerts.send_warning(report)
    
    def _extract_quality_percentage(self, output: str) -> float:
        """Extract quality percentage from summary report"""
        import re
        match = re.search(r'(\d+\.?\d*)%\s+clean', output, re.IGNORECASE)
        if match:
            return float(match.group(1))
        return 0.0
    
    def _generate_pre_market_report(self) -> str:
        """Generate pre-market analysis report"""
        report = []
        report.append(f"Date: {datetime.now().strftime('%Y-%m-%d')}")
        report.append(f"Market Opens: 09:15 AM IST")
        report.append("")
        
        # System status
        report.append("System Status:")
        report.append(f"  • Data Quality: {self.results.get('data_quality', {}).get('quality_pct', 'N/A')}%")
        report.append(f"  • QuantumEdge: {self.results.get('quantum_edge', {}).get('status', 'N/A')}")
        report.append(f"  • SAC: {self.results.get('sac_online', {}).get('status', 'N/A')}")
        report.append("")
        
        # Strategy allocations
        report.append("Active Strategies: 6")
        report.append("  • quantum_edge_v2: 25%")
        report.append("  • quantum_edge: 25%")
        report.append("  • default: 15%")
        report.append("  • gamma_scalping: 15%")
        report.append("  • vwap_deviation: 15%")
        report.append("  • iv_rank_trading: 15%")
        
        return "\n".join(report)
    
    def _pause_trading(self):
        """Emergency pause trading"""
        import subprocess
        logger.warning("⚠️  PAUSING TRADING ENGINE")
        
        result = subprocess.run(['pkill', '-f', 'start_sac_paper_trading'], capture_output=True)
        logger.info("Trading engine stopped")


def main():
    """Main entry point"""
    pipeline = DailyPipeline()
    pipeline.run()


if __name__ == "__main__":
    main()
