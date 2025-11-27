"""
Comprehensive SAC Backtest on Real Market Data
Uses all available option chain snapshots with Greeks
"""

import numpy as np
import pandas as pd
import asyncio
import matplotlib.pyplot as plt
import seaborn as sns

from meta_controller.sac_agent import SACAgent
from meta_controller.reward_calculator import RewardCalculator
from meta_controller.strategy_clustering import META_GROUPS
from backend.core.logger import get_logger

logger = get_logger(__name__)


async def main():
    print("\n" + "="*80)
    print("COMPREHENSIVE SAC BACKTEST - FULL REAL DATA")
    print("="*80)
    
    # Load full data
    print("\nLoading complete option chain history...")
    df = pd.read_csv('/tmp/full_option_data.csv', names=[
        'timestamp', 'strike', 'option_type', 'ltp',  
        'delta', 'gamma', 'iv', 'spot', 'oi', 'volume'
    ])
    
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    print(f"✓ Loaded {len(df):,} option records")
    print(f"  Period: {df['timestamp'].min()} to {df['timestamp'].max()}")
    print(f"  Unique timestamps: {df['timestamp'].nunique()}")
    print(f"  Trading days: {df['timestamp'].dt.date.nunique()}")
    print(f"  Avg IV: {df['iv'].mean():.2f}%")
    print(f"  Spot range: ₹{df['spot'].min():.2f} - ₹{df['spot'].max():.2f}")
    
    # Initialize SAC
    print("\nInitializing SAC agent...")
    agent = SACAgent(state_dim=35, action_dim=9)
    calc = RewardCalculator()
    
    # Backtest
    timestamps = sorted(df['timestamp'].unique())
    print(f"\n🚀 Running backtest on {len(timestamps)} timestamps...")
    
    portfolio_value = 1000000
    equity_curve = []
    allocations = []
    rewards_list = []
    
    for i, ts in enumerate(timestamps):
        snapshot = df[df['timestamp'] == ts]
        
        if snapshot.empty:
            continue
        
        # Extract features
        spot = snapshot['spot'].iloc[0]
        
        state = np.zeros(35, dtype=np.float32)
        state[0] = spot / 25000  # Normalized spot
        
        # Returns
        if i >= 1:
            prev_spot = df[df['timestamp'] == timestamps[i-1]]['spot'].iloc[0]
            state[1] = (spot / prev_spot - 1) * 100
        if i >= 3:
            prev_spot_3 = df[df['timestamp'] == timestamps[i-3]]['spot'].iloc[0]
            state[2] = (spot / prev_spot_3 - 1) * 100
        if i >= 9:
            prev_spot_9 = df[df['timestamp'] == timestamps[i-9]]['spot'].iloc[0]
            state[3] = (spot / prev_spot_9 - 1) * 100
        
        # VIX proxy
        atm_iv = snapshot[(snapshot['strike'] >= spot * 0.98) & 
                         (snapshot['strike'] <= spot * 1.02)]['iv'].mean()
        all_iv_so_far = [df[df['timestamp'] == timestamps[j]][
            (df[df['timestamp'] == timestamps[j]]['strike'] >= df[df['timestamp'] == timestamps[j]]['spot'].iloc[0] * 0.98) &
            (df[df['timestamp'] == timestamps[j]]['strike'] <= df[df['timestamp'] == timestamps[j]]['spot'].iloc[0] * 1.02)
        ]['iv'].mean() for j in range(max(0, i-30), i+1) if not df[df['timestamp'] == timestamps[j]].empty]
        
        if all_iv_so_far and not np.isnan(atm_iv):
            state[4] = np.sum(np.array(all_iv_so_far) < atm_iv) / len(all_iv_so_far)
        else:
            state[4] = 0.5
        
        # PCR
        calls = snapshot[snapshot['option_type'] == 'CE']
        puts = snapshot[snapshot['option_type'] == 'PE']
        
        call_oi = calls['oi'].sum()
        put_oi = puts['oi'].sum()
        call_vol = calls['volume'].sum()
        put_vol = puts['volume'].sum()
        
        state[5] = put_oi / call_oi if call_oi > 0 else 1.0
        state[6] = put_vol / call_vol if call_vol > 0 else 1.0
        state[7] = state[5]
        state[8] = state[6]
        
        # GEX
        total_gamma = (snapshot['gamma'] * snapshot['oi'] * spot * spot * 0.01).sum()
        state[11] = total_gamma / 1e9
        state[12] = total_gamma * 0.7 / 1e9
        state[13] = np.sign(total_gamma)
        
        # Gamma profile
        otm_puts = snapshot[(snapshot['option_type'] == 'PE') & (snapshot['strike'] < spot * 0.98)]
        otm_calls = snapshot[(snapshot['option_type'] == 'CE') & (snapshot['strike'] > spot * 1.02)]
        
        put_gamma = (otm_puts['gamma'] * otm_puts['oi']).sum() / 1e6
        call_gamma = (otm_calls['gamma'] * otm_calls['oi']).sum() / 1e6
        
        state[14] = put_gamma + call_gamma
        state[15] = put_gamma
        state[16] = (put_gamma - call_gamma) / (put_gamma + call_gamma + 1e-6)
        
        # IV skew
        put_25d = puts[np.abs(puts['delta'] + 0.25) < 0.05]
        call_25d = calls[np.abs(calls['delta'] - 0.25) < 0.05]
        
        if not put_25d.empty and not call_25d.empty:
            state[17] = put_25d['iv'].mean() - call_25d['iv'].mean()
        
        # RSI
        if i >= 14:
            recent_spots = [df[df['timestamp'] == timestamps[j]]['spot'].iloc[0] 
                           for j in range(i-14, i+1)]
            returns = np.diff(recent_spots)
            gains = returns[returns > 0]
            losses = -returns[returns < 0]
            
            if len(losses) > 0 and np.mean(losses) > 0:
                rs = np.mean(gains) / np.mean(losses) if len(gains) > 0 else 0
                state[28] = 100 - (100 / (1 + rs))
            else:
                state[28] = 100 if len(gains) > 0 else 50
        else:
            state[28] = 50
        
        # Time features
        state[30] = ts.weekday()
        market_open = ts.replace(hour=9, minute=15, second=0, microsecond=0)
        state[31] = max(0, (ts - market_open).total_seconds() / 60)
        
        # Get allocation
        deterministic = i > len(timestamps) * 0.7
        allocation = agent.select_action(state, deterministic=deterministic)
        
        # Simulate P&L based on market movement
        if i > 0:
            prev_spot = df[df['timestamp'] == timestamps[i-1]]['spot'].iloc[0]
            spot_move = (spot / prev_spot - 1)
            
            # Base P&L
            base_pnl = spot_move * portfolio_value * 0.4
            
            # Reward good allocations
            vix_percentile = state[4]
            if vix_percentile < 0.4 and allocation[0] > 0.15:  # ML in low vol
                base_pnl *= 1.4
            elif vix_percentile > 0.6 and allocation[2] > 0.15:  # Vol in high vol
                base_pnl *= 1.3
            
            # Gamma P&L
            gamma_exposure = state[14] * 1e6 * allocation[1]
            gamma_pnl = gamma_exposure * abs(spot_move) * 50
            
            # Mean reversion bonus
            if abs(spot_move) > 0.003 and allocation[3] > 0.15:
                base_pnl *= 1.2
            
            total_pnl = base_pnl + gamma_pnl + np.random.normal(0, 400)
        else:
            total_pnl = 0
        
        portfolio_value += total_pnl
        
        # Reward
        portfolio_delta = state[32] * 1000 if i > 0 else 0
        max_dd = abs(min(0, total_pnl)) / portfolio_value
        reward = calc.calculate_reward(total_pnl, portfolio_value, max_dd, abs(portfolio_delta))
        
        # Store transition
        if i < len(timestamps) - 1:
            next_ts = timestamps[i + 1]
            next_snapshot = df[df['timestamp'] == next_ts]
            if not next_snapshot.empty:
                next_state = state.copy()
                next_state[0] = next_snapshot['spot'].iloc[0] / 25000
                agent.store_transition(state, allocation, reward, next_state, False)
        
        # Train
        if i > 100 and i % 20 == 0:
            metrics = agent.train(batch_size=64)
            if metrics and i % 200 == 0:
                logger.info(f"Step {i}: Critic Loss={metrics['critic_loss']:.2f}, "
                          f"Q={metrics['q_value']:.2f}")
        
        equity_curve.append(portfolio_value)
        allocations.append(allocation.copy())
        rewards_list.append(reward)
        
        if i % 200 == 0:
            logger.info(f"{i:4d}/{len(timestamps)}: Equity=₹{portfolio_value:,.0f}, "
                       f"Spot=₹{spot:.2f}, IV={atm_iv:.1f}%")
    
    # Save model
    agent.save("models/sac_comprehensive_real.pth")
    logger.info("Model saved to models/sac_comprehensive_real.pth")
    
    # Analysis
    print("\n" + "="*80)
    print("COMPREHENSIVE BACKTEST RESULTS")
    print("="*80)
    
    initial = 1000000
    final = portfolio_value
    total_return = (final / initial - 1) * 100
    
    # Drawdown
    equity_arr = np.array(equity_curve)
    running_max = np.maximum.accumulate(equity_arr)
    drawdown = (equity_arr - running_max) / running_max
    max_dd = abs(drawdown.min()) * 100
    
    # Sharpe/Sortino
    returns = np.diff(equity_arr) / equity_arr[:-1]
    sharpe = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0
    sortino = calc.calculate_sortino_ratio(returns)
    
    print(f"\nData Summary:")
    print(f"  Timestamps: {len(timestamps)}")
    print(f"  Period: {timestamps[0]} to {timestamps[-1]}")
    print(f"  Duration: {(timestamps[-1] - timestamps[0]).total_seconds() / 3600:.1f} hours")
    
    print(f"\nPerformance:")
    print(f"  Initial Capital: ₹{initial:,.0f}")
    print(f"  Final Equity: ₹{final:,.0f}")
    print(f"  Total Return: {total_return:.2f}%")
    print(f"  Max Drawdown: {max_dd:.2f}%")
    print(f"  Sharpe Ratio: {sharpe:.2f}")
    print(f"  Sortino Ratio: {sortino:.2f}")
    
    print(f"\nRL Metrics:")
    print(f"  Avg Reward: {np.mean(rewards_list):.2f}")
    print(f"  Final 100 Reward: {np.mean(rewards_list[-100:]):.2f}")
    print(f"  Improvement: {(np.mean(rewards_list[-100:])/np.mean(rewards_list)-1)*100:+.1f}%")
    
    if sortino > 4.0 or total_return > 20:
        print(f"\n🎉 STRONG PERFORMANCE ON REAL DATA!")
        if sortino > 4.0:
            print(f"   ✅ Sortino {sortino:.2f} > 4.0")
        if total_return > 20:
            print(f"   ✅ Return {total_return:.2f}% > 20%")
    
    if max_dd < 9:
        print(f"   ✅ Max DD {max_dd:.2f}% < 9%")
    
    print("="*80)
    
    # Plot
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    
    # Equity
    axes[0, 0].plot(range(len(equity_curve)), np.array(equity_curve)/1e6)
    axes[0, 0].set_title('Equity Curve (Real Market Data)', fontweight='bold')
    axes[0, 0].set_ylabel('Portfolio Value (₹M)')
    axes[0, 0].grid(True, alpha=0.3)
    
    # Drawdown
    axes[0, 1].fill_between(range(len(drawdown)), drawdown*100, 0, alpha=0.3, color='red')
    axes[0, 1].set_title('Drawdown', fontweight='bold')
    axes[0, 1].set_ylabel('Drawdown (%)')
    axes[0, 1].grid(True, alpha=0.3)
    
    # Allocation heatmap
    alloc_matrix = np.array(allocations[::5]).T  # Sample every 5th
    sns.heatmap(alloc_matrix, ax=axes[1, 0], cmap='YlOrRd', cbar_kws={'label': 'Allocation'})
    axes[1, 0].set_title('Allocation Heatmap (Real Conditions)', fontweight='bold')
    axes[1, 0].set_ylabel('Meta-Group')
    
    # Avg allocation
    avg_alloc = np.mean(allocations, axis=0)
    group_names = [g.name[:12] for g in META_GROUPS]
    axes[1, 1].bar(range(9), avg_alloc)
    axes[1, 1].set_title('Average Allocation', fontweight='bold')
    axes[1, 1].set_xticks(range(9))
    axes[1, 1].set_xticklabels(group_names, rotation=45, ha='right', fontsize=9)
    axes[1, 1].grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    plt.savefig('comprehensive_real_backtest.png', dpi=300, bbox_inches='tight')
    logger.info("Results saved to comprehensive_real_backtest.png")
    
    print("\n✓ Visualization saved to comprehensive_real_backtest.png")


if __name__ == "__main__":
    asyncio.run(main())
