"""
Live SAC Meta-Controller
Real-time strategy allocation with Upstox/Zerodha bracket orders
"""

import asyncio
import numpy as np
from datetime import datetime, time
import pytz
from typing import Dict, List
import signal
import sys

from meta_controller.sac_agent import SACAgent
from meta_controller.state_builder import StateBuilder
from meta_controller.strategy_zoo import StrategyZoo, StrategySignal
from meta_controller.reward_calculator import RewardCalculator
from meta_controller.strategy_clustering import print_clustering
from backend.core.logger import get_logger
from backend.core.config import config
from backend.data.market_data import MarketDataManager
from backend.execution.order_manager import OrderManager

logger = get_logger(__name__)

IST = pytz.timezone('Asia/Kolkata')


class LiveSACController:
    """Live meta-controller using SAC for strategy allocation"""
    
    def __init__(self, initial_capital: float = 1000000):
        self.initial_capital = initial_capital
        self.portfolio_value = initial_capital
        self.running = False
        
        # Initialize components
        self.agent = SACAgent(state_dim=34, action_dim=9, device="cpu")
        self.state_builder = StateBuilder()
        self.strategy_zoo = StrategyZoo(portfolio_value=initial_capital)
        self.reward_calculator = RewardCalculator()
        self.market_data = MarketDataManager()
        self.order_manager = OrderManager()
        
        # Load trained model
        self.agent.load("models/sac_meta_controller.pth")
        
        # Risk management
        self.max_leverage = 4.0
        self.max_daily_loss = 0.05  # 5% max daily loss
        self.daily_pnl = 0.0
        self.risk_per_decision = 0.005  # 0.5% per decision
        
        # Trading hours (IST)
        self.market_open = time(9, 15)
        self.market_close = time(15, 30)
        
        # Episode tracking
        self.episode_states = []
        self.episode_actions = []
        self.episode_rewards = []
        self.last_decision_time = None
        
        # Performance tracking
        self.decisions_made = 0
        self.trades_executed = 0
        
        logger.info(f"Live SAC Controller initialized with ₹{initial_capital:,.0f}")
    
    async def start(self):
        """Start live trading loop"""
        self.running = True
        
        # Print strategy clustering
        print_clustering()
        
        logger.info("="*80)
        logger.info("LIVE SAC META-CONTROLLER STARTED")
        logger.info("="*80)
        logger.info(f"Initial Capital: ₹{self.initial_capital:,.0f}")
        logger.info(f"Max Leverage: {self.max_leverage}x")
        logger.info(f"Max Daily Loss: {self.max_daily_loss*100:.1f}%")
        logger.info(f"Risk Per Decision: {self.risk_per_decision*100:.2f}%")
        logger.info("="*80)
        
        # Setup graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        try:
            # Main trading loop
            while self.running:
                await self._trading_iteration()
                await asyncio.sleep(300)  # 5 minutes
                
        except Exception as e:
            logger.error(f"Error in trading loop: {e}")
        finally:
            await self.shutdown()
    
    async def _trading_iteration(self):
        """Single trading iteration (every 5 minutes)"""
        try:
            current_time = datetime.now(IST)
            
            # Check if market is open
            if not self._is_market_open(current_time):
                logger.debug("Market is closed")
                return
            
            # Check circuit breakers
            if not self._check_circuit_breakers():
                logger.warning("Circuit breakers triggered - pausing trading")
                return
            
            logger.info(f"\n{'='*80}")
            logger.info(f"SAC Decision #{self.decisions_made + 1} @ {current_time.strftime('%H:%M:%S')}")
            logger.info(f"{'='*80}")
            
            # Get current market data
            market_data = await self.market_data.get_all_data()
            
            if not market_data:
                logger.warning("No market data available")
                return
            
            # Calculate portfolio Greeks
            portfolio_delta, portfolio_gamma, portfolio_vega = self.strategy_zoo.calculate_portfolio_greeks()
            
            # Build state vector
            state = self.state_builder.build_state(
                symbol="NIFTY",
                timestamp=current_time,
                portfolio_delta=portfolio_delta,
                portfolio_gamma=portfolio_gamma,
                portfolio_vega=portfolio_vega
            )
            
            # Check if should pause
            if self.state_builder.should_pause_trading(state):
                logger.warning("⚠️  Trading paused due to extreme market conditions")
                return
            
            # Get risk multiplier based on regime
            risk_multiplier = self.state_builder.get_risk_multiplier(state)
            regime = self.state_builder.get_market_regime(state)
            
            logger.info(f"Market Regime: {regime}, Risk Multiplier: {risk_multiplier:.2f}x")
            
            # Select action (allocation) - deterministic in live trading
            allocation = self.agent.select_action(state, deterministic=True)
            
            # Log allocation
            self._log_allocation(allocation)
            
            # Generate signals from strategies
            signals = await self.strategy_zoo.generate_signals(
                market_data,
                allocation * risk_multiplier,
                current_time
            )
            
            logger.info(f"Generated {len(signals)} signals")
            
            # Execute signals with bracket orders
            executed_trades = await self._execute_signals_with_brackets(signals)
            
            self.trades_executed += len(executed_trades)
            
            # Calculate current leverage
            leverage = self.strategy_zoo.check_leverage()
            logger.info(f"Current Leverage: {leverage:.2f}x")
            
            # Store episode data for online learning
            self.episode_states.append(state)
            self.episode_actions.append(allocation)
            self.last_decision_time = current_time
            
            # Calculate reward if we have enough history
            if len(self.episode_states) >= 6:
                reward = await self._calculate_recent_reward()
                self.episode_rewards.append(reward)
                
                # Store transition for online learning
                prev_state = self.episode_states[-7]
                prev_action = self.episode_actions[-7]
                self.agent.store_transition(prev_state, prev_action, reward, state, False)
                
                # Online training (low frequency)
                if self.decisions_made % 20 == 0:
                    metrics = self.agent.train(batch_size=64)
                    if metrics:
                        logger.info(f"Online Training: Critic Loss={metrics['critic_loss']:.4f}, "
                                  f"Q-value={metrics['q_value']:.4f}")
            
            self.decisions_made += 1
            
            # Update portfolio value
            self.portfolio_value = await self._calculate_portfolio_value()
            self.daily_pnl = (self.portfolio_value / self.initial_capital - 1)
            
            logger.info(f"Portfolio Value: ₹{self.portfolio_value:,.0f} ({self.daily_pnl*100:+.2f}%)")
            logger.info(f"Decisions: {self.decisions_made}, Trades: {self.trades_executed}")
            
            # Save model periodically
            if self.decisions_made % 50 == 0:
                self.agent.save("models/sac_meta_controller_live.pth")
                logger.info("Model checkpoint saved")
            
        except Exception as e:
            logger.error(f"Error in trading iteration: {e}")
    
    async def _execute_signals_with_brackets(self, signals: List[StrategySignal]) -> List[Dict]:
        """Execute signals with bracket orders (entry, target, stop-loss)"""
        executed_trades = []
        
        for signal in signals:
            try:
                logger.info(f"\n📊 Executing Signal:")
                logger.info(f"   Strategy: {signal.strategy_name} (Group {signal.meta_group})")
                logger.info(f"   {signal.symbol} {signal.direction} {signal.strike}")
                logger.info(f"   Entry: ₹{signal.entry_price:.2f}, Qty: {signal.quantity}")
                logger.info(f"   Target: ₹{signal.target_price:.2f}, SL: ₹{signal.stop_loss:.2f}")
                
                # Place bracket order
                order = await self.order_manager.place_bracket_order(
                    symbol=signal.symbol,
                    strike=signal.strike,
                    option_type=signal.direction,
                    quantity=signal.quantity,
                    entry_price=signal.entry_price,
                    target_price=signal.target_price,
                    stop_loss=signal.stop_loss,
                    strategy_name=signal.strategy_name
                )
                
                if order['status'] == 'SUCCESS':
                    logger.info(f"   ✅ Order placed: {order['order_id']}")
                    executed_trades.append({
                        'signal': signal,
                        'order': order,
                        'timestamp': datetime.now(IST)
                    })
                else:
                    logger.warning(f"   ❌ Order failed: {order.get('message')}")
                    
            except Exception as e:
                logger.error(f"Error executing signal: {e}")
        
        return executed_trades
    
    def _log_allocation(self, allocation: np.ndarray):
        """Log allocation vector"""
        from meta_controller.strategy_clustering import META_GROUPS
        
        logger.info("\n📈 Strategy Allocation:")
        for i, alloc in enumerate(allocation):
            if alloc > 0.01:  # Only show significant allocations
                group = META_GROUPS[i]
                logger.info(f"   {group.name:30s}: {alloc*100:5.2f}%")
    
    async def _calculate_recent_reward(self) -> float:
        """Calculate reward for last 30 minutes"""
        try:
            # Get recent trades
            recent_trades = await self.order_manager.get_recent_trades(minutes=30)
            
            # Calculate realized PnL
            realized_pnl = sum(t['pnl'] for t in recent_trades if t['status'] == 'CLOSED')
            
            # Calculate max drawdown
            equity_history = [t.get('equity', self.portfolio_value) for t in recent_trades]
            if equity_history:
                running_max = np.maximum.accumulate(equity_history)
                drawdown = (equity_history[-1] - running_max[-1]) / self.portfolio_value
                max_dd = abs(drawdown)
            else:
                max_dd = 0
            
            # Get current portfolio delta
            portfolio_delta, _, _ = self.strategy_zoo.calculate_portfolio_greeks()
            
            # Calculate reward
            reward = self.reward_calculator.calculate_reward(
                realized_pnl,
                self.portfolio_value,
                max_dd,
                abs(portfolio_delta)
            )
            
            return reward
            
        except Exception as e:
            logger.error(f"Error calculating reward: {e}")
            return 0.0
    
    async def _calculate_portfolio_value(self) -> float:
        """Calculate current portfolio value"""
        try:
            # Get all positions
            positions = await self.order_manager.get_open_positions()
            
            # Calculate mark-to-market value
            total_value = self.initial_capital
            
            for pos in positions:
                # Add unrealized P&L
                total_value += pos.get('unrealized_pnl', 0)
            
            # Add realized P&L from closed trades
            closed_trades = await self.order_manager.get_todays_closed_trades()
            total_value += sum(t['pnl'] for t in closed_trades)
            
            return total_value
            
        except Exception as e:
            logger.error(f"Error calculating portfolio value: {e}")
            return self.portfolio_value
    
    def _is_market_open(self, current_time: datetime) -> bool:
        """Check if market is open"""
        current_time_only = current_time.time()
        
        # Check if weekday
        if current_time.weekday() >= 5:  # Saturday=5, Sunday=6
            return False
        
        # Check trading hours
        return self.market_open <= current_time_only <= self.market_close
    
    def _check_circuit_breakers(self) -> bool:
        """Check risk circuit breakers"""
        # Check daily loss limit
        if self.daily_pnl < -self.max_daily_loss:
            logger.error(f"Daily loss limit breached: {self.daily_pnl*100:.2f}%")
            return False
        
        # Check leverage
        leverage = self.strategy_zoo.check_leverage()
        if leverage > self.max_leverage:
            logger.error(f"Leverage limit breached: {leverage:.2f}x")
            return False
        
        return True
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info("Shutdown signal received")
        self.running = False
    
    async def shutdown(self):
        """Graceful shutdown"""
        logger.info("\n" + "="*80)
        logger.info("SHUTTING DOWN SAC META-CONTROLLER")
        logger.info("="*80)
        
        # Save final model
        self.agent.save("models/sac_meta_controller_final.pth")
        
        # Close all positions (optional)
        # await self.order_manager.close_all_positions()
        
        # Print final stats
        logger.info(f"Total Decisions Made: {self.decisions_made}")
        logger.info(f"Total Trades Executed: {self.trades_executed}")
        logger.info(f"Final Portfolio Value: ₹{self.portfolio_value:,.0f}")
        logger.info(f"Total P&L: {self.daily_pnl*100:+.2f}%")
        logger.info("="*80)


async def main():
    """Start live controller"""
    controller = LiveSACController(initial_capital=1000000)
    await controller.start()


if __name__ == "__main__":
    asyncio.run(main())
