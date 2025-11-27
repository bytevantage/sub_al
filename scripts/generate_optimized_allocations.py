#!/usr/bin/env python3
"""
Generate Optimized Strategy Allocations
"""

import sys
import yaml
import argparse
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.jobs.performance_report import generate_strategy_report
from backend.optimization.strategy_allocator import optimize_weights
from backend.core.config import config
from backend.core.logger import get_logger

logger = get_logger(__name__)


def main():
    """Main execution"""
    parser = argparse.ArgumentParser(description='Generate optimized strategy allocations')
    parser.add_argument('--days', type=int, default=90, help='Lookback period in days')
    parser.add_argument('--output', type=str, default='config/strategy_weights.yaml', 
                       help='Output YAML file path')
    args = parser.parse_args()
    
    # Generate performance report
    logger.info(f"Generating strategy performance report for last {args.days} days")
    report = generate_strategy_report(days=args.days)
    
    if report.empty:
        logger.error("No performance data available. Cannot optimize.")
        return
        
    # Get current market regime
    regime = config.get('market.regime', 'NORMAL')
    logger.info(f"Current market regime: {regime}")
    
    # Optimize weights
    logger.info("Optimizing strategy weights...")
    optimized_weights = optimize_weights(report, regime=regime)
    
    # Save to YAML
    logger.info(f"Saving optimized weights to {args.output}")
    with open(args.output, 'w') as f:
        yaml.dump(optimized_weights, f)
    
    logger.info("✓ Optimization complete")


if __name__ == "__main__":
    main()
