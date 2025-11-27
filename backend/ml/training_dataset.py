"""
Training Dataset Pipeline

Logs executed trades with features and outcomes for ML model training.
"""

from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path
import csv
import json
import logging

logger = logging.getLogger(__name__)


class TrainingDatasetPipeline:
    """
    Collects and logs training data from executed trades.
    
    Features logged:
    - Market data: spot price, IV, VIX, PCR, OI metrics
    - Technical indicators: RSI, MACD, Bollinger Bands (when available)
    - Greeks: Delta, Gamma, Theta, Vega
    - Temporal: Time of day, day of week, days to expiry
    - Trade context: Strategy, signal strength, position size
    
    Outcomes logged:
    - P&L (absolute and percentage)
    - Win/loss binary
    - Hold duration
    - Exit reason
    """
    
    def __init__(self, dataset_path: str = "data/training_dataset.csv"):
        self.dataset_path = Path(dataset_path)
        self.dataset_path.parent.mkdir(parents=True, exist_ok=True)
        
        # CSV header
        self.fieldnames = [
            # Identifiers
            'trade_id', 'timestamp', 'strategy',
            
            # Market data at entry
            'spot_price', 'strike_price', 'option_type', 'days_to_expiry',
            'iv', 'vix', 'pcr', 'total_call_oi', 'total_put_oi',
            
            # Greeks at entry
            'delta', 'gamma', 'theta', 'vega',
            
            # Technical indicators at entry
            'rsi', 'macd', 'macd_signal', 'bb_upper', 'bb_lower', 'bb_middle',
            
            # Temporal features
            'hour_of_day', 'day_of_week', 'is_market_open_hour',
            
            # Trade details
            'entry_price', 'quantity', 'signal_strength', 'side',
            
            # Market data at exit
            'exit_spot_price', 'exit_iv',
            
            # Outcomes
            'exit_price', 'pnl', 'pnl_pct', 'is_winning', 
            'hold_duration_minutes', 'exit_reason'
        ]
        
        # Initialize CSV if it doesn't exist
        if not self.dataset_path.exists():
            self._initialize_csv()
            logger.info(f"Training dataset initialized at {self.dataset_path}")
        else:
            logger.info(f"Using existing training dataset at {self.dataset_path}")
    
    def _initialize_csv(self):
        """Create CSV file with header"""
        with open(self.dataset_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=self.fieldnames)
            writer.writeheader()
    
    def log_trade(self, trade: Dict, market_state: Dict):
        """
        Log a completed trade to the training dataset.
        
        Args:
            trade: Trade dictionary with entry/exit details
            market_state: Market state at the time of trade execution
        """
        try:
            # Extract features
            entry_time = trade.get('entry_time', datetime.now())
            if isinstance(entry_time, str):
                entry_time = datetime.fromisoformat(entry_time)
            
            # Temporal features
            hour_of_day = entry_time.hour
            day_of_week = entry_time.weekday()  # 0=Monday, 6=Sunday
            is_market_open_hour = 1 if 9 <= hour_of_day <= 15 else 0
            
            # Calculate days to expiry
            expiry_str = trade.get('expiry')
            days_to_expiry = None
            if expiry_str:
                try:
                    expiry_date = datetime.strptime(expiry_str, '%Y-%m-%d')
                    days_to_expiry = (expiry_date - entry_time).days
                except:
                    pass
            
            # Calculate P&L percentage
            entry_price = trade.get('entry_price', 0)
            exit_price = trade.get('exit_price', 0)
            quantity = trade.get('quantity', 1)
            pnl = trade.get('pnl', 0)
            pnl_pct = (pnl / (entry_price * quantity) * 100) if entry_price and quantity else 0
            
            # Prepare row
            row = {
                # Identifiers
                'trade_id': trade.get('id', ''),
                'timestamp': entry_time.isoformat(),
                'strategy': trade.get('strategy', ''),
                
                # Market data at entry
                'spot_price': trade.get('spot_price_entry', 0),
                'strike_price': trade.get('strike', 0),
                'option_type': trade.get('direction', 'CALL'),
                'days_to_expiry': days_to_expiry,
                'iv': trade.get('iv', 0),
                'vix': market_state.get('vix', 0),
                'pcr': market_state.get('pcr', 0),
                'total_call_oi': market_state.get('total_call_oi', 0),
                'total_put_oi': market_state.get('total_put_oi', 0),
                
                # Greeks at entry
                'delta': trade.get('delta', 0),
                'gamma': trade.get('gamma', 0),
                'theta': trade.get('theta', 0),
                'vega': trade.get('vega', 0),
                
                # Technical indicators at entry (placeholder - would come from market_state)
                'rsi': market_state.get('rsi', 0),
                'macd': market_state.get('macd', 0),
                'macd_signal': market_state.get('macd_signal', 0),
                'bb_upper': market_state.get('bb_upper', 0),
                'bb_lower': market_state.get('bb_lower', 0),
                'bb_middle': market_state.get('bb_middle', 0),
                
                # Temporal features
                'hour_of_day': hour_of_day,
                'day_of_week': day_of_week,
                'is_market_open_hour': is_market_open_hour,
                
                # Trade details
                'entry_price': entry_price,
                'quantity': quantity,
                'signal_strength': trade.get('signal_strength', 0),
                'side': trade.get('side', 'BUY'),
                
                # Market data at exit
                'exit_spot_price': trade.get('spot_price_exit', 0),
                'exit_iv': trade.get('exit_iv', 0),
                
                # Outcomes
                'exit_price': exit_price,
                'pnl': pnl,
                'pnl_pct': round(pnl_pct, 2),
                'is_winning': 1 if pnl > 0 else 0,
                'hold_duration_minutes': trade.get('hold_duration_minutes', 0),
                'exit_reason': trade.get('exit_reason', 'MANUAL')
            }
            
            # Append to CSV
            with open(self.dataset_path, 'a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=self.fieldnames)
                writer.writerow(row)
            
            logger.info(f"Logged trade {trade.get('id')} to training dataset")
            
        except Exception as e:
            logger.error(f"Error logging trade to training dataset: {e}")
    
    def get_dataset_stats(self) -> Dict:
        """Get statistics about the training dataset"""
        if not self.dataset_path.exists():
            return {
                'total_records': 0,
                'file_size_mb': 0,
                'path': str(self.dataset_path)
            }
        
        # Count rows (excluding header)
        with open(self.dataset_path, 'r') as f:
            row_count = sum(1 for _ in f) - 1  # Subtract header
        
        # Get file size
        file_size_mb = self.dataset_path.stat().st_size / (1024 * 1024)
        
        return {
            'total_records': row_count,
            'file_size_mb': round(file_size_mb, 2),
            'path': str(self.dataset_path),
            'last_modified': datetime.fromtimestamp(self.dataset_path.stat().st_mtime).isoformat()
        }
    
    def export_to_json(self, output_path: str = None) -> str:
        """
        Export CSV dataset to JSON format.
        
        Args:
            output_path: Output JSON file path (default: same as CSV but .json)
        
        Returns:
            Path to exported JSON file
        """
        if output_path is None:
            output_path = str(self.dataset_path).replace('.csv', '.json')
        
        records = []
        with open(self.dataset_path, 'r') as f:
            reader = csv.DictReader(f)
            records = list(reader)
        
        with open(output_path, 'w') as f:
            json.dump(records, f, indent=2)
        
        logger.info(f"Exported {len(records)} records to {output_path}")
        return output_path
    
    def get_sample_records(self, n: int = 10) -> List[Dict]:
        """Get sample records from the dataset"""
        if not self.dataset_path.exists():
            return []
        
        records = []
        with open(self.dataset_path, 'r') as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if i >= n:
                    break
                records.append(row)
        
        return records
