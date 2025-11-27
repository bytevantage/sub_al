"""
Quantum Edge v2 - Inference Engine
Real-time prediction using trained Temporal Fusion Transformer
Outputs direction probability every 5 minutes for live/paper trading
"""

import numpy as np
import torch
import torch.nn as nn
from datetime import datetime
from pathlib import Path
import sys
import time

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from training.quantum_edge_v2.feature_engineering import QuantumEdgeFeatureEngineer
from training.quantum_edge_v2.train import TemporalFusionTransformer


class QuantumEdgeInference:
    """
    Real-time inference engine for QuantumEdge v2
    Provides predictions every 5 minutes during market hours
    """
    
    def __init__(
        self,
        model_path: str = 'models/quantum_edge_v2.pt',
        device: str = None
    ):
        self.model_path = model_path
        self.device = device or ('cuda' if torch.cuda.is_available() else 'cpu')
        
        # Load model and artifacts
        self._load_model()
        
        # Feature engineer
        self.feature_engineer = QuantumEdgeFeatureEngineer()
        
        # Prediction history
        self.prediction_history = []
        
        print(f"✅ QuantumEdge v2 Inference Engine loaded")
        print(f"   Device: {self.device}")
        print(f"   Model: {model_path}")
    
    def _load_model(self):
        """Load trained model and artifacts"""
        
        if not Path(self.model_path).exists():
            raise FileNotFoundError(f"Model not found: {self.model_path}")
        
        checkpoint = torch.load(self.model_path, map_location=self.device)
        
        # Extract hyperparameters
        self.hyperparameters = checkpoint['hyperparameters']
        self.scaler = checkpoint['scaler']
        self.feature_names = checkpoint['feature_names']
        
        # Initialize model
        self.model = TemporalFusionTransformer(
            input_dim=34,
            hidden_dim=self.hyperparameters['hidden_dim'],
            num_heads=self.hyperparameters['num_heads'],
            num_layers=self.hyperparameters['num_layers'],
            dropout=self.hyperparameters['dropout']
        ).to(self.device)
        
        # Load weights
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.model.eval()
        
        print(f"\n✅ Model loaded successfully")
        print(f"   Training date: {checkpoint.get('training_date', 'Unknown')}")
        print(f"   Data period: {checkpoint.get('data_period', {})}")
        print(f"   Hyperparameters: {self.hyperparameters}")
    
    def predict(
        self,
        symbol: str = 'NIFTY',
        timestamp: datetime = None,
        sequence_length: int = None
    ) -> dict:
        """
        Generate prediction for current market state
        
        Args:
            symbol: Trading symbol
            timestamp: Prediction timestamp (None = now)
            sequence_length: Lookback window
            
        Returns:
            dict with prediction results
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        if sequence_length is None:
            sequence_length = self.hyperparameters.get('sequence_length', 12)
        
        # Extract current features and sequence
        features_sequence = self._get_feature_sequence(symbol, timestamp, sequence_length)
        
        if features_sequence is None:
            return {
                'timestamp': timestamp,
                'prediction': 'NEUTRAL',
                'confidence': 0.0,
                'probabilities': {'UP': 0.33, 'FLAT': 0.34, 'DOWN': 0.33},
                'magnitude': 0.0,
                'error': 'Insufficient data'
            }
        
        # Normalize
        features_sequence = self.scaler.transform(features_sequence)
        
        # Convert to tensor
        x = torch.FloatTensor(features_sequence).unsqueeze(0).to(self.device)  # (1, seq_len, features)
        
        # Predict
        with torch.no_grad():
            dir_logits, magnitude, confidence = self.model(x)
            
            # Direction probabilities
            probs = torch.softmax(dir_logits, dim=1).cpu().numpy()[0]
            
            # Predicted direction
            predicted_class = np.argmax(probs)
            direction_map = {0: 'DOWN', 1: 'FLAT', 2: 'UP'}
            predicted_direction = direction_map[predicted_class]
            
            # Confidence
            conf_value = confidence.cpu().item()
            
            # Magnitude
            mag_value = magnitude.cpu().item()
        
        # Build result
        result = {
            'timestamp': timestamp,
            'symbol': symbol,
            'prediction': predicted_direction,
            'confidence': conf_value,
            'probabilities': {
                'DOWN': float(probs[0]),
                'FLAT': float(probs[1]),
                'UP': float(probs[2])
            },
            'expected_magnitude': mag_value,
            'recommended_action': self._get_trading_action(predicted_direction, conf_value, probs),
            'signal_strength': self._calculate_signal_strength(probs, conf_value)
        }
        
        # Store in history
        self.prediction_history.append(result)
        
        return result
    
    def _get_feature_sequence(
        self,
        symbol: str,
        timestamp: datetime,
        sequence_length: int
    ) -> np.ndarray:
        """Get historical feature sequence"""
        
        # Get timestamps for lookback period
        from datetime import timedelta
        
        features_list = []
        
        for i in range(sequence_length):
            ts = timestamp - timedelta(minutes=5 * (sequence_length - i - 1))
            features = self.feature_engineer.extract_features_from_db(symbol, ts)
            
            # Check if valid
            if np.all(features == 0):
                return None
            
            features_list.append(features)
        
        return np.array(features_list)
    
    def _get_trading_action(
        self,
        direction: str,
        confidence: float,
        probs: np.ndarray
    ) -> str:
        """Determine recommended trading action"""
        
        # Only act on high-confidence predictions
        if confidence < 0.6:
            return 'WAIT'
        
        # Check probability spread (edge)
        max_prob = np.max(probs)
        if max_prob < 0.5:
            return 'WAIT'
        
        if direction == 'UP' and confidence > 0.7:
            return 'BUY_CALL'
        elif direction == 'DOWN' and confidence > 0.7:
            return 'BUY_PUT'
        elif direction == 'FLAT':
            return 'WAIT'
        else:
            return 'WAIT'
    
    def _calculate_signal_strength(self, probs: np.ndarray, confidence: float) -> float:
        """Calculate overall signal strength [0-1]"""
        
        # Probability edge
        max_prob = np.max(probs)
        entropy = -np.sum(probs * np.log(probs + 1e-10))
        normalized_entropy = entropy / np.log(3)  # Max entropy for 3 classes
        clarity = 1 - normalized_entropy
        
        # Combined strength
        strength = (max_prob * 0.5 + clarity * 0.3 + confidence * 0.2)
        
        return float(strength)
    
    def predict_live(
        self,
        symbol: str = 'NIFTY',
        interval_seconds: int = 300,  # 5 minutes
        market_hours_only: bool = True
    ):
        """
        Continuous prediction loop for live trading
        
        Args:
            symbol: Trading symbol
            interval_seconds: Prediction interval
            market_hours_only: Only predict during market hours
        """
        
        print(f"\n🚀 Starting live prediction mode")
        print(f"   Symbol: {symbol}")
        print(f"   Interval: {interval_seconds}s ({interval_seconds/60:.0f} minutes)")
        print(f"   Market hours only: {market_hours_only}")
        print(f"\n{'='*80}")
        
        iteration = 0
        
        try:
            while True:
                current_time = datetime.now()
                
                # Check market hours
                if market_hours_only:
                    market_open = current_time.replace(hour=9, minute=15, second=0, microsecond=0)
                    market_close = current_time.replace(hour=15, minute=30, second=0, microsecond=0)
                    
                    if not (market_open <= current_time <= market_close):
                        if iteration % 12 == 0:  # Log every hour
                            print(f"⏸️  [{current_time.strftime('%H:%M:%S')}] Market closed - waiting...")
                        time.sleep(interval_seconds)
                        iteration += 1
                        continue
                
                # Make prediction
                print(f"\n📊 Prediction #{iteration} @ {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"{'-'*80}")
                
                result = self.predict(symbol, current_time)
                
                # Display results
                self._display_prediction(result)
                
                # Wait for next iteration
                time.sleep(interval_seconds)
                iteration += 1
                
        except KeyboardInterrupt:
            print(f"\n\n⏹️  Live prediction stopped")
            print(f"   Total predictions: {len(self.prediction_history)}")
            self._print_summary()
    
    def _display_prediction(self, result: dict):
        """Display prediction results"""
        
        pred = result['prediction']
        conf = result['confidence']
        probs = result['probabilities']
        action = result['recommended_action']
        strength = result['signal_strength']
        
        # Color coding
        pred_color = {
            'UP': '🟢',
            'DOWN': '🔴',
            'FLAT': '⚪'
        }.get(pred, '⚪')
        
        print(f"{pred_color} Prediction: {pred} (Confidence: {conf:.2%})")
        print(f"   Probabilities:")
        print(f"      UP:   {probs['UP']:.2%}")
        print(f"      FLAT: {probs['FLAT']:.2%}")
        print(f"      DOWN: {probs['DOWN']:.2%}")
        print(f"   Signal Strength: {strength:.2%}")
        print(f"   Recommended Action: {action}")
        
        if result.get('expected_magnitude'):
            print(f"   Expected Move: {result['expected_magnitude']:.2f}%")
        
        if result.get('error'):
            print(f"   ⚠️  {result['error']}")
    
    def _print_summary(self):
        """Print prediction summary statistics"""
        
        if not self.prediction_history:
            return
        
        print(f"\n{'='*80}")
        print("PREDICTION SUMMARY")
        print(f"{'='*80}")
        
        predictions = [p['prediction'] for p in self.prediction_history]
        confidences = [p['confidence'] for p in self.prediction_history]
        
        print(f"\n📊 Distribution:")
        print(f"   UP:   {predictions.count('UP'):3d} ({predictions.count('UP')/len(predictions)*100:.1f}%)")
        print(f"   FLAT: {predictions.count('FLAT'):3d} ({predictions.count('FLAT')/len(predictions)*100:.1f}%)")
        print(f"   DOWN: {predictions.count('DOWN'):3d} ({predictions.count('DOWN')/len(predictions)*100:.1f}%)")
        
        print(f"\n📊 Confidence:")
        print(f"   Average: {np.mean(confidences):.2%}")
        print(f"   High (>70%): {sum(c > 0.7 for c in confidences)} predictions")
        
        # High-confidence predictions
        high_conf = [p for p in self.prediction_history if p['confidence'] > 0.7]
        if high_conf:
            print(f"\n🎯 High-Confidence Predictions ({len(high_conf)}):")
            for p in high_conf[-5:]:  # Last 5
                print(f"   {p['timestamp'].strftime('%H:%M')} | {p['prediction']:5s} | "
                      f"Conf: {p['confidence']:.2%} | Action: {p['recommended_action']}")
    
    def get_latest_prediction(self) -> dict:
        """Get most recent prediction"""
        if self.prediction_history:
            return self.prediction_history[-1]
        return None
    
    def export_predictions(self, filepath: str = 'predictions.csv'):
        """Export prediction history to CSV"""
        import pandas as pd
        
        if not self.prediction_history:
            print("No predictions to export")
            return
        
        df = pd.DataFrame([{
            'timestamp': p['timestamp'],
            'symbol': p['symbol'],
            'prediction': p['prediction'],
            'confidence': p['confidence'],
            'prob_up': p['probabilities']['UP'],
            'prob_flat': p['probabilities']['FLAT'],
            'prob_down': p['probabilities']['DOWN'],
            'magnitude': p.get('expected_magnitude', 0),
            'action': p['recommended_action'],
            'strength': p['signal_strength']
        } for p in self.prediction_history])
        
        df.to_csv(filepath, index=False)
        print(f"✅ Predictions exported to {filepath}")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='QuantumEdge v2 Inference Engine')
    parser.add_argument('--model', type=str, default='models/quantum_edge_v2.pt',
                       help='Path to trained model')
    parser.add_argument('--symbol', type=str, default='NIFTY',
                       help='Trading symbol')
    parser.add_argument('--mode', type=str, choices=['single', 'live'], default='single',
                       help='Prediction mode')
    parser.add_argument('--interval', type=int, default=300,
                       help='Prediction interval in seconds (live mode)')
    
    args = parser.parse_args()
    
    # Initialize inference engine
    engine = QuantumEdgeInference(model_path=args.model)
    
    if args.mode == 'single':
        # Single prediction
        print(f"\n📊 Single Prediction Mode")
        print(f"{'='*80}")
        
        result = engine.predict(symbol=args.symbol)
        engine._display_prediction(result)
        
        print(f"\n{'='*80}")
        
    else:
        # Live prediction loop
        engine.predict_live(
            symbol=args.symbol,
            interval_seconds=args.interval,
            market_hours_only=True
        )


if __name__ == "__main__":
    main()
