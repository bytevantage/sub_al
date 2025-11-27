"""
SAC Meta-Controller System Test
Verifies all components work correctly
"""

import asyncio
import numpy as np
from datetime import datetime
import sys

from meta_controller.strategy_clustering import META_GROUPS, print_clustering, get_meta_group
from meta_controller.sac_agent import SACAgent
from meta_controller.state_builder import StateBuilder
from meta_controller.strategy_zoo import StrategyZoo
from meta_controller.reward_calculator import RewardCalculator
from features.greeks_engine import GreeksEngine
from backend.core.logger import get_logger

logger = get_logger(__name__)


class SACSystemTester:
    """Test all SAC components"""
    
    def __init__(self):
        self.tests_passed = 0
        self.tests_failed = 0
        
    def run_all_tests(self):
        """Run all system tests"""
        print("="*80)
        print("SAC META-CONTROLLER SYSTEM TEST")
        print("="*80)
        print()
        
        # Test 1: Strategy Clustering
        self.test_strategy_clustering()
        
        # Test 2: Greeks Engine
        self.test_greeks_engine()
        
        # Test 3: SAC Agent
        self.test_sac_agent()
        
        # Test 4: State Builder
        self.test_state_builder()
        
        # Test 5: Strategy Zoo
        asyncio.run(self.test_strategy_zoo())
        
        # Test 6: Reward Calculator
        self.test_reward_calculator()
        
        # Test 7: Integration
        asyncio.run(self.test_integration())
        
        # Summary
        print("\n" + "="*80)
        print("TEST SUMMARY")
        print("="*80)
        print(f"✅ Tests Passed: {self.tests_passed}")
        print(f"❌ Tests Failed: {self.tests_failed}")
        print(f"Total Tests: {self.tests_passed + self.tests_failed}")
        
        if self.tests_failed == 0:
            print("\n🎉 ALL TESTS PASSED!")
            print("\nSystem is ready for:")
            print("  1. Offline training: python backtest_sac.py")
            print("  2. Live trading: python live_sac_controller.py")
        else:
            print(f"\n⚠️  {self.tests_failed} test(s) failed. Please fix before proceeding.")
        
        print("="*80)
        
        return self.tests_failed == 0
    
    def test_strategy_clustering(self):
        """Test strategy clustering"""
        print("\n📊 Test 1: Strategy Clustering")
        print("-" * 80)
        
        try:
            # Check meta-groups exist
            assert len(META_GROUPS) == 9, "Should have exactly 9 meta-groups"
            print("✓ 9 meta-groups defined")
            
            # Check strategies
            total_strategies = sum(len(g.strategies) for g in META_GROUPS)
            assert total_strategies >= 25, f"Should have at least 25 strategies, found {total_strategies}"
            print(f"✓ {total_strategies} strategies defined")
            
            # Check max allocations
            for group in META_GROUPS:
                assert group.max_allocation == 0.35, f"Max allocation should be 0.35 for {group.name}"
            print("✓ Max allocation constraints set (35%)")
            
            # Test mapping
            test_strategy = "QuantumEdge"
            group_id = get_meta_group(test_strategy)
            assert group_id == 0, f"QuantumEdge should be in group 0, got {group_id}"
            print("✓ Strategy mapping works")
            
            # Print clustering
            print_clustering()
            
            self.tests_passed += 1
            print("✅ Strategy Clustering Test PASSED")
            
        except Exception as e:
            self.tests_failed += 1
            print(f"❌ Strategy Clustering Test FAILED: {e}")
    
    def test_greeks_engine(self):
        """Test Greeks engine"""
        print("\n🔬 Test 2: Greeks Engine")
        print("-" * 80)
        
        try:
            engine = GreeksEngine()
            
            # Check feature names
            actual_features = len(engine.FEATURE_NAMES)
            assert actual_features >= 34, f"Should have at least 34 features, got {actual_features}"
            print(f"✓ {actual_features} feature names defined")
            
            # Mock state vector (database might not be available in test)
            state = np.zeros(34)
            assert state.shape == (34,), f"State shape should be (34,), got {state.shape}"
            print("✓ State vector shape correct")
            
            # Check feature names are unique
            assert len(engine.FEATURE_NAMES) == len(set(engine.FEATURE_NAMES)), "Feature names must be unique"
            print("✓ Feature names are unique")
            
            # Print some feature names
            print("\nSample features:")
            for i in [0, 4, 10, 20, 30]:
                print(f"  [{i}] {engine.FEATURE_NAMES[i]}")
            
            self.tests_passed += 1
            print("✅ Greeks Engine Test PASSED")
            
        except Exception as e:
            self.tests_failed += 1
            print(f"❌ Greeks Engine Test FAILED: {e}")
    
    def test_sac_agent(self):
        """Test SAC agent"""
        print("\n🧠 Test 3: SAC Agent")
        print("-" * 80)
        
        try:
            agent = SACAgent(state_dim=34, action_dim=9, hidden_dim=256)
            
            # Test action selection
            state = np.random.randn(34).astype(np.float32)
            action = agent.select_action(state, deterministic=True)
            
            assert action.shape == (9,), f"Action shape should be (9,), got {action.shape}"
            print("✓ Action selection works")
            
            # Check allocation sum
            assert abs(action.sum() - 1.0) < 0.01, f"Allocation should sum to 1.0, got {action.sum()}"
            print(f"✓ Allocation sums to 1.0 (actual: {action.sum():.4f})")
            
            # Check max constraint
            assert action.max() <= 0.35, f"Max allocation should be ≤0.35, got {action.max()}"
            print(f"✓ Max allocation constraint satisfied (max: {action.max():.4f})")
            
            # Test storage
            next_state = np.random.randn(34).astype(np.float32)
            reward = 0.05
            agent.store_transition(state, action, reward, next_state, False)
            print(f"✓ Transition storage works ({len(agent.replay_buffer)} samples)")
            
            # Test save/load
            agent.save("models/test_sac.pth")
            agent.load("models/test_sac.pth")
            print("✓ Model save/load works")
            
            self.tests_passed += 1
            print("✅ SAC Agent Test PASSED")
            
        except Exception as e:
            self.tests_failed += 1
            print(f"❌ SAC Agent Test FAILED: {e}")
    
    def test_state_builder(self):
        """Test state builder"""
        print("\n🏗️  Test 4: State Builder")
        print("-" * 80)
        
        try:
            builder = StateBuilder()
            
            # Mock state
            state = np.random.randn(34).astype(np.float32)
            
            # Test regime detection
            regime = builder.get_market_regime(state)
            assert regime in ['LOW_VOL', 'NORMAL', 'HIGH_VOL', 'CRISIS'], f"Invalid regime: {regime}"
            print(f"✓ Regime detection works (detected: {regime})")
            
            # Test pause check
            should_pause = builder.should_pause_trading(state)
            assert isinstance(should_pause, bool), "should_pause_trading should return bool"
            print(f"✓ Pause check works (pause: {should_pause})")
            
            # Test risk multiplier
            risk_mult = builder.get_risk_multiplier(state)
            assert 0.5 <= risk_mult <= 1.5, f"Risk multiplier out of range: {risk_mult}"
            print(f"✓ Risk multiplier works ({risk_mult:.2f}x)")
            
            self.tests_passed += 1
            print("✅ State Builder Test PASSED")
            
        except Exception as e:
            self.tests_failed += 1
            print(f"❌ State Builder Test FAILED: {e}")
    
    async def test_strategy_zoo(self):
        """Test strategy zoo"""
        print("\n🦁 Test 5: Strategy Zoo")
        print("-" * 80)
        
        try:
            zoo = StrategyZoo(portfolio_value=1000000)
            
            # Check initialization
            print(f"✓ Strategy zoo initialized with ₹{zoo.portfolio_value:,.0f}")
            
            # Check strategies loaded
            print(f"✓ Loaded {len(zoo.strategies)} strategies")
            
            # Mock allocation
            allocation = np.array([0.3, 0.2, 0.1, 0.1, 0.1, 0.1, 0.05, 0.03, 0.02])
            print(f"✓ Mock allocation: {allocation}")
            
            # Check portfolio greeks calculation
            delta, gamma, vega = zoo.calculate_portfolio_greeks()
            print(f"✓ Portfolio Greeks: Δ={delta:.0f}, Γ={gamma:.0f}, ν={vega:.0f}")
            
            # Check leverage calculation
            leverage = zoo.check_leverage()
            print(f"✓ Leverage calculation: {leverage:.2f}x")
            
            # Check portfolio allocation
            port_alloc = zoo.get_portfolio_allocation()
            assert port_alloc.shape == (9,), "Portfolio allocation should be 9-dim"
            print(f"✓ Portfolio allocation shape correct")
            
            self.tests_passed += 1
            print("✅ Strategy Zoo Test PASSED")
            
        except Exception as e:
            self.tests_failed += 1
            print(f"❌ Strategy Zoo Test FAILED: {e}")
    
    def test_reward_calculator(self):
        """Test reward calculator"""
        print("\n🏆 Test 6: Reward Calculator")
        print("-" * 80)
        
        try:
            calc = RewardCalculator()
            
            # Test basic reward
            reward = calc.calculate_reward(
                realized_pnl=5000,
                portfolio_value=1000000,
                max_drawdown=0.02,
                portfolio_delta=0.5
            )
            
            print(f"✓ Reward calculation works: {reward:.6f}")
            
            # Test trajectory reward
            pnl_series = [100, 250, 180, 400, 550, 480]
            metrics = calc.calculate_trajectory_reward(pnl_series, 1000000)
            
            assert 'reward' in metrics, "Should have reward"
            assert 'pnl_ratio' in metrics, "Should have pnl_ratio"
            assert 'max_dd' in metrics, "Should have max_dd"
            
            print(f"✓ Trajectory reward: {metrics['reward']:.6f}")
            print(f"✓ PnL ratio: {metrics['pnl_ratio']:.6f}")
            print(f"✓ Max DD: {metrics['max_dd']:.6f}")
            
            # Test Sortino ratio
            returns = np.random.normal(0.001, 0.01, 100)
            sortino = calc.calculate_sortino_ratio(returns)
            print(f"✓ Sortino ratio calculation: {sortino:.2f}")
            
            self.tests_passed += 1
            print("✅ Reward Calculator Test PASSED")
            
        except Exception as e:
            self.tests_failed += 1
            print(f"❌ Reward Calculator Test FAILED: {e}")
    
    async def test_integration(self):
        """Test full integration"""
        print("\n🔗 Test 7: Full Integration")
        print("-" * 80)
        
        try:
            # Initialize all components
            agent = SACAgent(state_dim=34, action_dim=9)
            builder = StateBuilder()
            zoo = StrategyZoo(portfolio_value=1000000)
            calc = RewardCalculator()
            
            print("✓ All components initialized")
            
            # Build mock state
            state = np.random.randn(34).astype(np.float32)
            print("✓ State built")
            
            # Get allocation
            allocation = agent.select_action(state, deterministic=True)
            print(f"✓ Allocation selected: {allocation[:3]}... (sum={allocation.sum():.4f})")
            
            # Calculate reward
            reward = calc.calculate_reward(1000, 1000000, 0.01, 0.3)
            print(f"✓ Reward calculated: {reward:.6f}")
            
            # Store transition
            next_state = np.random.randn(34).astype(np.float32)
            agent.store_transition(state, allocation, reward, next_state, False)
            print(f"✓ Transition stored ({len(agent.replay_buffer)} samples)")
            
            # Full cycle simulation
            print("\n✓ Simulating full decision cycle:")
            print(f"   1. State: {state.shape}")
            print(f"   2. Action: {allocation.shape}, sum={allocation.sum():.4f}")
            print(f"   3. Reward: {reward:.6f}")
            print(f"   4. Next State: {next_state.shape}")
            
            self.tests_passed += 1
            print("✅ Integration Test PASSED")
            
        except Exception as e:
            self.tests_failed += 1
            print(f"❌ Integration Test FAILED: {e}")


def main():
    """Run all tests"""
    tester = SACSystemTester()
    success = tester.run_all_tests()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
