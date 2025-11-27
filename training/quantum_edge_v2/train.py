"""
Quantum Edge v2 - Training Pipeline
Uses Temporal Fusion Transformer for NIFTY options direction prediction
Walk-forward validation with Optuna hyperparameter optimization
"""

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import StandardScaler
import optuna
from datetime import datetime, timedelta
import pickle
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from feature_engineering import QuantumEdgeFeatureEngineer

print("="*100)
print("QUANTUM EDGE V2 - TRAINING PIPELINE")
print("Temporal Fusion Transformer for NIFTY Options")
print("="*100)


class TemporalFusionTransformer(nn.Module):
    """
    Temporal Fusion Transformer for time-series forecasting
    State-of-the-art architecture for financial prediction
    """
    
    def __init__(
        self,
        input_dim: int = 34,
        hidden_dim: int = 128,
        num_heads: int = 4,
        num_layers: int = 3,
        dropout: float = 0.1,
        forecast_horizon: int = 1
    ):
        super().__init__()
        
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        
        # Input embedding
        self.input_embedding = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout)
        )
        
        # Variable selection network (attention-based feature selection)
        self.variable_selection = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim),
            nn.Tanh(),
            nn.Linear(hidden_dim, input_dim),
            nn.Softmax(dim=-1)
        )
        
        # Temporal processing with transformer encoder
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=hidden_dim,
            nhead=num_heads,
            dim_feedforward=hidden_dim * 4,
            dropout=dropout,
            batch_first=True
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        
        # GRN (Gated Residual Network) for context
        self.grn = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim),
            nn.ELU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.Dropout(dropout)
        )
        
        # Multi-horizon attention
        self.temporal_attention = nn.MultiheadAttention(
            embed_dim=hidden_dim,
            num_heads=num_heads,
            dropout=dropout,
            batch_first=True
        )
        
        # Output heads
        self.direction_head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim // 2, 3)  # UP, FLAT, DOWN
        )
        
        self.magnitude_head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim // 2, 1)  # Predicted return magnitude
        )
        
        self.confidence_head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim // 2, 1),
            nn.Sigmoid()  # Confidence score [0, 1]
        )
    
    def forward(self, x, sequence_lengths=None):
        """
        Args:
            x: (batch, seq_len, input_dim)
            sequence_lengths: actual lengths if using padding
        
        Returns:
            direction_logits, magnitude, confidence
        """
        batch_size, seq_len, _ = x.shape
        
        # Input embedding
        embedded = self.input_embedding(x)  # (batch, seq_len, hidden)
        
        # Variable selection (feature importance)
        importance = self.variable_selection(embedded)  # (batch, seq_len, input_dim)
        weighted_input = x * importance  # Element-wise multiplication
        embedded_weighted = self.input_embedding(weighted_input)
        
        # Temporal transformer encoding
        encoded = self.transformer(embedded_weighted)  # (batch, seq_len, hidden)
        
        # GRN with residual
        grn_out = self.grn(encoded)
        encoded = encoded + grn_out
        
        # Temporal attention (focus on relevant time steps)
        attended, _ = self.temporal_attention(encoded, encoded, encoded)
        
        # Use last timestep for prediction
        final_state = attended[:, -1, :]  # (batch, hidden)
        
        # Multi-task outputs
        direction = self.direction_head(final_state)  # (batch, 3)
        magnitude = self.magnitude_head(final_state)  # (batch, 1)
        confidence = self.confidence_head(final_state)  # (batch, 1)
        
        return direction, magnitude, confidence


class OptionsDataset(Dataset):
    """PyTorch Dataset for option chain features"""
    
    def __init__(self, features, targets, sequence_length=12):
        """
        Args:
            features: (n_samples, n_features)
            targets: (n_samples,) - future returns
            sequence_length: lookback window
        """
        self.features = features
        self.targets = targets
        self.sequence_length = sequence_length
        
    def __len__(self):
        return len(self.features) - self.sequence_length
    
    def __getitem__(self, idx):
        # Get sequence
        x = self.features[idx:idx + self.sequence_length]
        
        # Target is next bar's direction and magnitude
        future_idx = idx + self.sequence_length
        if future_idx < len(self.targets):
            target_return = self.targets[future_idx]
        else:
            target_return = 0.0
        
        # Direction: 0=DOWN, 1=FLAT, 2=UP
        if target_return < -0.05:
            direction = 0
        elif target_return > 0.05:
            direction = 2
        else:
            direction = 1
        
        magnitude = abs(target_return)
        
        return (
            torch.FloatTensor(x),
            torch.LongTensor([direction]),
            torch.FloatTensor([magnitude])
        )


