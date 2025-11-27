#!/usr/bin/env python3
"""
Start Paper Trading with SAC Meta-Controller
Applies autopsy recommendations and runs optimized system
"""

import asyncio
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.core.logger import get_logger
from backend.core.config import config

logger = get_logger(__name__)


class SACPaperTradingEngine:
    """Paper trading engine with SAC meta-controller"""
    
    def __init__(self, initial_capital: float = 5000000):
        self.initial_capital = initial_capital
        self.portfolio_value = initial_capital
        self.sac_enabled = config.get('sac_meta_controller', {}).get('enabled', False)
        
        logger.info("="*80)
        logger.info("SAC-POWERED PAPER TRADING ENGINE")
        logger.info("="*80)
        logger.info(f"Initial Capital: ₹{initial_capital:,.0f}")
        logger.info(f"SAC Meta-Controller: {'✅ ENABLED' if self.sac_enabled else '❌ DISABLED'}")
        logger.info(f"Mode: PAPER TRADING")
        logger.info("="*80)
        
        if self.sac_enabled:
            self._load_sac_controller()
        
        self._load_strategies()
    
    def _load_sac_controller(self):
        """Load SAC meta-controller"""
        try:
            from meta_controller.sac_agent import SACAgent
            from meta_controller.state_builder import StateBuilder
            from meta_controller.strategy_zoo import StrategyZoo
            
            sac_config = config.get('sac_meta_controller', {})
            model_path = sac_config.get('model_path', 'models/sac_comprehensive_real.pth')
            
            self.sac_agent = SACAgent(state_dim=35, action_dim=9)
            
            if os.path.exists(model_path):
                self.sac_agent.load(model_path)
                logger.info(f"✅ Loaded SAC model: {model_path}")
            else:
                logger.warning(f"⚠️  SAC model not found: {model_path}, using random initialization")
            
            self.state_builder = StateBuilder()
            self.strategy_zoo = StrategyZoo(portfolio_value=self.initial_capital)
            
            logger.info("✅ SAC Meta-Controller initialized")
            
        except Exception as e:
            logger.error(f"❌ Failed to load SAC controller: {e}")
            self.sac_enabled = False
    
    def _load_strategies(self):
        """Load configured strategies"""
        strategies_config = config.get('strategies', {})
        
        logger.info("\n📊 ACTIVE STRATEGIES:")
        logger.info("-"*80)
        
        active_count = 0
        killed_count = 0
        
        for strategy_name, strategy_config in strategies_config.items():
            enabled = strategy_config.get('enabled', False)
            allocation = strategy_config.get('allocation', 0)
            
            if enabled:
                active_count += 1
                filters = strategy_config.get('filters', {})
                time_filter = filters.get('time_window', {}).get('enabled', False)
                day_filter = filters.get('day_of_week', {}).get('enabled', False)
                
                logger.info(f"  ✅ {strategy_name}: {allocation*100:.0f}% allocation")
                if time_filter:
                    tw = filters.get('time_window', {})
                    logger.info(f"      ⏰ Time: {tw.get('start_hour')}:{tw.get('start_minute'):02d}-{tw.get('end_hour')}:{tw.get('end_minute'):02d}")
                if day_filter:
                    logger.info(f"      📅 Days: {filters.get('day_of_week', {}).get('allowed_days')}")
            else:
                killed_count += 1
                reason = strategy_config.get('reason', 'Disabled')
                logger.info(f"  ❌ {strategy_name}: DISABLED - {reason}")
        
        logger.info("-"*80)
        logger.info(f"Active: {active_count} | Disabled: {killed_count}")
        logger.info("="*80)
        
        self.active_strategies = active_count
    
    def _write_status_file(self, allocation, iteration, pnl):
        """Write current status to JSON file for dashboard"""
        import json
        import numpy as np
        
        status = {
            'timestamp': datetime.now().isoformat(),
            'capital': self.portfolio_value,
            'initial_capital': self.initial_capital,
            'total_pnl': self.portfolio_value - self.initial_capital,
            'last_pnl': pnl,
            'iteration': iteration,
            'sac_enabled': self.sac_enabled,
            'active_strategies': self.active_strategies,
            'sac_allocation': allocation.tolist() if isinstance(allocation, np.ndarray) else list(allocation),
            'top_groups': allocation.argsort()[-3:][::-1].tolist() if isinstance(allocation, np.ndarray) else [],
            'market_status': 'open',
            'strategies': {
                'quantum_edge': {'enabled': True, 'allocation': 0.25},
                'quantum_edge_v2': {'enabled': True, 'allocation': 0.25},
                'default': {'enabled': True, 'allocation': 0.15},
                'gamma_scalping': {'enabled': True, 'allocation': 0.15},
                'vwap_deviation': {'enabled': True, 'allocation': 0.15},
                'iv_rank_trading': {'enabled': True, 'allocation': 0.15}
            }
        }
        
        try:
            with open('frontend/dashboard/paper_trading_status.json', 'w') as f:
                json.dump(status, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to write status file: {e}")
    
    async def run(self):
        """Main trading loop"""
        logger.info("\n🚀 Starting paper trading loop...")
        logger.info("📊 Press Ctrl+C to stop\n")
        
        iteration = 0
        
        try:
            while True:
                iteration += 1
                current_time = datetime.now()
                
                # Check if market is open (9:15 AM - 3:30 PM IST)
                market_open_hour = 9
                market_close_hour = 15
                
                if current_time.hour < market_open_hour or current_time.hour >= market_close_hour:
                    if iteration % 12 == 1:  # Log every hour when market closed
                        logger.info(f"⏸️  Market closed - waiting... ({current_time.strftime('%H:%M:%S')})")
                    await asyncio.sleep(300)  # 5 minutes
                    continue
                
                logger.info(f"\n{'='*80}")
                logger.info(f"Iteration #{iteration} @ {current_time.strftime('%H:%M:%S')}")
                logger.info(f"Portfolio: ₹{self.portfolio_value:,.0f}")
                logger.info(f"{'='*80}")
                
                if self.sac_enabled:
                    # Get state
                    try:
                        portfolio_delta, portfolio_gamma, portfolio_vega = self.strategy_zoo.calculate_portfolio_greeks()
                        
                        state = self.state_builder.build_state(
                            symbol="NIFTY",
                            timestamp=current_time,
                            portfolio_delta=portfolio_delta,
                            portfolio_gamma=portfolio_gamma,
                            portfolio_vega=portfolio_vega
                        )
                        
                        # Check if should pause
                        if self.state_builder.should_pause_trading(state):
                            logger.warning("⚠️  Trading paused - extreme market conditions")
                            await asyncio.sleep(300)
                            continue
                        
                        # Get allocation from SAC
                        allocation = self.sac_agent.select_action(state, deterministic=True)
                        
                        logger.info(f"🧠 SAC Allocation: {allocation}")
                        logger.info(f"   Top 3 Groups: {allocation.argsort()[-3:][::-1]}")
                        
                        # TODO: Execute trades based on allocation
                        # For now, just simulate
                        simulated_pnl = (allocation.max() - 0.11) * 5000  # Mock P&L
                        self.portfolio_value += simulated_pnl
                        
                        logger.info(f"💰 Simulated P&L: ₹{simulated_pnl:,.2f}")
                        
                        # Write status to JSON for dashboard
                        self._write_status_file(allocation, iteration, simulated_pnl)
                        
                    except Exception as e:
                        logger.error(f"❌ SAC iteration error: {e}")
                
                else:
                    logger.info("📊 Running without SAC (traditional strategy execution)")
                    # TODO: Run traditional strategies
                
                # Wait for next iteration (5 minutes)
                await asyncio.sleep(300)
                
        except KeyboardInterrupt:
            logger.info("\n\n⏹️  Stopping paper trading...")
            logger.info(f"Final Portfolio Value: ₹{self.portfolio_value:,.0f}")
            logger.info(f"Total P&L: ₹{self.portfolio_value - self.initial_capital:,.0f}")
            logger.info("="*80)


async def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='SAC-Powered Paper Trading Engine')
    parser.add_argument('--capital', type=float, default=5000000, help='Initial capital (default: 5000000)')
    args = parser.parse_args()
    
    engine = SACPaperTradingEngine(initial_capital=args.capital)
    await engine.run()


if __name__ == "__main__":
    asyncio.run(main())
