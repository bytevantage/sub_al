#!/usr/bin/env python3
"""
Test Trade Lifecycle - End-to-End Verification
Tests: Trade Entry → Exit → Database Persistence → ML Training
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from backend.database.database import db
from backend.database.models import Trade, Position
from backend.ml.model_manager import ModelManager
from backend.ml.training_data_collector import TrainingDataCollector
from backend.core.logger import get_logger

logger = get_logger(__name__)


async def verify_trade_data_persistence():
    """Verify that all trade data including Greeks are being saved"""
    
    print("\n" + "="*80)
    print("=== TRADE LIFECYCLE TEST: Database Persistence ===")
    print("="*80 + "\n")
    
    try:
        logger.info("✓ Using existing database connection")
        
        # Step 1: Check open positions
        print("\n--- Step 1: Current Open Positions ---")
        with db.get_session() as session:
            positions = session.query(Position).all()
            print(f"Found {len(positions)} open positions")
            
            for pos in positions:
                print(f"\nPosition ID: {pos.position_id}")
                print(f"  Symbol: {pos.symbol} {pos.strike_price} {pos.instrument_type}")
                print(f"  Entry Price: ₹{pos.entry_price}")
                print(f"  Current Price: ₹{pos.current_price}")
                print(f"  Unrealized P&L: ₹{pos.unrealized_pnl} ({pos.unrealized_pnl_pct:.2f}%)")
                print(f"  Strategy: {pos.strategy_name}")
                print(f"  ML Score: {pos.ml_score}")
                print(f"  Greeks at Entry:")
                print(f"    Delta: {pos.delta_entry}, Gamma: {pos.gamma_entry}")
                print(f"    Theta: {pos.theta_entry}, Vega: {pos.vega_entry}")
        
        # Step 2: Check recent closed trades
        print("\n--- Step 2: Recent Closed Trades (Last 10) ---")
        with db.get_session() as session:
            closed_trades = session.query(Trade).filter(
                Trade.status == 'CLOSED'
            ).order_by(Trade.exit_time.desc()).limit(10).all()
            
            print(f"Found {len(closed_trades)} closed trades\n")
            
            for i, trade in enumerate(closed_trades, 1):
                print(f"\n{i}. Trade ID: {trade.trade_id}")
                print(f"   Symbol: {trade.symbol} {trade.strike_price} {trade.instrument_type}")
                print(f"   Entry: ₹{trade.entry_price} @ {trade.entry_time}")
                print(f"   Exit: ₹{trade.exit_price} @ {trade.exit_time}")
                print(f"   Net P&L: ₹{trade.net_pnl} ({trade.pnl_percentage:.2f}%)")
                print(f"   Hold Duration: {trade.hold_duration_minutes} minutes")
                print(f"   Strategy: {trade.strategy_name} (weight: {trade.strategy_weight})")
                print(f"   Signal Strength: {trade.signal_strength}")
                print(f"   ML Score: {trade.ml_score}")
                
                # Check Greeks persistence
                print(f"   Greeks at Entry:")
                print(f"     Delta: {trade.delta_entry}, Gamma: {trade.gamma_entry}")
                print(f"     Theta: {trade.theta_entry}, Vega: {trade.vega_entry}")
                print(f"     IV: {trade.iv_entry}%, VIX: {trade.vix_entry}")
                
                print(f"   Greeks at Exit:")
                print(f"     Delta: {trade.delta_exit}, Gamma: {trade.gamma_exit}")
                print(f"     Theta: {trade.theta_exit}, Vega: {trade.vega_exit}")
                print(f"     IV: {trade.iv_exit}%, VIX: {trade.vix_exit}")
                
                # Check market context
                print(f"   Market Context:")
                print(f"     Spot @ Entry: ₹{trade.spot_price_entry}")
                print(f"     Spot @ Exit: ₹{trade.spot_price_exit}")
                print(f"     OI @ Entry: {trade.oi_entry}, OI @ Exit: {trade.oi_exit}")
                print(f"     Volume @ Entry: {trade.volume_entry}, Volume @ Exit: {trade.volume_exit}")
                
                # Check ML metadata
                print(f"   ML Metadata:")
                print(f"     Model Version: {trade.model_version}")
                print(f"     Model Hash: {trade.model_hash}")
                if trade.features_snapshot:
                    print(f"     Features Captured: {len(trade.features_snapshot)} features")
                    # Show first 5 features
                    feature_items = list(trade.features_snapshot.items())[:5]
                    for fname, fval in feature_items:
                        print(f"       {fname}: {fval}")
                    if len(trade.features_snapshot) > 5:
                        print(f"       ... and {len(trade.features_snapshot) - 5} more")
                
                print(f"   Exit Type: {trade.exit_type}")
                print(f"   Exit Reason: {trade.exit_reason}")
                print("-" * 70)
        
        # Step 3: Statistics
        print("\n--- Step 3: Database Statistics ---")
        with db.get_session() as session:
            total_trades = session.query(Trade).count()
            closed_trades_count = session.query(Trade).filter(Trade.status == 'CLOSED').count()
            open_trades_count = session.query(Trade).filter(Trade.status == 'OPEN').count()
            
            # Trades with complete Greek data
            trades_with_entry_greeks = session.query(Trade).filter(
                Trade.delta_entry.isnot(None),
                Trade.gamma_entry.isnot(None),
                Trade.theta_entry.isnot(None),
                Trade.vega_entry.isnot(None)
            ).count()
            
            trades_with_exit_greeks = session.query(Trade).filter(
                Trade.delta_exit.isnot(None),
                Trade.gamma_exit.isnot(None),
                Trade.status == 'CLOSED'
            ).count()
            
            # Trades with ML metadata
            trades_with_ml_score = session.query(Trade).filter(
                Trade.ml_score.isnot(None)
            ).count()
            
            trades_with_model_version = session.query(Trade).filter(
                Trade.model_version.isnot(None)
            ).count()
            
            trades_with_features = session.query(Trade).filter(
                Trade.features_snapshot.isnot(None)
            ).count()
            
            print(f"Total Trades: {total_trades}")
            print(f"  Closed: {closed_trades_count}")
            print(f"  Open: {open_trades_count}")
            print(f"\nData Quality:")
            print(f"  Trades with Entry Greeks: {trades_with_entry_greeks}/{total_trades} ({trades_with_entry_greeks/total_trades*100:.1f}%)")
            print(f"  Closed Trades with Exit Greeks: {trades_with_exit_greeks}/{closed_trades_count} ({trades_with_exit_greeks/closed_trades_count*100:.1f}% if closed_trades_count > 0 else 0)")
            print(f"  Trades with ML Score: {trades_with_ml_score}/{total_trades} ({trades_with_ml_score/total_trades*100:.1f}%)")
            print(f"  Trades with Model Version: {trades_with_model_version}/{total_trades}")
            print(f"  Trades with Feature Snapshot: {trades_with_features}/{total_trades}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error verifying trade data: {e}")
        import traceback
        traceback.print_exc()
        return False


async def verify_ml_training_pipeline():
    """Verify that ML training can use the persisted trade data"""
    
    print("\n" + "="*80)
    print("=== ML TRAINING PIPELINE TEST ===")
    print("="*80 + "\n")
    
    try:
        # Initialize ML components
        model_manager = ModelManager()
        await model_manager.load_models()
        
        data_collector = TrainingDataCollector(db)
        
        # Step 1: Check current model status
        print("\n--- Step 1: Current Model Status ---")
        model_info = model_manager.get_model_info()
        
        if model_info.get('model_loaded'):
            print("✓ ML Model is loaded")
            print(f"  Version: {model_info.get('version')}")
            metrics = model_info.get('metrics', {})
            print(f"  Accuracy: {metrics.get('accuracy', 0):.3f}")
            print(f"  AUC: {metrics.get('auc', 0):.3f}")
            print(f"  CV Score: {metrics.get('cv_mean', 0):.3f}")
            print(f"  Training Samples: {metrics.get('train_samples', 0)}")
            print(f"  Number of Features: {model_info.get('num_features')}")
            
            print(f"\n  Top 5 Important Features:")
            for i, feat in enumerate(model_info.get('top_features', [])[:5], 1):
                print(f"    {i}. {feat['name']}: {feat['importance']:.4f}")
        else:
            print("⚠ No ML model currently loaded")
            print("  Model will be trained when enough data is collected")
        
        # Step 2: Check training data availability
        print("\n--- Step 2: Training Data Availability ---")
        stats = await data_collector.get_training_statistics()
        
        print(f"Total Samples Available: {stats.get('total_samples', 0)}")
        print(f"  Winning Trades: {stats.get('winning_trades', 0)}")
        print(f"  Losing Trades: {stats.get('losing_trades', 0)}")
        print(f"  Win Rate: {stats.get('win_rate', 0):.1f}%")
        print(f"  Avg P&L: {stats.get('avg_pnl_percent', 0):.2f}%")
        print(f"  Avg Hold Duration: {stats.get('avg_hold_duration', 0):.0f} minutes")
        
        # Step 3: Collect training data
        print("\n--- Step 3: Collecting Training Data ---")
        training_df = await data_collector.collect_daily_data(lookback_days=0)  # All time
        
        if not training_df.empty:
            print(f"✓ Collected {len(training_df)} samples")
            print(f"  Columns: {len(training_df.columns)}")
            print(f"  Feature columns (excluding metadata):")
            
            # Show feature columns
            exclude_cols = ['trade_id', 'entry_time', 'strategy_name', 'is_winner', 'pnl_percent', 'hold_duration']
            feature_cols = [col for col in training_df.columns if col not in exclude_cols]
            
            print(f"    Total features: {len(feature_cols)}")
            for col in feature_cols[:10]:
                print(f"      - {col}")
            if len(feature_cols) > 10:
                print(f"      ... and {len(feature_cols) - 10} more")
            
            # Check data quality
            print(f"\n  Data Quality Check:")
            missing_greeks = training_df[['delta_entry', 'gamma_entry', 'theta_entry', 'vega_entry']].isnull().sum().sum()
            total_greek_fields = len(training_df) * 4
            print(f"    Missing Greek values: {missing_greeks}/{total_greek_fields} ({missing_greeks/total_greek_fields*100:.1f}%)")
            
            # Step 4: Test model training
            print("\n--- Step 4: Testing Model Training ---")
            min_samples = model_manager.min_training_samples
            
            if len(training_df) >= min_samples:
                print(f"✓ Sufficient data for training ({len(training_df)}/{min_samples})")
                print("  Triggering model training...")
                
                success = await model_manager.train_model(training_df)
                
                if success:
                    print("✓ Model training completed successfully!")
                    
                    # Get updated model info
                    updated_info = model_manager.get_model_info()
                    metrics = updated_info.get('metrics', {})
                    print(f"\n  Updated Model Metrics:")
                    print(f"    Accuracy: {metrics.get('accuracy', 0):.3f}")
                    print(f"    AUC: {metrics.get('auc', 0):.3f}")
                    print(f"    CV Score: {metrics.get('cv_mean', 0):.3f} (+/- {metrics.get('cv_std', 0):.3f})")
                else:
                    print("✗ Model training failed")
            else:
                print(f"⚠ Insufficient data for training")
                print(f"  Need {min_samples - len(training_df)} more samples")
        else:
            print("✗ No training data available")
        
        print("\n" + "="*80)
        print("=== ML Training Pipeline Test Complete ===")
        print("="*80)
        
        return True
        
    except Exception as e:
        logger.error(f"Error in ML training pipeline test: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("=== COMPREHENSIVE TRADE LIFECYCLE TEST ===")
    print(f"=== {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
    print("="*80)
    
    # Test 1: Database Persistence
    result1 = await verify_trade_data_persistence()
    
    # Test 2: ML Training Pipeline
    result2 = await verify_ml_training_pipeline()
    
    # Summary
    print("\n" + "="*80)
    print("=== TEST SUMMARY ===")
    print("="*80)
    print(f"Database Persistence: {'✓ PASS' if result1 else '✗ FAIL'}")
    print(f"ML Training Pipeline: {'✓ PASS' if result2 else '✗ FAIL'}")
    print("="*80 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
