#!/usr/bin/env python3
"""
SAC Full Offline Retrain - Weekly Only
Runs Friday 6 PM & Sunday 10 PM

Author: AI Systems Operator
Last Modified: 2025-11-20
"""

import sys
import os
from datetime import datetime, timedelta
from pathlib import Path
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from meta_controller.sac_agent import SACAgent
from meta_controller.state_builder import StateBuilder
from backend.database.connection import get_db_connection
from backend.core.logger import get_logger

logger = get_logger(__name__)


def load_historical_data(start_date: datetime, end_date: datetime):
    """Load all historical experience data"""
    logger.info(f"Loading historical data: {start_date.date()} to {end_date.date()}")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = """
    SELECT state, action, reward, next_state, done
    FROM sac_experience
    WHERE timestamp >= %s AND timestamp <= %s
    ORDER BY timestamp
    """
    
    cursor.execute(query, (start_date, end_date))
    rows = cursor.fetchall()
    conn.close()
    
    logger.info(f"   Loaded {len(rows)} historical experiences")
    
    return rows


def main():
    parser = argparse.ArgumentParser(description='SAC Full Offline Retrain')
    parser.add_argument('--start-date', required=True, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', required=True, help='End date (YYYY-MM-DD)')
    parser.add_argument('--output', required=True, help='Output model path')
    parser.add_argument('--versioned-backup', required=True, help='Versioned backup path')
    
    args = parser.parse_args()
    
    start_date = datetime.strptime(args.start_date, '%Y-%m-%d')
    end_date = datetime.strptime(args.end_date, '%Y-%m-%d')
    
    logger.info("="*80)
    logger.info("SAC FULL OFFLINE RETRAIN")
    logger.info("="*80)
    logger.info(f"Start: {start_date.date()}")
    logger.info(f"End: {end_date.date()}")
    logger.info(f"Output: {args.output}")
    logger.info("")
    
    # Initialize agent
    agent = SACAgent(state_dim=35, action_dim=9)
    
    # Try to load existing model for warm start
    if Path(args.output).exists():
        logger.info("Loading existing model for warm start...")
        agent.load(args.output)
    
    # Load historical data
    historical_data = load_historical_data(start_date, end_date)
    
    if len(historical_data) == 0:
        logger.error("No historical data found!")
        sys.exit(1)
    
    # Add all experiences to replay buffer
    logger.info("\nFilling replay buffer...")
    for i, row in enumerate(historical_data):
        import numpy as np
        state = np.frombuffer(row[0], dtype=np.float32)
        action = np.frombuffer(row[1], dtype=np.float32)
        reward = float(row[2])
        next_state = np.frombuffer(row[3], dtype=np.float32)
        done = bool(row[4])
        
        agent.store_transition(state, action, reward, next_state, done)
        
        if (i + 1) % 1000 == 0:
            logger.info(f"   Added {i+1}/{len(historical_data)} experiences")
    
    logger.info(f"✅ Replay buffer filled: {len(agent.replay_buffer)} experiences")
    
    # Full training
    logger.info("\n🎯 Starting full training...")
    num_epochs = 500  # Full retrain
    batch_size = 256
    
    for epoch in range(num_epochs):
        metrics = agent.train(batch_size=batch_size)
        
        if metrics and (epoch + 1) % 50 == 0:
            logger.info(
                f"   Epoch {epoch+1}/{num_epochs}: "
                f"Critic={metrics['critic_loss']:.4f}, "
                f"Actor={metrics['actor_loss']:.4f}, "
                f"Alpha={metrics['alpha']:.4f}"
            )
    
    # Save model
    logger.info(f"\n💾 Saving model to {args.output}...")
    agent.save(args.output)
    
    # Create versioned backup
    logger.info(f"💾 Creating versioned backup: {args.versioned_backup}...")
    agent.save(args.versioned_backup)
    
    logger.info("\n✅ Full retrain complete!")
    logger.info(f"   Model: {args.output}")
    logger.info(f"   Backup: {args.versioned_backup}")
    logger.info(f"   Training steps: {agent.training_steps}")


if __name__ == "__main__":
    main()
