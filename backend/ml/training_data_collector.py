"""
Training Data Collector
Extracts features from closed trades for ML training
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from pathlib import Path

from backend.core.logger import get_logger
from backend.database.models import Trade
from backend.database.database import get_db

logger = get_logger(__name__)


class TrainingDataCollector:
    """Collects and prepares training data from closed trades"""
    
    def __init__(self, db=None):
        self.db = db  # Database module (not used directly, we use get_db())
        self.training_dir = Path("data/training")
        self.training_dir.mkdir(parents=True, exist_ok=True)
        
    async def collect_daily_data(self, date: datetime = None, lookback_days: int = 30) -> pd.DataFrame:
        """
        Collect all features from trades closed within lookback period
        
        Args:
            date: End date (defaults to now)
            lookback_days: Number of days to look back (default 30, use 0 for all time)
            
        Returns:
            DataFrame with all features and target variable
        """
        try:
            # Query closed trades
            session = next(get_db())
            
            if date is None:
                date = datetime.now()
            
            # Build query based on lookback
            query = session.query(Trade).filter(
                Trade.status == "CLOSED",
                Trade.entry_price > 0  # Exclude invalid trades with zero entry price
            )
            
            # Add time filter if lookback specified
            if lookback_days > 0:
                start_time = date - timedelta(days=lookback_days)
                query = query.filter(Trade.exit_time >= start_time)
            
            trades = query.all()
            
            if lookback_days > 0:
                logger.info(f"Found {len(trades)} closed trades in last {lookback_days} days")
            else:
                logger.info(f"Found {len(trades)} closed trades (all time)")

            
            if len(trades) == 0:
                return pd.DataFrame()
            
            # Extract features from each trade
            training_data = []
            
            for trade in trades:
                try:
                    features = self._extract_features(trade)
                    if features:
                        training_data.append(features)
                except Exception as e:
                    logger.error(f"Error extracting features from trade {trade.trade_id}: {e}")
            
            session.close()
            
            # Convert to DataFrame
            df = pd.DataFrame(training_data)
            
            logger.info(f"Extracted features from {len(df)} trades")
            
            return df
            
        except Exception as e:
            logger.error(f"Error collecting daily data: {e}")
            return pd.DataFrame()
    
    def _extract_features(self, trade: Trade) -> Optional[Dict]:
        """
        Extract all features from a single trade
        
        Args:
            trade: Trade object from database
            
        Returns:
            Dictionary with features and target variable
        """
        try:
            # Skip if critical data is missing (check for None, not falsy values like 0.0)
            if trade.delta_entry is None or not trade.entry_price or not trade.spot_price_entry:
                logger.debug(f"Skipping trade {trade.trade_id} - missing critical data")
                return None
            
            # Calculate additional features
            moneyness = (trade.spot_price_entry - trade.strike_price) / trade.spot_price_entry
            
            if trade.expiry_date and trade.entry_time:
                time_to_expiry = (trade.expiry_date - trade.entry_time).days
            else:
                time_to_expiry = 7  # Default
            
            # Entry Greeks
            delta_entry = trade.delta_entry or 0.0
            gamma_entry = trade.gamma_entry or 0.0
            theta_entry = trade.theta_entry or 0.0
            vega_entry = trade.vega_entry or 0.0
            
            # Market context
            spot_entry = trade.spot_price_entry or 0.0
            iv_entry = trade.iv_entry or 20.0
            vix_entry = trade.vix_entry or 15.0
            pcr_entry = trade.pcr_entry or 1.0
            
            # Signal quality
            signal_strength = trade.signal_strength or 50.0
            strategy_weight = trade.strategy_weight or 5
            
            # Risk metrics
            risk_reward = trade.risk_reward_ratio or 1.0
            position_size = trade.position_size_pct or 0.0
            
            # Target variable
            is_winner = 1 if trade.is_winning_trade else 0
            pnl_percent = trade.pnl_percentage or 0.0
            
            # Hold duration
            hold_duration = trade.hold_duration_minutes or 0
            
            # Option type encoding
            is_call = 1 if trade.instrument_type == "CALL" else 0
            
            # Time features
            entry_hour = trade.entry_time.hour if trade.entry_time else 9
            entry_minute = trade.entry_time.minute if trade.entry_time else 15
            
            # Strategy encoding (one-hot would be better, but keep simple for now)
            strategy_name = trade.strategy_name or "Unknown"
            
            features = {
                # Trade identification (not used in training)
                'trade_id': trade.trade_id,
                'entry_time': trade.entry_time,
                'strategy_name': strategy_name,
                
                # Signal features
                'signal_strength': signal_strength,
                'strategy_weight': strategy_weight,
                
                # Greeks at entry
                'delta_entry': delta_entry,
                'gamma_entry': gamma_entry,
                'theta_entry': theta_entry,
                'vega_entry': vega_entry,
                
                # Absolute Greeks (magnitude)
                'abs_delta': abs(delta_entry),
                'abs_gamma': abs(gamma_entry),
                'abs_theta': abs(theta_entry),
                'abs_vega': abs(vega_entry),
                
                # Market context
                'spot_entry': spot_entry,
                'iv_entry': iv_entry,
                'vix_entry': vix_entry,
                'pcr_entry': pcr_entry,
                
                # Option characteristics
                'moneyness': moneyness,
                'time_to_expiry': time_to_expiry,
                'is_call': is_call,
                
                # Risk metrics
                'risk_reward': risk_reward,
                'position_size': position_size,
                
                # Time features
                'entry_hour': entry_hour,
                'entry_minute': entry_minute,
                
                # Derived features
                'iv_vix_ratio': iv_entry / vix_entry if vix_entry > 0 else 1.0,
                'gamma_vega_ratio': gamma_entry / vega_entry if vega_entry != 0 else 0.0,
                'theta_per_day': theta_entry * time_to_expiry if time_to_expiry > 0 else 0.0,
                
                # Target variables
                'is_winner': is_winner,
                'pnl_percent': pnl_percent,
                'hold_duration': hold_duration
            }
            
            return features
            
        except Exception as e:
            logger.error(f"Error extracting features: {e}")
            return None
    
    async def save_training_data(self, df: pd.DataFrame, filename: str) -> str:
        """
        Save training data to CSV
        
        Args:
            df: DataFrame with training data
            filename: Name of file to save
            
        Returns:
            Path to saved file
        """
        try:
            if df.empty:
                logger.warning("Empty DataFrame - nothing to save")
                return ""
            
            filepath = self.training_dir / filename
            df.to_csv(filepath, index=False)
            
            logger.info(f"✓ Saved {len(df)} training samples to {filepath}")
            
            return str(filepath)
            
        except Exception as e:
            logger.error(f"Error saving training data: {e}")
            return ""
    
    async def load_all_training_data(self) -> pd.DataFrame:
        """
        Load all historical training data from CSV files
        
        Returns:
            Combined DataFrame with all historical data
        """
        try:
            all_files = sorted(self.training_dir.glob("trades_*.csv"))
            
            if not all_files:
                logger.warning("No training data files found")
                return pd.DataFrame()
            
            # Load and combine all files
            dfs = []
            for file in all_files:
                try:
                    df = pd.read_csv(file)
                    dfs.append(df)
                except Exception as e:
                    logger.error(f"Error loading {file}: {e}")
            
            if not dfs:
                return pd.DataFrame()
            
            combined_df = pd.concat(dfs, ignore_index=True)
            
            # Remove duplicates based on trade_id
            combined_df = combined_df.drop_duplicates(subset=['trade_id'], keep='last')
            
            logger.info(f"Loaded {len(combined_df)} training samples from {len(all_files)} files")
            
            return combined_df
            
        except Exception as e:
            logger.error(f"Error loading training data: {e}")
            return pd.DataFrame()
    
    async def get_training_statistics(self) -> Dict:
        """
        Get statistics about training data
        
        Returns:
            Dictionary with statistics
        """
        try:
            df = await self.load_all_training_data()
            
            if df.empty:
                return {
                    'total_samples': 0,
                    'winning_trades': 0,
                    'losing_trades': 0,
                    'win_rate': 0.0
                }
            
            stats = {
                'total_samples': len(df),
                'winning_trades': int(df['is_winner'].sum()),
                'losing_trades': int((df['is_winner'] == 0).sum()),
                'win_rate': float(df['is_winner'].mean() * 100),
                'avg_pnl_percent': float(df['pnl_percent'].mean()),
                'avg_hold_duration': float(df['hold_duration'].mean()),
                'date_range': {
                    'start': df['entry_time'].min(),
                    'end': df['entry_time'].max()
                }
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting training statistics: {e}")
            return {}
