"""
Quantum Edge v2 - Performance Monitoring
Tracks predictions vs actual outcomes for continuous evaluation
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
from pathlib import Path
import subprocess

print("="*100)
print("QUANTUM EDGE V2 - PERFORMANCE MONITORING")
print("="*100)


class PerformanceMonitor:
    """Monitor and evaluate model predictions vs actual outcomes"""
    
    def __init__(self, lookback_days: int = 7):
        self.lookback_days = lookback_days
        self.predictions = []
        self.actuals = []
    
    def load_predictions_from_db(self):
        """Load recent predictions from database"""
        
        print(f"\n📥 Loading predictions from last {self.lookback_days} days...")
        
        # This would query from a predictions table
        # For now, we'll show the structure
        
        query = f"""
        SELECT 
            timestamp,
            symbol,
            prediction,
            confidence,
            prob_up,
            prob_flat,
            prob_down,
            expected_magnitude,
            actual_return,
            correct
        FROM quantum_edge_predictions
        WHERE timestamp >= NOW() - INTERVAL '{self.lookback_days} days'
        ORDER BY timestamp;
        """
        
        # TODO: Execute query when predictions table exists
        print(f"   ⚠️  Predictions table not yet created")
        print(f"   Create with: CREATE TABLE quantum_edge_predictions (...)")
        
        return pd.DataFrame()
    
    def evaluate_predictions(self, df: pd.DataFrame):
        """Evaluate prediction accuracy"""
        
        if df.empty:
            print("\n⚠️  No predictions to evaluate")
            return
        
        print(f"\n📊 EVALUATION RESULTS")
        print("="*80)
        
        # Overall accuracy
        accuracy = df['correct'].mean()
        print(f"\n✅ Overall Accuracy: {accuracy:.2%}")
        
        # By confidence level
        print(f"\n📊 Accuracy by Confidence:")
        confidence_bins = [0, 0.7, 0.8, 0.9, 1.0]
        labels = ['60-70%', '70-80%', '80-90%', '90-100%']
        
        df['confidence_bin'] = pd.cut(df['confidence'], bins=confidence_bins, labels=labels)
        
        for bin_label in labels:
            bin_data = df[df['confidence_bin'] == bin_label]
            if len(bin_data) > 0:
                acc = bin_data['correct'].mean()
                count = len(bin_data)
                print(f"   {bin_label}: {acc:.2%} ({count} predictions)")
        
        # By prediction type
        print(f"\n📊 Accuracy by Prediction:")
        for pred in ['UP', 'FLAT', 'DOWN']:
            pred_data = df[df['prediction'] == pred]
            if len(pred_data) > 0:
                acc = pred_data['correct'].mean()
                count = len(pred_data)
                print(f"   {pred}: {acc:.2%} ({count} predictions)")
        
        # Calibration
        print(f"\n📊 Calibration:")
        for conf_level in [0.7, 0.8, 0.9]:
            conf_data = df[df['confidence'] >= conf_level]
            if len(conf_data) > 0:
                actual_acc = conf_data['correct'].mean()
                expected_acc = conf_data['confidence'].mean()
                diff = abs(actual_acc - expected_acc)
                
                status = "✅" if diff < 0.05 else "⚠️"
                print(f"   {status} Conf ≥ {conf_level:.0%}: "
                      f"Expected {expected_acc:.2%}, Actual {actual_acc:.2%} "
                      f"(Δ {diff:.2%})")
        
        # Trading performance
        print(f"\n💰 Trading Performance (High Confidence Only):")
        high_conf = df[df['confidence'] > 0.7]
        
        if len(high_conf) > 0:
            # Simulated P&L (assuming ₹10,000 per trade)
            high_conf['pnl'] = high_conf.apply(
                lambda x: x['actual_return'] * 10000 if x['correct'] else -10000 * 0.5,
                axis=1
            )
            
            total_pnl = high_conf['pnl'].sum()
            win_rate = high_conf['correct'].mean()
            num_trades = len(high_conf)
            
            print(f"   Trades: {num_trades}")
            print(f"   Win Rate: {win_rate:.2%}")
            print(f"   Total P&L: ₹{total_pnl:,.0f}")
            print(f"   Avg P&L: ₹{total_pnl/num_trades:,.0f} per trade")
    
    def plot_performance(self, df: pd.DataFrame):
        """Generate performance visualizations"""
        
        if df.empty:
            return
        
        print(f"\n📊 Generating performance charts...")
        
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        
        # 1. Accuracy over time
        df['date'] = pd.to_datetime(df['timestamp']).dt.date
        daily_acc = df.groupby('date')['correct'].mean()
        
        axes[0, 0].plot(daily_acc.index, daily_acc.values, marker='o')
        axes[0, 0].axhline(y=0.84, color='r', linestyle='--', label='Target (84%)')
        axes[0, 0].set_title('Daily Accuracy', fontweight='bold')
        axes[0, 0].set_ylabel('Accuracy')
        axes[0, 0].legend()
        axes[0, 0].grid(True, alpha=0.3)
        
        # 2. Confidence distribution
        axes[0, 1].hist(df['confidence'], bins=20, alpha=0.7, edgecolor='black')
        axes[0, 1].axvline(x=0.7, color='r', linestyle='--', label='Min Threshold')
        axes[0, 1].set_title('Confidence Distribution', fontweight='bold')
        axes[0, 1].set_xlabel('Confidence')
        axes[0, 1].set_ylabel('Count')
        axes[0, 1].legend()
        
        # 3. Prediction distribution
        pred_counts = df['prediction'].value_counts()
        axes[1, 0].bar(pred_counts.index, pred_counts.values, 
                      color=['green', 'gray', 'red'])
        axes[1, 0].set_title('Prediction Distribution', fontweight='bold')
        axes[1, 0].set_ylabel('Count')
        
        # 4. Calibration plot
        confidence_bins = np.linspace(0.6, 1.0, 9)
        bin_centers = []
        bin_accuracies = []
        
        for i in range(len(confidence_bins) - 1):
            bin_data = df[(df['confidence'] >= confidence_bins[i]) & 
                         (df['confidence'] < confidence_bins[i+1])]
            if len(bin_data) > 5:
                bin_centers.append((confidence_bins[i] + confidence_bins[i+1]) / 2)
                bin_accuracies.append(bin_data['correct'].mean())
        
        if bin_centers:
            axes[1, 1].scatter(bin_centers, bin_accuracies, s=100)
            axes[1, 1].plot([0.6, 1.0], [0.6, 1.0], 'r--', label='Perfect Calibration')
            axes[1, 1].set_title('Calibration Plot', fontweight='bold')
            axes[1, 1].set_xlabel('Predicted Confidence')
            axes[1, 1].set_ylabel('Actual Accuracy')
            axes[1, 1].legend()
            axes[1, 1].grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        output_path = 'training/quantum_edge_v2/performance_report.png'
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        
        print(f"   ✅ Charts saved: {output_path}")
    
    def generate_report(self):
        """Generate comprehensive performance report"""
        
        print(f"\n📄 Generating performance report...")
        
        # Load data
        df = self.load_predictions_from_db()
        
        if df.empty:
            print(f"\n⚠️  No data available for report")
            print(f"\n💡 To start tracking:")
            print(f"   1. Create predictions table in database")
            print(f"   2. Log predictions from inference.py")
            print(f"   3. Log actual outcomes after 30 minutes")
            print(f"   4. Run this script to evaluate")
            return
        
        # Evaluate
        self.evaluate_predictions(df)
        
        # Plot
        self.plot_performance(df)
        
        print(f"\n{'='*80}")
        print(f"✅ MONITORING COMPLETE")
        print(f"{'='*80}")


def create_predictions_table():
    """Create table to store predictions for monitoring"""
    
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS quantum_edge_predictions (
        id SERIAL PRIMARY KEY,
        timestamp TIMESTAMPTZ NOT NULL,
        symbol VARCHAR(10) NOT NULL,
        prediction VARCHAR(10) NOT NULL,
        confidence FLOAT NOT NULL,
        prob_up FLOAT NOT NULL,
        prob_flat FLOAT NOT NULL,
        prob_down FLOAT NOT NULL,
        expected_magnitude FLOAT,
        spot_price FLOAT,
        actual_return FLOAT,
        correct BOOLEAN,
        evaluated BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    
    CREATE INDEX IF NOT EXISTS idx_predictions_timestamp 
    ON quantum_edge_predictions(timestamp);
    
    CREATE INDEX IF NOT EXISTS idx_predictions_evaluated 
    ON quantum_edge_predictions(evaluated);
    """
    
    cmd = f"""
    docker exec trading_db psql -U trading_user -d trading_db -c "
    {create_table_sql}
    "
    """
    
    print("\n🔧 Creating predictions table...")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    if 'CREATE TABLE' in result.stdout or 'already exists' in result.stderr:
        print("   ✅ Predictions table ready")
    else:
        print(f"   ⚠️  {result.stderr}")


def main():
    """Main monitoring function"""
    
    # Create table if needed
    create_predictions_table()
    
    # Run monitor
    monitor = PerformanceMonitor(lookback_days=7)
    monitor.generate_report()


if __name__ == "__main__":
    main()