class QuantumEdgeTrainer:
    """Training pipeline with walk-forward validation"""
    
    def __init__(
        self,
        start_date: datetime,
        end_date: datetime,
        n_splits: int = 5,
        device: str = None
    ):
        self.start_date = start_date
        self.end_date = end_date
        self.n_splits = n_splits
        self.device = device or ('cuda' if torch.cuda.is_available() else 'cpu')
        
        self.feature_engineer = QuantumEdgeFeatureEngineer()
        self.scaler = StandardScaler()
        
        print(f"\n📊 Training Configuration:")
        print(f"   Period: {start_date} to {end_date}")
        print(f"   Splits: {n_splits}")
        print(f"   Device: {self.device}")
    
    def load_data(self):
        """Load and prepare training data"""
        print(f"\n📥 Loading data from option_chain_snapshots_clean...")
        
        # Fetch historical data
        import subprocess
        
        query = f"""
        docker exec trading_db psql -U trading_user -d trading_db -t -A -F"," -c "
        SELECT DISTINCT timestamp
        FROM option_chain_snapshots_clean
        WHERE symbol = 'NIFTY'
          AND timestamp BETWEEN '{self.start_date}' AND '{self.end_date}'
        ORDER BY timestamp;
        " > /tmp/timestamps.csv
        """
        
        subprocess.run(query, shell=True, capture_output=True)
        
        timestamps = pd.read_csv('/tmp/timestamps.csv', names=['timestamp'])
        timestamps['timestamp'] = pd.to_datetime(timestamps['timestamp'])
        
        print(f"   Found {len(timestamps)} timestamps")
        
        # Extract features for each timestamp
        features_list = []
        returns_list = []
        valid_timestamps = []
        
        print(f"\n🔧 Extracting 34-dim features...")
        for i, ts in enumerate(timestamps['timestamp']):
            if i % 100 == 0:
                print(f"   Progress: {i}/{len(timestamps)} ({i/len(timestamps)*100:.1f}%)")
            
            features = self.feature_engineer.extract_features_from_db('NIFTY', ts)
            
            # Calculate future return (6 bars ahead = 30 minutes)
            if i < len(timestamps) - 6:
                future_ts = timestamps['timestamp'].iloc[i + 6]
                current_spot = features[0] * 25000  # Denormalize
                
                # Get future spot
                future_features = self.feature_engineer.extract_features_from_db('NIFTY', future_ts)
                future_spot = future_features[0] * 25000
                
                ret = (future_spot / current_spot - 1) * 100
                
                features_list.append(features)
                returns_list.append(ret)
                valid_timestamps.append(ts)
        
        self.features = np.array(features_list)
        self.targets = np.array(returns_list)
        self.timestamps = pd.DatetimeIndex(valid_timestamps)
        
        print(f"\n✅ Data loaded:")
        print(f"   Features: {self.features.shape}")
        print(f"   Targets: {self.targets.shape}")
        print(f"   Timespan: {self.timestamps[0]} to {self.timestamps[-1]}")
        
        # Normalize features
        self.features = self.scaler.fit_transform(self.features)
        
        return self.features, self.targets
    
    def objective(self, trial: optuna.Trial, train_idx, val_idx):
        """Optuna objective function"""
        
        # Hyperparameters to tune
        hidden_dim = trial.suggest_categorical('hidden_dim', [64, 128, 256])
        num_heads = trial.suggest_categorical('num_heads', [2, 4, 8])
        num_layers = trial.suggest_int('num_layers', 2, 4)
        dropout = trial.suggest_float('dropout', 0.1, 0.4)
        lr = trial.suggest_loguniform('lr', 1e-5, 1e-3)
        sequence_length = trial.suggest_int('sequence_length', 6, 24)
        
        # Create model
        model = TemporalFusionTransformer(
            input_dim=34,
            hidden_dim=hidden_dim,
            num_heads=num_heads,
            num_layers=num_layers,
            dropout=dropout
        ).to(self.device)
        
        # Datasets
        train_dataset = OptionsDataset(
            self.features[train_idx],
            self.targets[train_idx],
            sequence_length=sequence_length
        )
        val_dataset = OptionsDataset(
            self.features[val_idx],
            self.targets[val_idx],
            sequence_length=sequence_length
        )
        
        train_loader = DataLoader(train_dataset, batch_size=64, shuffle=True)
        val_loader = DataLoader(val_dataset, batch_size=64, shuffle=False)
        
        # Optimizer
        optimizer = torch.optim.Adam(model.parameters(), lr=lr)
        
        # Loss functions
        direction_criterion = nn.CrossEntropyLoss()
        magnitude_criterion = nn.MSELoss()
        
        # Training
        best_val_acc = 0
        patience = 5
        patience_counter = 0
        
        for epoch in range(20):
            model.train()
            train_loss = 0
            
            for x, direction, magnitude in train_loader:
                x = x.to(self.device)
                direction = direction.to(self.device).squeeze()
                magnitude = magnitude.to(self.device)
                
                optimizer.zero_grad()
                
                dir_logits, mag_pred, conf = model(x)
                
                loss_dir = direction_criterion(dir_logits, direction)
                loss_mag = magnitude_criterion(mag_pred, magnitude)
                
                loss = loss_dir + 0.5 * loss_mag
                loss.backward()
                
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                
                train_loss += loss.item()
            
            # Validation
            model.eval()
            correct = 0
            total = 0
            
            with torch.no_grad():
                for x, direction, magnitude in val_loader:
                    x = x.to(self.device)
                    direction = direction.to(self.device).squeeze()
                    
                    dir_logits, _, _ = model(x)
                    _, predicted = torch.max(dir_logits, 1)
                    
                    total += direction.size(0)
                    correct += (predicted == direction).sum().item()
            
            val_acc = correct / total
            
            if val_acc > best_val_acc:
                best_val_acc = val_acc
                patience_counter = 0
            else:
                patience_counter += 1
                if patience_counter >= patience:
                    break
        
        return best_val_acc
    
    def train_with_optuna(self, n_trials: int = 50):
        """Hyperparameter optimization with Optuna"""
        
        print(f"\n🔍 Starting hyperparameter search ({n_trials} trials)...")
        
        # Use first train/val split for hyperparameter tuning
        tscv = TimeSeriesSplit(n_splits=self.n_splits)
        train_idx, val_idx = list(tscv.split(self.features))[0]
        
        study = optuna.create_study(direction='maximize')
        study.optimize(
            lambda trial: self.objective(trial, train_idx, val_idx),
            n_trials=n_trials,
            show_progress_bar=True
        )
        
        print(f"\n✅ Best hyperparameters:")
        for key, value in study.best_params.items():
            print(f"   {key}: {value}")
        print(f"   Best validation accuracy: {study.best_value:.4f}")
        
        return study.best_params
    
    def train_final_model(self, best_params: dict):
        """Train final model with best hyperparameters"""
        
        print(f"\n🎯 Training final model...")
        
        model = TemporalFusionTransformer(
            input_dim=34,
            hidden_dim=best_params['hidden_dim'],
            num_heads=best_params['num_heads'],
            num_layers=best_params['num_layers'],
            dropout=best_params['dropout']
        ).to(self.device)
        
        # Use all data for final training
        dataset = OptionsDataset(
            self.features,
            self.targets,
            sequence_length=best_params['sequence_length']
        )
        
        train_loader = DataLoader(dataset, batch_size=64, shuffle=True)
        
        optimizer = torch.optim.Adam(model.parameters(), lr=best_params['lr'])
        direction_criterion = nn.CrossEntropyLoss()
        magnitude_criterion = nn.MSELoss()
        
        # Training loop
        for epoch in range(50):
            model.train()
            total_loss = 0
            correct = 0
            total = 0
            
            for x, direction, magnitude in train_loader:
                x = x.to(self.device)
                direction = direction.to(self.device).squeeze()
                magnitude = magnitude.to(self.device)
                
                optimizer.zero_grad()
                
                dir_logits, mag_pred, conf = model(x)
                
                loss_dir = direction_criterion(dir_logits, direction)
                loss_mag = magnitude_criterion(mag_pred, magnitude)
                
                loss = loss_dir + 0.5 * loss_mag
                loss.backward()
                
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                
                total_loss += loss.item()
                
                _, predicted = torch.max(dir_logits, 1)
                total += direction.size(0)
                correct += (predicted == direction).sum().item()
            
            if (epoch + 1) % 10 == 0:
                acc = correct / total
                print(f"   Epoch {epoch+1}/50: Loss={total_loss/len(train_loader):.4f}, Acc={acc:.4f}")
        
        return model
    
    def evaluate(self, model):
        """Evaluate model performance"""
        
        print(f"\n📊 Evaluating model...")
        
        dataset = OptionsDataset(self.features, self.targets, sequence_length=12)
        loader = DataLoader(dataset, batch_size=64, shuffle=False)
        
        model.eval()
        all_predictions = []
        all_actuals = []
        all_confidences = []
        
        with torch.no_grad():
            for x, direction, magnitude in loader:
                x = x.to(self.device)
                direction = direction.to(self.device).squeeze()
                
                dir_logits, _, conf = model(x)
                probs = torch.softmax(dir_logits, dim=1)
                _, predicted = torch.max(probs, 1)
                
                all_predictions.extend(predicted.cpu().numpy())
                all_actuals.extend(direction.cpu().numpy())
                all_confidences.extend(conf.cpu().numpy().flatten())
        
        all_predictions = np.array(all_predictions)
        all_actuals = np.array(all_actuals)
        all_confidences = np.array(all_confidences)
        
        # Metrics
        accuracy = (all_predictions == all_actuals).mean()
        
        # High-confidence predictions
        high_conf_mask = all_confidences > 0.7
        if high_conf_mask.sum() > 0:
            high_conf_acc = (all_predictions[high_conf_mask] == all_actuals[high_conf_mask]).mean()
        else:
            high_conf_acc = 0
        
        print(f"\n✅ Evaluation Results:")
        print(f"   Overall Accuracy: {accuracy*100:.2f}%")
        print(f"   High Confidence Accuracy (>0.7): {high_conf_acc*100:.2f}%")
        print(f"   High Confidence Samples: {high_conf_mask.sum()} / {len(all_predictions)}")
        
        return accuracy, high_conf_acc
    
    def save_model(self, model, best_params, save_path='models/quantum_edge_v2.pt'):
        """Save trained model and artifacts"""
        
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Save model
        torch.save({
            'model_state_dict': model.state_dict(),
            'hyperparameters': best_params,
            'scaler': self.scaler,
            'feature_names': self.feature_engineer.FEATURE_NAMES,
            'training_date': datetime.now(),
            'data_period': {
                'start': str(self.start_date),
                'end': str(self.end_date)
            }
        }, save_path)
        
        print(f"\n💾 Model saved to {save_path}")


