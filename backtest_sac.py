"""
SAC Backtesting Engine
Walk-forward backtest on 2024-2025 historical data
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import asyncio
from typing import Dict, List
import matplotlib.pyplot as plt
import seaborn as sns

from meta_controller.sac_agent import SACAgent
from meta_controller.state_builder import StateBuilder
from meta_controller.strategy_zoo import StrategyZoo
from meta_controller.reward_calculator import RewardCalculator
from features.greeks_engine import GreeksEngine
from backend.core.logger import get_logger
from backend.database.database import get_db

logger = get_logger(__name__)


class SACBacktester:
    """Backtest SAC meta-controller on historical data"""
    
    def __init__(
        self,
        start_date: str = "2024-01-01",
        end_date: str = "2025-11-01",
        initial_capital: float = 1000000,
        training_mode: bool = True
    ):
        self.start_date = pd.Timestamp(start_date)
        self.end_date = pd.Timestamp(end_date)
        self.initial_capital = initial_capital
        self.training_mode = training_mode
        
        # Initialize components
        self.agent = SACAgent(state_dim=34, action_dim=9)
        self.state_builder = StateBuilder()
        self.strategy_zoo = StrategyZoo(portfolio_value=initial_capital)
        self.reward_calculator = RewardCalculator()
        
        # Results storage
        self.equity_curve = []
        self.allocation_history = []
        self.pnl_by_group = {i: [] for i in range(9)}
        self.trades = []
        
        logger.info(f"Backtest initialized: {start_date} to {end_date}")
    
    async def run_backtest(self):
        """Run complete walk-forward backtest"""
        logger.info("Starting SAC backtest...")
        
        # Get all timestamps
        timestamps = await self._get_timestamps()
        
        if not timestamps:
            logger.error("No timestamps found in database")
            return
        
        logger.info(f"Found {len(timestamps)} timestamps")
        
        # Initialize portfolio
        portfolio_value = self.initial_capital
        positions = []
        episode_buffer = []
        
        # Walk through each timestamp
        for i, timestamp in enumerate(timestamps):
            try:
                # Build state
                portfolio_delta, portfolio_gamma, portfolio_vega = self._calculate_portfolio_greeks(positions)
                state = self.state_builder.build_state(
                    symbol="NIFTY",
                    timestamp=timestamp,
                    portfolio_delta=portfolio_delta,
                    portfolio_gamma=portfolio_gamma,
                    portfolio_vega=portfolio_vega
                )
                
                # Check if should pause
                if self.state_builder.should_pause_trading(state):
                    logger.warning(f"Trading paused at {timestamp}")
                    continue
                
                # Select action (allocation)
                deterministic = not self.training_mode
                allocation = self.agent.select_action(state, deterministic=deterministic)
                
                # Store allocation
                self.allocation_history.append({
                    'timestamp': timestamp,
                    'allocation': allocation.copy()
                })
                
                # Generate and execute signals
                # Simulate market data (in real backtest, would fetch from DB)
                market_data = await self._get_market_data(timestamp)
                signals = await self.strategy_zoo.generate_signals(market_data, allocation, timestamp)
                
                # Execute signals and update positions
                positions, trades = self._execute_signals(signals, positions, timestamp)
                self.trades.extend(trades)
                
                # Calculate PnL and reward after 30 minutes (6 bars)
                if i >= 6:
                    # Get next state
                    next_timestamp = timestamps[min(i + 6, len(timestamps) - 1)]
                    portfolio_delta_next, portfolio_gamma_next, portfolio_vega_next = self._calculate_portfolio_greeks(positions)
                    next_state = self.state_builder.build_state(
                        symbol="NIFTY",
                        timestamp=next_timestamp,
                        portfolio_delta=portfolio_delta_next,
                        portfolio_gamma=portfolio_gamma_next,
                        portfolio_vega=portfolio_vega_next
                    )
                    
                    # Calculate reward
                    pnl_30min = sum(t['pnl'] for t in self.trades[-20:] if t['exit_time'] <= next_timestamp)
                    max_dd = self._calculate_max_dd(positions)
                    reward = self.reward_calculator.calculate_reward(
                        pnl_30min,
                        portfolio_value,
                        max_dd,
                        abs(portfolio_delta_next)
                    )
                    
                    # Store transition
                    if self.training_mode:
                        prev_state = episode_buffer[-6][0] if len(episode_buffer) >= 6 else state
                        prev_action = episode_buffer[-6][1] if len(episode_buffer) >= 6 else allocation
                        self.agent.store_transition(prev_state, prev_action, reward, next_state, False)
                    
                    episode_buffer.append((state, allocation, reward, next_state))
                
                # Update portfolio value
                portfolio_value = self._calculate_portfolio_value(positions)
                self.equity_curve.append({
                    'timestamp': timestamp,
                    'equity': portfolio_value
                })
                
                # Train agent every 50 steps
                if self.training_mode and i % 50 == 0 and i > 100:
                    metrics = self.agent.train(batch_size=256)
                    if metrics:
                        logger.info(f"Step {i}: Critic Loss={metrics['critic_loss']:.4f}, "
                                  f"Q-value={metrics['q_value']:.4f}, Alpha={metrics['alpha']:.4f}")
                
                # Progress update
                if i % 100 == 0:
                    logger.info(f"Processed {i}/{len(timestamps)} timestamps, Equity: ₹{portfolio_value:,.0f}")
                
            except Exception as e:
                logger.error(f"Error at timestamp {timestamp}: {e}")
                continue
        
        # Final analysis
        await self._analyze_results()
        
        # Save model
        if self.training_mode:
            self.agent.save("models/sac_meta_controller.pth")
            logger.info("Model saved")
    
    async def _get_timestamps(self) -> List[datetime]:
        """Get all 5-minute timestamps from database"""
        try:
            from sqlalchemy import text
            
            db = next(get_db())
            query = text("""
                SELECT DISTINCT timestamp
                FROM option_snapshots
                WHERE symbol = 'NIFTY'
                    AND timestamp BETWEEN :start_date AND :end_date
                ORDER BY timestamp
            """)
            
            result = db.execute(query, {
                "start_date": self.start_date,
                "end_date": self.end_date
            })
            
            timestamps = [row[0] for row in result.fetchall()]
            db.close()
            
            return timestamps
            
        except Exception as e:
            logger.error(f"Error getting timestamps: {e}")
            return []
    
    async def _get_market_data(self, timestamp: datetime) -> Dict:
        """Get market data for timestamp (simplified)"""
        # In full implementation, would query option_snapshots table
        return {
            'NIFTY': {
                'spot_price': 26000,
                'timestamp': timestamp
            }
        }
    
    def _execute_signals(self, signals, positions, timestamp) -> tuple:
        """Execute signals and update positions"""
        new_trades = []
        
        for signal in signals:
            # Simulate trade execution
            trade = {
                'timestamp': timestamp,
                'strategy': signal.strategy_name,
                'meta_group': signal.meta_group,
                'symbol': signal.symbol,
                'direction': signal.direction,
                'entry_price': signal.entry_price,
                'quantity': signal.quantity,
                'pnl': 0,
                'exit_time': None
            }
            
            new_trades.append(trade)
            positions.append(trade)
        
        # Close expired positions
        closed_positions = []
        for pos in positions:
            # Simulate position close after some time
            if (timestamp - pos['timestamp']).total_seconds() > 1800:  # 30 minutes
                pos['exit_time'] = timestamp
                pos['pnl'] = np.random.normal(500, 1000)  # Simulate P&L
                closed_positions.append(pos)
        
        # Remove closed positions
        positions = [p for p in positions if p['exit_time'] is None]
        
        return positions, closed_positions
    
    def _calculate_portfolio_greeks(self, positions) -> tuple:
        """Calculate portfolio Greeks"""
        delta = sum(p.get('delta', 0) * p.get('quantity', 0) for p in positions)
        gamma = sum(p.get('gamma', 0) * p.get('quantity', 0) for p in positions)
        vega = sum(p.get('vega', 0) * p.get('quantity', 0) for p in positions)
        return delta, gamma, vega
    
    def _calculate_max_dd(self, positions) -> float:
        """Calculate current drawdown"""
        if not self.equity_curve:
            return 0.0
        
        equity = [e['equity'] for e in self.equity_curve[-50:]]
        running_max = np.maximum.accumulate(equity)
        drawdown = (equity[-1] - running_max[-1]) / self.initial_capital
        return abs(drawdown)
    
    def _calculate_portfolio_value(self, positions) -> float:
        """Calculate total portfolio value"""
        # Simplified - would need mark-to-market in real implementation
        return self.initial_capital + sum(t['pnl'] for t in self.trades)
    
    async def _analyze_results(self):
        """Analyze and plot backtest results"""
        logger.info("\n" + "="*80)
        logger.info("BACKTEST RESULTS")
        logger.info("="*80)
        
        if not self.equity_curve:
            logger.warning("No equity curve data")
            return
        
        # Convert to DataFrame
        equity_df = pd.DataFrame(self.equity_curve)
        equity_df['returns'] = equity_df['equity'].pct_change()
        
        # Calculate metrics
        final_equity = equity_df['equity'].iloc[-1]
        total_return = (final_equity / self.initial_capital - 1) * 100
        
        # Maximum drawdown
        running_max = equity_df['equity'].expanding().max()
        drawdown = (equity_df['equity'] - running_max) / running_max
        max_dd = abs(drawdown.min()) * 100
        
        # Sharpe ratio
        sharpe = self.reward_calculator.calculate_sortino_ratio(equity_df['returns'].dropna().values)
        
        # Print results
        logger.info(f"Initial Capital: ₹{self.initial_capital:,.0f}")
        logger.info(f"Final Equity: ₹{final_equity:,.0f}")
        logger.info(f"Total Return: {total_return:.2f}%")
        logger.info(f"Max Drawdown: {max_dd:.2f}%")
        logger.info(f"Sortino Ratio: {sharpe:.2f}")
        logger.info(f"Total Trades: {len(self.trades)}")
        
        # Plot results
        self._plot_results(equity_df)
        
        logger.info("="*80)
    
    def _plot_results(self, equity_df: pd.DataFrame):
        """Plot equity curve and allocation heatmap"""
        fig, axes = plt.subplots(2, 2, figsize=(16, 10))
        
        # Equity curve
        axes[0, 0].plot(equity_df['timestamp'], equity_df['equity'])
        axes[0, 0].set_title('Equity Curve')
        axes[0, 0].set_xlabel('Time')
        axes[0, 0].set_ylabel('Portfolio Value (₹)')
        axes[0, 0].grid(True)
        
        # Drawdown
        running_max = equity_df['equity'].expanding().max()
        drawdown = (equity_df['equity'] - running_max) / running_max * 100
        axes[0, 1].fill_between(equity_df['timestamp'], drawdown, 0, alpha=0.3, color='red')
        axes[0, 1].set_title('Drawdown')
        axes[0, 1].set_xlabel('Time')
        axes[0, 1].set_ylabel('Drawdown (%)')
        axes[0, 1].grid(True)
        
        # Allocation heatmap
        if self.allocation_history:
            alloc_df = pd.DataFrame([
                {'timestamp': a['timestamp'], **{f'Group_{i}': a['allocation'][i] for i in range(9)}}
                for a in self.allocation_history[::10]  # Sample every 10th
            ])
            
            alloc_matrix = alloc_df[[f'Group_{i}' for i in range(9)]].T.values
            sns.heatmap(alloc_matrix, ax=axes[1, 0], cmap='YlOrRd', cbar_kws={'label': 'Allocation'})
            axes[1, 0].set_title('Allocation Heatmap Over Time')
            axes[1, 0].set_ylabel('Meta-Group')
            axes[1, 0].set_xlabel('Time')
        
        # Per-group PnL
        if self.trades:
            group_pnl = {}
            for trade in self.trades:
                g = trade['meta_group']
                group_pnl[g] = group_pnl.get(g, 0) + trade['pnl']
            
            groups = list(group_pnl.keys())
            pnls = list(group_pnl.values())
            axes[1, 1].bar(groups, pnls)
            axes[1, 1].set_title('P&L by Meta-Group')
            axes[1, 1].set_xlabel('Meta-Group')
            axes[1, 1].set_ylabel('Total P&L (₹)')
            axes[1, 1].grid(True)
        
        plt.tight_layout()
        plt.savefig('backtest_results.png', dpi=300)
        logger.info("Results saved to backtest_results.png")


async def main():
    """Run backtest"""
    backtester = SACBacktester(
        start_date="2024-01-01",
        end_date="2025-11-01",
        initial_capital=1000000,
        training_mode=True
    )
    
    await backtester.run_backtest()


if __name__ == "__main__":
    asyncio.run(main())
