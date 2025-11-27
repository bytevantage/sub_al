"""
QuantumEdge V2 - Incremental Training
Trains only on new day's data (fast, <10 minutes)

Author: AI Systems Operator
Last Modified: 2025-11-20
"""

import torch
import torch.nn as nn
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from training.quantum_edge_v2.feature_engineering import QuantumEdgeFeatureEngineer
from training.quantum_edge_v2.train import TemporalFusionTransformer, QuantumEdgeDataset
from backend.core.logger import get_logger

logger = get_logger(__name__)


class IncrementalTrainer:
    """Incremental trainer for QuantumEdge v2"""
    
    def __init__(self, model_path: str, data_date: datetime):
        self.model_path = model_path
        self.data_date = data_date
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.feature_engineer = QuantumEdgeFeatureEngineer()
        
        logger.info("="*80)
        logger.info("QUANTUMEDGE V2 - INCREMENTAL TRAINING")
        logger.info("="*80)
        logger.info(f"Model: {model_path}")
        logger.info(f"Date: {data_date.strftime('%Y-%m-%d')}")
        logger.info(f"Device: {self.device}")
        
        # Load existing model
        self.model, self.hyperparameters = self._load_model()
    
    def _load_model(self):
        """Load existing model"""
        logger.info("\n📥 Loading existing model...")
        
        if not Path(self.model_path).exists():
            raise FileNotFoundError(f"Model not found: {self.model_path}")
        
        checkpoint = torch.load(self.model_path, map_location=self.device)
        
        hyperparameters = checkpoint['hyperparameters']
        
        # Reconstruct model
        model = TemporalFusionTransformer(
            input_dim=34,
            hidden_dim=hyperparameters['hidden_dim'],
            num_heads=hyperparameters['num_heads'],
            num_layers=hyperparameters['num_layers'],
            output_dim=3,
            dropout=hyperparameters['dropout'],
            sequence_length=hyperparameters['sequence_length']
        ).to(self.device)
        
        model.load_state_dict(checkpoint['model_state_dict'])
        
        logger.info("✅ Model loaded successfully")
        
        return model, hyperparameters
    
    def incremental_update(self, epochs: int = 10, lr: float = 0.0001):
        """Incremental update on new day's data"""
        logger.info("\n🔧 Loading new data...")
        
        features, targets = self._load_day_data()
        
        if len(features) == 0:
            logger.warning("⚠️  No data found")
            return {'status': 'no_data', 'accuracy': 0, 'loss': 0, 'samples': 0}
        
        logger.info(f"   Loaded: {len(features)} samples")
        
        dataset = QuantumEdgeDataset(
            features, targets,
            sequence_length=self.hyperparameters['sequence_length']
        )
        
        dataloader = torch.utils.data.DataLoader(dataset, batch_size=32, shuffle=True)
        
        # Training
        self.model.train()
        optimizer = torch.optim.AdamW(self.model.parameters(), lr=lr)
        criterion = nn.CrossEntropyLoss()
        
        logger.info(f"\n🎯 Training for {epochs} epochs...")
        
        for epoch in range(epochs):
            total_loss = 0
            correct = 0
            total = 0
            
            for X_batch, y_batch in dataloader:
                X_batch = X_batch.to(self.device)
                y_batch = y_batch.to(self.device)
                
                optimizer.zero_grad()
                outputs = self.model(X_batch)
                loss = criterion(outputs, y_batch)
                loss.backward()
                optimizer.step()
                
                total_loss += loss.item()
                _, predicted = outputs.max(1)
                total += y_batch.size(0)
                correct += predicted.eq(y_batch).sum().item()
            
            if (epoch + 1) % 5 == 0:
                accuracy = correct / total if total > 0 else 0
                logger.info(f"   Epoch {epoch+1}/{epochs}: Loss={total_loss:.4f}, Acc={accuracy:.2%}")
        
        # Save updated model
        self._save_model()
        
        final_accuracy = correct / total if total > 0 else 0
        
        return {
            'status': 'success',
            'accuracy': final_accuracy,
            'loss': total_loss,
            'samples': len(features)
        }
    
    def _load_day_data(self):
        """Load data for specific date"""
        from backend.database.connection import get_db_connection
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        start = self.data_date.replace(hour=9, minute=15)
        end = self.data_date.replace(hour=15, minute=30)
        
        query = """
        SELECT DISTINCT timestamp 
        FROM option_chain_snapshots_clean
        WHERE symbol='NIFTY' 
          AND timestamp >= %s 
          AND timestamp <= %s
        ORDER BY timestamp
        """
        
        cursor.execute(query, (start, end))
        timestamps = [row[0] for row in cursor.fetchall()]
        
        features_list = []
        targets_list = []
        
        for i, ts in enumerate(timestamps[:-12]):
            features = self.feature_engineer.extract_features_from_db('NIFTY', ts)
            
            if features is None or len(features) != 34:
                continue
            
            # Target: direction in next 12 periods (1 hour)
            future_ts = timestamps[i + 12] if i + 12 < len(timestamps) else None
            if future_ts:
                target = self._calculate_target(ts, future_ts)
                features_list.append(features)
                targets_list.append(target)
        
        conn.close()
        
        return np.array(features_list), np.array(targets_list)
    
    def _calculate_target(self, current_ts, future_ts):
        """Calculate target direction"""
        from backend.database.connection import get_db_connection
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT spot_price FROM option_chain_snapshots_clean
            WHERE symbol='NIFTY' AND timestamp=%s LIMIT 1
        """, (current_ts,))
        current_spot = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT spot_price FROM option_chain_snapshots_clean
            WHERE symbol='NIFTY' AND timestamp=%s LIMIT 1
        """, (future_ts,))
        future_spot = cursor.fetchone()[0]
        
        conn.close()
        
        ret = (future_spot - current_spot) / current_spot
        
        if ret > 0.002:
            return 0  # UP
        elif ret < -0.002:
            return 2  # DOWN
        else:
            return 1  # FLAT
    
    def _save_model(self):
        """Save updated model"""
        torch.save({
            'model_state_dict': self.model.state_dict(),
            'hyperparameters': self.hyperparameters,
            'training_date': datetime.now(),
            'last_update_date': self.data_date
        }, self.model_path)
        
        logger.info(f"\n💾 Model saved: {self.model_path}")