def main():
    # Training configuration (using available data range)
    start_date = datetime(2025, 11, 17)  # Actual data starts Nov 17, 2025
    end_date = datetime(2025, 11, 20)    # Through Nov 20, 2025
    
    # Initialize trainer
    trainer = QuantumEdgeTrainer(
        start_date=start_date,
        end_date=end_date,
        n_splits=2  # Reduced for small dataset (3 days)
    )
    
    # Load data
    features, targets = trainer.load_data()
    
    # Hyperparameter optimization (reduced trials for small dataset)
    best_params = trainer.train_with_optuna(n_trials=10)
    
    # Train final model
    final_model = trainer.train_final_model(best_params)
    
    # Evaluate
    accuracy, high_conf_acc = trainer.evaluate(final_model)
    
    # Save
    trainer.save_model(final_model, best_params)
    
    print("\n" + "="*100)
    print("✅ TRAINING COMPLETE!")
    print("="*100)
    print(f"\n📊 Final Performance:")
    print(f"   Direction Accuracy: {accuracy*100:.2f}%")
    print(f"   High-Confidence Accuracy: {high_conf_acc*100:.2f}%")
    
    if accuracy > 0.84:
        print(f"\n🎉 TARGET ACHIEVED: Accuracy > 84%")
    
    print(f"\n💾 Model saved: models/quantum_edge_v2.pt")
    print(f"📊 Ready for inference!")


if __name__ == "__main__":
    main()
