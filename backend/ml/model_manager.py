"""
ML Model Manager
Manages machine learning models for signal scoring
"""

import os
import joblib
import pandas as pd
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import accuracy_score, roc_auc_score, classification_report, confusion_matrix
import warnings
warnings.filterwarnings('ignore')

from backend.core.logger import get_ml_logger

logger = get_ml_logger()


class ModelManager:
    """Manages ML models lifecycle"""
    
    def __init__(self, model_dir: str = "models"):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        
        self.model = None
        self.model_version = "v1.0.0"  # Semantic versioning: major.minor.patch
        self.model_hash = None  # Hash of model file for exact traceability
        self.model_loaded_at = None  # Timestamp when model was loaded
        self.feature_names = []
        self.feature_importance = {}
        self.training_count = 0
        self.min_training_samples = 100
        self.model_metrics = {}
        
    async def load_models(self):
        """Load ML models from disk"""
        try:
            model_path = self.model_dir / f"signal_scorer_{self.model_version}.pkl"
            metadata_path = self.model_dir / f"model_metadata_{self.model_version}.pkl"
            
            if model_path.exists():
                self.model = joblib.load(model_path)
                self.model_loaded_at = datetime.now().isoformat()
                
                # Calculate model hash for traceability
                import hashlib
                with open(model_path, 'rb') as f:
                    self.model_hash = hashlib.sha256(f.read()).hexdigest()[:16]
                
                logger.info(f"✓ ML model loaded: {model_path} (version: {self.model_version}, hash: {self.model_hash})")
                
                # Load metadata
                if metadata_path.exists():
                    metadata = joblib.load(metadata_path)
                    self.feature_names = metadata.get('feature_names', [])
                    self.feature_importance = metadata.get('feature_importance', {})
                    self.model_metrics = metadata.get('metrics', {})
                    logger.info(f"✓ Model metadata loaded - Accuracy: {self.model_metrics.get('accuracy', 0):.3f}")
            else:
                logger.warning("No existing model found. Will train when enough data is collected.")
                self.model = None
                
        except Exception as e:
            logger.error(f"Error loading ML model: {e}")
            self.model = None
    
    async def score_signals(self, signals: List, market_state: Dict) -> List:
        """
        Score signals using ML model.
        
        Adds ML telemetry:
        - model_version: Version of model used for scoring
        - model_hash: Hash of model file
        - features_snapshot: Dict of features used for prediction
        - ml_confidence: Model's prediction probability
        """
        
        if not self.model:
            # Return signals with default ML probability
            for signal in signals:
                if hasattr(signal, 'ml_probability'):
                    signal.ml_probability = signal.strength / 100
                if hasattr(signal, 'ml_confidence'):
                    signal.ml_confidence = signal.strength / 100
                signal.model_version = None
                signal.model_hash = None
                signal.features_snapshot = {}
                signal.metadata.setdefault('ml', {})
                signal.metadata['ml'].update({
                    'model_version': None,
                    'model_hash': None,
                    'confidence': signal.ml_confidence,
                    'features': {}
                })
            return signals
        
        try:
            # Extract features for each signal
            for signal in signals:
                features = self._extract_features(signal, market_state)
                
                # Create feature snapshot (map feature names to values)
                features_snapshot = {}
                if len(self.feature_names) == len(features):
                    features_snapshot = {name: value for name, value in zip(self.feature_names, features)}
                else:
                    # Fallback if feature names not available
                    features_snapshot = {f'feature_{i}': value for i, value in enumerate(features)}
                
                # Predict probability
                if len(features) > 0:
                    probability = self.model.predict_proba([features])[0][1]
                    signal.ml_probability = probability
                    signal.ml_confidence = probability
                else:
                    signal.ml_probability = signal.strength / 100
                    signal.ml_confidence = signal.strength / 100
                
                # Add ML telemetry
                signal.model_version = self.model_version
                signal.model_hash = self.model_hash
                signal.features_snapshot = features_snapshot
                signal.metadata.setdefault('ml', {})
                signal.metadata['ml'].update({
                    'model_version': self.model_version,
                    'model_hash': self.model_hash,
                    'confidence': signal.ml_confidence,
                    'features': features_snapshot
                })
            
            return signals
            
        except Exception as e:
            logger.error(f"Error scoring signals: {e}")
            return signals
    
    def _extract_features(self, signal, market_state: Dict) -> List[float]:
        """Extract features from signal and market state matching training dataset"""
        features = []
        
        try:
            symbol_data = market_state.get(signal.symbol, {})
            option_chain = symbol_data.get('option_chain', {})
            spot_price = symbol_data.get('spot_price', 0)
            expiry = symbol_data.get('expiry')
            
            # Get option data
            direction = signal.direction
            strike = signal.strike
            
            if direction == "CALL":
                option_data = option_chain.get('calls', {}).get(strike, {})
                is_call = 1
            else:
                option_data = option_chain.get('puts', {}).get(strike, {})
                is_call = 0
            
            # Greeks
            delta = option_data.get('delta', 0.0)
            gamma = option_data.get('gamma', 0.0)
            theta = option_data.get('theta', 0.0)
            vega = option_data.get('vega', 0.0)
            
            # Market context
            iv = option_data.get('iv', 20.0)
            vix = symbol_data.get('vix', 15.0)
            pcr = option_chain.get('pcr', 1.0)
            
            # Time features
            now = datetime.now()
            entry_hour = now.hour
            entry_minute = now.minute
            
            # Time to expiry
            if expiry:
                try:
                    from datetime import datetime as dt
                    expiry_dt = dt.fromisoformat(expiry) if isinstance(expiry, str) else expiry
                    time_to_expiry = (expiry_dt - now).days if expiry_dt > now else 0
                except:
                    time_to_expiry = 7
            else:
                time_to_expiry = 7
            
            # Moneyness
            moneyness = (spot_price - strike) / spot_price if spot_price > 0 else 0
            
            # Risk metrics
            risk_reward = getattr(signal, 'risk_reward_ratio', 1.0)
            
            # Match training feature order exactly (24 features)
            features = [
                signal.strength / 100,          # signal_strength
                getattr(signal, 'strategy_weight', 5),  # strategy_weight
                delta,                          # delta_entry
                gamma,                          # gamma_entry
                theta,                          # theta_entry
                vega,                           # vega_entry
                abs(delta),                     # abs_delta
                abs(gamma),                     # abs_gamma
                abs(theta),                     # abs_theta
                abs(vega),                      # abs_vega
                spot_price,                     # spot_entry
                iv,                             # iv_entry
                vix,                            # vix_entry
                pcr,                            # pcr_entry
                moneyness,                      # moneyness
                time_to_expiry,                 # time_to_expiry
                is_call,                        # is_call
                risk_reward,                    # risk_reward
                0.0,                            # position_size (not available at signal time)
                entry_hour,                     # entry_hour
                entry_minute,                   # entry_minute
                iv / vix if vix > 0 else 1.0,   # iv_vix_ratio
                gamma / vega if vega != 0 else 0.0,  # gamma_vega_ratio
                theta * time_to_expiry if time_to_expiry > 0 else 0.0  # theta_per_day
            ]
            
        except Exception as e:
            logger.error(f"Error extracting features: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        return features
    
    async def train_model(self, training_df: pd.DataFrame) -> bool:
        """
        Train/retrain ML model using XGBoost
        
        Args:
            training_df: DataFrame with features and target variable
            
        Returns:
            True if training successful, False otherwise
        """
        try:
            if len(training_df) < self.min_training_samples:
                logger.info(f"Not enough data to train. Need {self.min_training_samples}, have {len(training_df)}")
                return False
            
            logger.info(f"=== Training ML Model with {len(training_df)} samples ===")
            
            # Define feature columns (exclude identifiers and target)
            exclude_cols = ['trade_id', 'entry_time', 'strategy_name', 'is_winner', 'pnl_percent', 'hold_duration']
            feature_cols = [col for col in training_df.columns if col not in exclude_cols]
            
            # Prepare features and target
            X = training_df[feature_cols]
            y = training_df['is_winner']
            
            # Handle missing values
            X = X.fillna(0)
            
            # Check class balance
            win_rate = y.mean()
            logger.info(f"Win rate in training data: {win_rate:.1%}")
            
            if win_rate < 0.1 or win_rate > 0.9:
                logger.warning(f"Imbalanced dataset - win rate: {win_rate:.1%}")
            
            # Train/test split (80/20)
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, 
                test_size=0.2, 
                random_state=42,
                stratify=y if len(y.unique()) > 1 else None
            )
            
            logger.info(f"Training set: {len(X_train)} samples")
            logger.info(f"Test set: {len(X_test)} samples")
            
            # Calculate scale_pos_weight for imbalanced data
            negative_count = (y_train == 0).sum()
            positive_count = (y_train == 1).sum()
            scale_pos_weight = negative_count / positive_count if positive_count > 0 else 1.0
            
            # Train XGBoost model
            logger.info("Training XGBoost classifier...")
            
            self.model = xgb.XGBClassifier(
                n_estimators=100,
                max_depth=5,
                learning_rate=0.1,
                objective='binary:logistic',
                eval_metric='auc',
                scale_pos_weight=scale_pos_weight,
                random_state=42,
                n_jobs=-1
            )
            
            # Fit model
            self.model.fit(
                X_train, y_train,
                eval_set=[(X_test, y_test)],
                verbose=False
            )
            
            # Predictions
            y_pred = self.model.predict(X_test)
            y_pred_proba = self.model.predict_proba(X_test)[:, 1]
            
            # Calculate metrics
            accuracy = accuracy_score(y_test, y_pred)
            auc = roc_auc_score(y_test, y_pred_proba)
            
            # Cross-validation score
            cv_scores = cross_val_score(self.model, X, y, cv=3, scoring='accuracy')
            cv_mean = cv_scores.mean()
            cv_std = cv_scores.std()
            
            # Store metrics
            self.model_metrics = {
                'accuracy': accuracy,
                'auc': auc,
                'cv_mean': cv_mean,
                'cv_std': cv_std,
                'train_samples': len(X_train),
                'test_samples': len(X_test),
                'win_rate': win_rate,
                'training_date': datetime.now().isoformat()
            }
            
            # Feature importance
            self.feature_names = feature_cols
            importance_values = self.model.feature_importances_
            self.feature_importance = dict(zip(feature_cols, importance_values))
            
            # Sort by importance
            sorted_importance = sorted(self.feature_importance.items(), key=lambda x: x[1], reverse=True)
            
            # Log results
            logger.info(f"✓ Model Training Complete")
            logger.info(f"  Accuracy: {accuracy:.3f}")
            logger.info(f"  AUC: {auc:.3f}")
            logger.info(f"  CV Score: {cv_mean:.3f} (+/- {cv_std:.3f})")
            
            logger.info(f"\nTop 10 Most Important Features:")
            for i, (feature, importance) in enumerate(sorted_importance[:10], 1):
                logger.info(f"  {i}. {feature}: {importance:.4f}")
            
            # Classification report
            logger.info(f"\nClassification Report:")
            report = classification_report(y_test, y_pred, target_names=['Losing', 'Winning'])
            logger.info(f"\n{report}")
            
            # Confusion matrix
            cm = confusion_matrix(y_test, y_pred)
            logger.info(f"\nConfusion Matrix:")
            logger.info(f"  True Negatives: {cm[0][0]}, False Positives: {cm[0][1]}")
            logger.info(f"  False Negatives: {cm[1][0]}, True Positives: {cm[1][1]}")
            
            # Save model
            await self.save_model()
            
            return True
            
        except Exception as e:
            logger.error(f"Error training ML model: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def should_retrain(self) -> bool:
        """Check if model should be retrained"""
        # Retrain every 20 trades
        self.training_count += 1
        return self.training_count >= 20
    
    async def save_model(self):
        """Save ML model and metadata to disk"""
        try:
            if self.model:
                # Save model
                model_path = self.model_dir / f"signal_scorer_{self.model_version}.pkl"
                joblib.dump(self.model, model_path)
                logger.info(f"✓ ML model saved: {model_path}")
                
                # Save metadata
                metadata = {
                    'feature_names': self.feature_names,
                    'feature_importance': self.feature_importance,
                    'metrics': self.model_metrics,
                    'version': self.model_version,
                    'saved_at': datetime.now().isoformat()
                }
                
                metadata_path = self.model_dir / f"model_metadata_{self.model_version}.pkl"
                joblib.dump(metadata, metadata_path)
                logger.info(f"✓ Model metadata saved: {metadata_path}")
                
        except Exception as e:
            logger.error(f"Error saving ML model: {e}")
    
    def get_model_info(self) -> Dict:
        """Get information about current model"""
        if not self.model:
            return {
                'model_loaded': False,
                'message': 'No model loaded'
            }
        
        # Convert numpy types to Python native types for JSON serialization
        metrics_serializable = {}
        for k, v in self.model_metrics.items():
            if hasattr(v, 'item'):  # numpy scalar
                metrics_serializable[k] = v.item()
            else:
                metrics_serializable[k] = v
        
        # Convert feature importance values
        top_features = []
        for name, importance in sorted(
            self.feature_importance.items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:10]:
            top_features.append({
                'name': name,
                'importance': float(importance)
            })
        
        return {
            'model_loaded': True,
            'version': self.model_version,
            'metrics': metrics_serializable,
            'num_features': len(self.feature_names),
            'top_features': top_features
        }
