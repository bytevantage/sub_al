"""
Demo SAC Backtest - Works without historical data
Generates synthetic market conditions to demonstrate the system
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import asyncio
import matplotlib.pyplot as plt
import seaborn as sns

from meta_controller.sac_agent import SACAgent
from meta_controller.state_builder import StateBuilder
from meta_controller.strategy_zoo import StrategyZoo
from meta_controller.reward_calculator import RewardCalculator
from meta_controller.strategy_clustering import print_clustering
from backend.core.logger import get_logger

logger = get_logger(__name__)


class DemoSACBacktester:
    """Demo backtest with synthetic data"""
    
    def __init__(self, num_episodes: int = 1000, initial_capital: float = 1000000):
        self.num_episodes = num_episodes
        self.initial_capital = initial_capital
        self.portfolio_value = initial_capital
        
        # Initialize components
        self.agent = SACAgent(state_dim=35, action_dim=9)
        self.reward_calculator = RewardCalculator()
        
        # Results storage
        self.equity_curve = []
        self.allocations = []
        self.rewards = []
        self.training_metrics = []
        
        logger.info(f"Demo backtest initialized: {num_episodes} episodes")
        
    def generate_synthetic_state(self, episode: int) -> np.ndarray:
        """Generate synthetic 35-dim state vector"""
        # Create realistic market state with trends
        t = episode / self.num_episodes
        
        # Base features with some autocorrelation
        state = np.zeros(35, dtype=np.float32)
        
        # Spot price features (0-3)
        state[0] = 1.0 + 0.1 * np.sin(2 * np.pi * t * 5)  # Spot normalized
        state[1] = np.random.normal(0, 0.5)  # 1-bar return
        state[2] = np.random.normal(0, 1.0)  # 3-bar return
        state[3] = np.random.normal(0, 1.5)  # 9-bar return
        
        # VIX percentile (4)
        state[4] = 0.3 + 0.4 * np.sin(2 * np.pi * t * 3)  # Cycles between 0.3-0.7
        
        # PCR metrics (5-8)
        state[5:9] = np.random.uniform(0.8, 1.2, 4)  # PCR ratios
        
        # Max pain (9-10)
        state[9] = np.random.normal(0, 2)  # Distance
        state[10] = 1.0
        
        # GEX features (11-13)
        state[11] = np.random.normal(0, 0.5)  # Total GEX
        state[12] = np.random.normal(0, 0.3)  # Near GEX
        state[13] = np.random.choice([-1, 0, 1])  # Direction
        
        # Gamma profile (14-16)
        state[14:17] = np.random.normal(0, 0.3, 3)
        
        # IV features (17-18)
        state[17] = np.random.normal(0, 1)  # IV skew
        state[18] = np.random.normal(0, 0.5)  # Term slope
        
        # OI changes (19-24)
        state[19:25] = np.random.normal(0, 2, 6)
        
        # VWAP Z-score (25)
        state[25] = np.random.normal(0, 1)
        
        # Technicals (26-28)
        state[26] = np.random.uniform(15, 35)  # ADX
        state[27] = np.random.uniform(0.5, 2.5)  # ATR
        state[28] = np.random.uniform(30, 70)  # RSI
        
        # Time features (29-31)
        state[29] = np.random.uniform(24, 168)  # Hours to expiry
        state[30] = episode % 5  # Day of week
        state[31] = np.random.uniform(0, 375)  # Minutes since open
        
        # Portfolio Greeks (32-34)
        state[32] = np.random.normal(0, 0.5)  # Delta
        state[33] = np.random.normal(0, 0.3)  # Gamma
        state[34] = np.random.normal(0, 0.4)  # Vega
        
        return state
    
    def simulate_pnl(self, state: np.ndarray, allocation: np.ndarray) -> float:
        """
        Simulate P&L based on state and allocation
        
        Reward good strategies:
        - High allocation to ML_PREDICTION (group 0) when VIX is low
        - High allocation to VOLATILITY_TRADING (group 2) when VIX is high
        - Diversification bonus
        """
        # Extract key features
        vix_percentile = state[4]
        rsi = state[28]
        spot_return = state[1]
        
        # Base P&L from market conditions
        base_pnl = np.random.normal(0, 1000)
        
        # Reward optimal allocations
        optimal_score = 0.0
        
        # Low VIX → favor ML_PREDICTION (group 0) and MOMENTUM (group 4)
        if vix_percentile < 0.4:
            optimal_score += allocation[0] * 2.0  # ML prediction
            optimal_score += allocation[4] * 1.5  # Momentum
        
        # High VIX → favor VOLATILITY_TRADING (group 2) and MEAN_REVERSION (group 3)
        elif vix_percentile > 0.6:
            optimal_score += allocation[2] * 2.0  # Volatility trading
            optimal_score += allocation[3] * 1.5  # Mean reversion
        
        # Medium VIX → balanced
        else:
            optimal_score += np.sum(allocation * 0.8)
        
        # Diversification bonus (Shannon entropy)
        allocation_clean = allocation + 1e-10
        entropy = -np.sum(allocation_clean * np.log(allocation_clean))
        diversification_bonus = entropy * 200
        
        # Combine
        strategy_pnl = optimal_score * 500 + diversification_bonus
        
        # Add market-based component
        if spot_return > 0 and allocation[0] > 0.2:  # ML caught the move
            strategy_pnl += 800
        elif spot_return < 0 and allocation[3] > 0.2:  # Mean reversion helped
            strategy_pnl += 600
        
        total_pnl = base_pnl + strategy_pnl
        
        # Add some noise
        total_pnl += np.random.normal(0, 500)
        
        return total_pnl
    
    def calculate_reward(self, pnl: float, portfolio_delta: float) -> float:
        """Calculate reward from P&L"""
        # Simulate drawdown
        max_dd = abs(min(0, pnl)) / self.portfolio_value
        
        # Use reward calculator
        reward = self.reward_calculator.calculate_reward(
            realized_pnl=pnl,
            portfolio_value=self.portfolio_value,
            max_drawdown=max_dd,
            portfolio_delta=abs(portfolio_delta)
        )
        
        return reward
    
    async def run_backtest(self):
        """Run demo backtest"""
        print("\n" + "="*80)
        print("SAC DEMO BACKTEST - SYNTHETIC DATA")
        print("="*80)
        print_clustering()
        print()
        
        logger.info(f"Starting demo backtest: {self.num_episodes} episodes")
        logger.info(f"Initial capital: ₹{self.initial_capital:,.0f}")
        
        # Training loop
        for episode in range(self.num_episodes):
            # Generate state
            state = self.generate_synthetic_state(episode)
            
            # Select action
            deterministic = episode > self.num_episodes * 0.8  # Deterministic after 80%
            allocation = self.agent.select_action(state, deterministic=deterministic)
            
            # Simulate P&L
            pnl = self.simulate_pnl(state, allocation)
            
            # Update portfolio
            self.portfolio_value += pnl
            
            # Calculate reward
            portfolio_delta = state[32] * 1000  # De-normalize
            reward = self.calculate_reward(pnl, portfolio_delta)
            
            # Generate next state
            next_state = self.generate_synthetic_state(episode + 1)
            
            # Store transition
            self.agent.store_transition(state, allocation, reward, next_state, False)
            
            # Train
            if episode > 100 and episode % 5 == 0:
                metrics = self.agent.train(batch_size=64)
                if metrics:
                    self.training_metrics.append(metrics)
            
            # Store results
            self.equity_curve.append({
                'episode': episode,
                'equity': self.portfolio_value,
                'pnl': pnl
            })
            self.allocations.append(allocation.copy())
            self.rewards.append(reward)
            
            # Progress
            if episode % 100 == 0:
                avg_reward = np.mean(self.rewards[-100:]) if len(self.rewards) >= 100 else np.mean(self.rewards)
                logger.info(f"Episode {episode}/{self.num_episodes}: "
                          f"Equity=₹{self.portfolio_value:,.0f}, "
                          f"Avg Reward={avg_reward:.4f}")
        
        # Save model
        self.agent.save("models/sac_meta_controller_demo.pth")
        logger.info("Model saved to models/sac_meta_controller_demo.pth")
        
        # Analyze results
        await self._analyze_results()
    
    async def _analyze_results(self):
        """Analyze and plot results"""
        print("\n" + "="*80)
        print("DEMO BACKTEST RESULTS")
        print("="*80)
        
        # Convert to DataFrame
        equity_df = pd.DataFrame(self.equity_curve)
        
        # Calculate metrics
        final_equity = equity_df['equity'].iloc[-1]
        total_return = (final_equity / self.initial_capital - 1) * 100
        
        # Drawdown
        running_max = equity_df['equity'].expanding().max()
        drawdown = (equity_df['equity'] - running_max) / running_max
        max_dd = abs(drawdown.min()) * 100
        
        # Returns
        equity_df['returns'] = equity_df['equity'].pct_change()
        
        # Sharpe/Sortino
        returns = equity_df['returns'].dropna()
        sharpe = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0
        sortino = self.reward_calculator.calculate_sortino_ratio(returns.values)
        
        # Reward metrics
        avg_reward = np.mean(self.rewards)
        final_reward = np.mean(self.rewards[-100:])
        
        # Print results
        print(f"\nInitial Capital: ₹{self.initial_capital:,.0f}")
        print(f"Final Equity: ₹{final_equity:,.0f}")
        print(f"Total Return: {total_return:.2f}%")
        print(f"Max Drawdown: {max_dd:.2f}%")
        print(f"Sharpe Ratio: {sharpe:.2f}")
        print(f"Sortino Ratio: {sortino:.2f}")
        print(f"\nAverage Reward: {avg_reward:.4f}")
        print(f"Final 100 Episodes Reward: {final_reward:.4f}")
        print(f"Improvement: {((final_reward/avg_reward - 1) * 100):+.1f}%")
        
        # Plot results
        self._plot_results(equity_df)
        
        # Performance summary
        if sortino > 4.0 and max_dd < 9:
            print("\n🎉 TARGET PERFORMANCE ACHIEVED!")
            print(f"   ✅ Sortino {sortino:.2f} > 4.0")
            print(f"   ✅ Max DD {max_dd:.2f}% < 9%")
        else:
            print(f"\n📊 Performance:")
            print(f"   Sortino {sortino:.2f} (target: >4.0)")
            print(f"   Max DD {max_dd:.2f}% (target: <9%)")
        
        print("="*80)
    
    def _plot_results(self, equity_df: pd.DataFrame):
        """Plot results"""
        fig, axes = plt.subplots(2, 3, figsize=(18, 10))
        
        # Equity curve
        axes[0, 0].plot(equity_df['episode'], equity_df['equity'] / 1e6)
        axes[0, 0].axhline(y=self.initial_capital/1e6, color='r', linestyle='--', alpha=0.5)
        axes[0, 0].set_title('Equity Curve', fontsize=12, fontweight='bold')
        axes[0, 0].set_xlabel('Episode')
        axes[0, 0].set_ylabel('Portfolio Value (₹ millions)')
        axes[0, 0].grid(True, alpha=0.3)
        
        # Drawdown
        running_max = equity_df['equity'].expanding().max()
        drawdown = (equity_df['equity'] - running_max) / running_max * 100
        axes[0, 1].fill_between(equity_df['episode'], drawdown, 0, alpha=0.3, color='red')
        axes[0, 1].set_title('Drawdown', fontsize=12, fontweight='bold')
        axes[0, 1].set_xlabel('Episode')
        axes[0, 1].set_ylabel('Drawdown (%)')
        axes[0, 1].grid(True, alpha=0.3)
        
        # Rewards
        window = 50
        smoothed_rewards = pd.Series(self.rewards).rolling(window).mean()
        axes[0, 2].plot(smoothed_rewards, alpha=0.7)
        axes[0, 2].set_title(f'Rewards (Smoothed, window={window})', fontsize=12, fontweight='bold')
        axes[0, 2].set_xlabel('Episode')
        axes[0, 2].set_ylabel('Reward')
        axes[0, 2].grid(True, alpha=0.3)
        
        # Allocation heatmap
        alloc_matrix = np.array(self.allocations[::10]).T  # Sample every 10th
        sns.heatmap(alloc_matrix, ax=axes[1, 0], cmap='YlOrRd', cbar_kws={'label': 'Allocation'})
        axes[1, 0].set_title('Allocation Heatmap Over Time', fontsize=12, fontweight='bold')
        axes[1, 0].set_ylabel('Meta-Group')
        axes[1, 0].set_xlabel('Episode (sampled)')
        
        # Average allocation per group
        avg_alloc = np.mean(self.allocations, axis=0)
        from meta_controller.strategy_clustering import META_GROUPS
        group_names = [g.name[:15] for g in META_GROUPS]
        axes[1, 1].bar(range(9), avg_alloc)
        axes[1, 1].set_title('Average Allocation by Meta-Group', fontsize=12, fontweight='bold')
        axes[1, 1].set_xlabel('Meta-Group')
        axes[1, 1].set_ylabel('Average Allocation')
        axes[1, 1].set_xticks(range(9))
        axes[1, 1].set_xticklabels(group_names, rotation=45, ha='right', fontsize=8)
        axes[1, 1].grid(True, alpha=0.3, axis='y')
        
        # Training metrics
        if self.training_metrics:
            critic_losses = [m['critic_loss'] for m in self.training_metrics]
            axes[1, 2].plot(critic_losses, alpha=0.7)
            axes[1, 2].set_title('Critic Loss During Training', fontsize=12, fontweight='bold')
            axes[1, 2].set_xlabel('Training Step')
            axes[1, 2].set_ylabel('Critic Loss')
            axes[1, 2].grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig('demo_sac_backtest_results.png', dpi=300, bbox_inches='tight')
        logger.info("Results saved to demo_sac_backtest_results.png")
        plt.close()


async def main():
    """Run demo backtest"""
    backtester = DemoSACBacktester(
        num_episodes=1000,
        initial_capital=1000000
    )
    
    await backtester.run_backtest()


if __name__ == "__main__":
    asyncio.run(main())
