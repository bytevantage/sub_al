"""
Quantum Edge v2 - Feature Engineering
Extracts 34 institutional-grade features from clean option chain data
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional
import subprocess
from pathlib import Path

class QuantumEdgeFeatureEngineer:
    """
    Extracts 34-dimensional feature vector from option chain snapshots
    Uses only CLEAN data for reliable predictions
    """
    
    FEATURE_NAMES = [
        # 0-3: Spot Price & Returns
        'spot_price_norm',
        'return_1bar', 'return_3bar', 'return_9bar',
        
        # 4: VIX Proxy
        'atm_iv_percentile',
        
        # 5-8: PCR Metrics
        'pcr_oi', 'pcr_volume', 'pcr_oi_change', 'pcr_value',
        
        # 9-11: Max Pain
        'max_pain_distance', 'max_pain_strike_norm', 'max_pain_pull_strength',
        
        # 12-15: Dealer GEX (Gamma Exposure)
        'dealer_gex_total', 'dealer_gex_near_expiry', 'dealer_gex_direction', 'gex_flip_proximity',
        
        # 16-19: Gamma Profile
        'net_gamma', 'otm_put_gamma', 'otm_call_gamma', 'gamma_slope',
        
        # 20-22: IV Features
        'iv_skew_25delta', 'iv_term_structure', 'iv_rank_30d',
        
        # 23-26: OI Velocity
        'oi_velocity_5min', 'oi_velocity_15min', 'call_oi_velocity', 'put_oi_velocity',
        
        # 27-28: Order Flow
        'order_imbalance', 'large_trade_flow',
        
        # 29-31: Technical
        'vwap_zscore', 'rsi_14', 'adx_14',
        
        # 32-33: Time
        'time_to_expiry_hours', 'intraday_minutes'
    ]
    
    def __init__(self):
        self.spot_norm_factor = 25000.0
        self.lookback_periods = {'short': 5, 'medium': 15, 'long': 30}
        
    def extract_features_from_db(
        self, 
        symbol: str = 'NIFTY',
        timestamp: Optional[datetime] = None,
        lookback_minutes: int = 60
    ) -> np.ndarray:
        """
        Extract features from database for a given timestamp
        
        Args:
            symbol: Symbol to analyze (NIFTY/SENSEX)
            timestamp: Target timestamp (None = latest)
            lookback_minutes: Historical data window
            
        Returns:
            34-dim numpy array
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        # Fetch option chain data
        df = self._fetch_option_chain(symbol, timestamp, lookback_minutes)
        
        if df.empty:
            print(f"⚠️  No data for {symbol} at {timestamp}")
            return np.zeros(34, dtype=np.float32)
        
        # Build feature vector
        features = self._compute_features(df, timestamp)
        
        return features
    
    def _fetch_option_chain(
        self, 
        symbol: str, 
        timestamp: datetime, 
        lookback_minutes: int
    ) -> pd.DataFrame:
        """Fetch clean option chain data from database"""
        
        start_time = timestamp - timedelta(minutes=lookback_minutes)
        
        # Export via Docker
        query = f"""
        docker exec trading_db psql -U trading_user -d trading_db -t -A -F"," -c "
        SELECT 
            timestamp, strike_price, option_type, ltp, bid, ask,
            volume, oi, oi_change, delta, gamma, theta, vega, iv, spot_price, expiry
        FROM option_chain_snapshots_clean
        WHERE symbol = '{symbol}'
          AND timestamp BETWEEN '{start_time}' AND '{timestamp}'
        ORDER BY timestamp, strike_price;
        " > /tmp/quantum_features.csv
        """
        
        subprocess.run(query, shell=True, capture_output=True)
        
        try:
            df = pd.read_csv('/tmp/quantum_features.csv', names=[
                'timestamp', 'strike', 'option_type', 'ltp', 'bid', 'ask',
                'volume', 'oi', 'oi_change', 'delta', 'gamma', 'theta', 'vega', 'iv', 'spot', 'expiry'
            ])
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df['expiry'] = pd.to_datetime(df['expiry'], format='mixed', errors='coerce')
            return df
        except:
            return pd.DataFrame()
    
    def _compute_features(self, df: pd.DataFrame, target_time: datetime) -> np.ndarray:
        """Compute all 34 features"""
        
        features = np.zeros(34, dtype=np.float32)
        
        # Get current snapshot
        current = df[df['timestamp'] == target_time]
        if current.empty:
            current = df[df['timestamp'] == df['timestamp'].max()]
        
        if current.empty:
            return features
        
        spot = current['spot'].iloc[0]
        
        # ============================================================================
        # FEATURES 0-3: Spot Price & Returns
        # ============================================================================
        features[0] = spot / self.spot_norm_factor
        
        timestamps = sorted(df['timestamp'].unique())
        current_idx = len(timestamps) - 1
        
        if current_idx >= 1:
            prev_spot = df[df['timestamp'] == timestamps[current_idx-1]]['spot'].iloc[0]
            features[1] = (spot / prev_spot - 1) * 100
        
        if current_idx >= 3:
            prev_spot_3 = df[df['timestamp'] == timestamps[current_idx-3]]['spot'].iloc[0]
            features[2] = (spot / prev_spot_3 - 1) * 100
        
        if current_idx >= 9:
            prev_spot_9 = df[df['timestamp'] == timestamps[current_idx-9]]['spot'].iloc[0]
            features[3] = (spot / prev_spot_9 - 1) * 100
        
        # ============================================================================
        # FEATURE 4: ATM IV Percentile
        # ============================================================================
        atm = current[(current['strike'] >= spot * 0.98) & (current['strike'] <= spot * 1.02)]
        current_iv = atm['iv'].mean() if not atm.empty else 20
        
        historical_iv = []
        for ts in timestamps:
            ts_data = df[df['timestamp'] == ts]
            if not ts_data.empty:
                ts_spot = ts_data['spot'].iloc[0]
                ts_atm = ts_data[(ts_data['strike'] >= ts_spot * 0.98) & (ts_data['strike'] <= ts_spot * 1.02)]
                if not ts_atm.empty:
                    historical_iv.append(ts_atm['iv'].mean())
        
        if historical_iv:
            features[4] = np.sum(np.array(historical_iv) < current_iv) / len(historical_iv)
        
        # ============================================================================
        # FEATURES 5-8: PCR Metrics
        # ============================================================================
        calls = current[current['option_type'] == 'CE']
        puts = current[current['option_type'] == 'PE']
        
        call_oi = calls['oi'].sum()
        put_oi = puts['oi'].sum()
        call_vol = calls['volume'].sum()
        put_vol = puts['volume'].sum()
        
        features[5] = put_oi / call_oi if call_oi > 0 else 1.0
        features[6] = put_vol / call_vol if call_vol > 0 else 1.0
        
        call_oi_change = calls['oi_change'].sum()
        put_oi_change = puts['oi_change'].sum()
        features[7] = put_oi_change / call_oi_change if call_oi_change != 0 else 1.0
        
        # PCR by value
        call_value = (calls['ltp'] * calls['oi']).sum()
        put_value = (puts['ltp'] * puts['oi']).sum()
        features[8] = put_value / call_value if call_value > 0 else 1.0
        
        # ============================================================================
        # FEATURES 9-11: Max Pain
        # ============================================================================
        strikes = current['strike'].unique()
        max_pain = self._calculate_max_pain(current, strikes)
        
        features[9] = (spot - max_pain) / spot * 100
        features[10] = max_pain / self.spot_norm_factor
        features[11] = abs(features[9]) / 100  # Pull strength
        
        # ============================================================================
        # FEATURES 12-15: Dealer GEX
        # ============================================================================
        call_gex = (calls['gamma'] * calls['oi'] * spot * spot * 0.01).sum()
        put_gex = (puts['gamma'] * puts['oi'] * spot * spot * 0.01).sum()
        
        total_gex = call_gex - put_gex  # Dealers short calls, long puts
        features[12] = total_gex / 1e9
        
        # Near expiry GEX
        if 'expiry' in current.columns and not current['expiry'].isna().all():
            near_expiry_mask = current['expiry'] <= (target_time + timedelta(days=7))
            near_expiry = current[near_expiry_mask]
            if not near_expiry.empty:
                near_call_gex = (near_expiry[near_expiry['option_type']=='CE']['gamma'] * 
                                near_expiry[near_expiry['option_type']=='CE']['oi'] * spot * spot * 0.01).sum()
                near_put_gex = (near_expiry[near_expiry['option_type']=='PE']['gamma'] * 
                               near_expiry[near_expiry['option_type']=='PE']['oi'] * spot * spot * 0.01).sum()
                features[13] = (near_call_gex - near_put_gex) / 1e9
            else:
                # Fallback: use all data
                features[13] = features[12]
        else:
            # No expiry data: use total GEX as proxy
            features[13] = features[12]
        
        features[14] = np.sign(total_gex)
        
        # GEX flip proximity (how close to zero-gamma level)
        features[15] = 1.0 / (1.0 + abs(total_gex / 1e9))
        
        # ============================================================================
        # FEATURES 16-19: Gamma Profile
        # ============================================================================
        otm_puts = current[(current['option_type'] == 'PE') & (current['strike'] < spot * 0.98)]
        otm_calls = current[(current['option_type'] == 'CE') & (current['strike'] > spot * 1.02)]
        
        put_gamma_total = (otm_puts['gamma'] * otm_puts['oi']).sum() / 1e6
        call_gamma_total = (otm_calls['gamma'] * otm_calls['oi']).sum() / 1e6
        
        features[16] = put_gamma_total + call_gamma_total
        features[17] = put_gamma_total
        features[18] = call_gamma_total
        features[19] = (put_gamma_total - call_gamma_total) / (put_gamma_total + call_gamma_total + 1e-6)
        
        # ============================================================================
        # FEATURES 20-22: IV Features
        # ============================================================================
        # IV Skew (25-delta)
        put_25d = puts[abs(puts['delta'] + 0.25) < 0.05]
        call_25d = calls[abs(calls['delta'] - 0.25) < 0.05]
        
        if not put_25d.empty and not call_25d.empty:
            features[20] = put_25d['iv'].mean() - call_25d['iv'].mean()
        
        # IV term structure (would need multiple expiries)
        features[21] = 0
        
        # IV Rank 30-day
        features[22] = features[4]  # Use percentile as proxy
        
        # ============================================================================
        # FEATURES 23-26: OI Velocity
        # ============================================================================
        if len(timestamps) >= 2:
            prev_data = df[df['timestamp'] == timestamps[-2]]
            if not prev_data.empty:
                prev_oi = prev_data['oi'].sum()
                curr_oi = current['oi'].sum()
                features[23] = (curr_oi - prev_oi) / (prev_oi + 1) * 100
        
        if len(timestamps) >= 4:
            prev_data_15 = df[df['timestamp'] == timestamps[-4]]
            if not prev_data_15.empty:
                prev_oi_15 = prev_data_15['oi'].sum()
                curr_oi = current['oi'].sum()
                features[24] = (curr_oi - prev_oi_15) / (prev_oi_15 + 1) * 100
        
        # Call/Put OI velocity
        features[25] = calls['oi_change'].sum() / (call_oi + 1) * 100
        features[26] = puts['oi_change'].sum() / (put_oi + 1) * 100
        
        # ============================================================================
        # FEATURES 27-28: Order Flow
        # ============================================================================
        # Order imbalance (bid vs ask sizes would be ideal, using volume as proxy)
        features[27] = (call_vol - put_vol) / (call_vol + put_vol + 1)
        
        # Large trade flow (using top 10% of volumes)
        all_volumes = current['volume']
        threshold = all_volumes.quantile(0.9)
        large_trades = current[current['volume'] > threshold]
        features[28] = len(large_trades) / (len(current) + 1) * 100
        
        # ============================================================================
        # FEATURES 29-31: Technical Indicators
        # ============================================================================
        # VWAP Z-score
        vwap = (current['ltp'] * current['volume']).sum() / (current['volume'].sum() + 1)
        features[29] = (spot - vwap) / spot * 100 if current['volume'].sum() > 0 else 0
        
        # RSI
        if len(timestamps) >= 14:
            recent_spots = [df[df['timestamp'] == ts]['spot'].iloc[0] for ts in timestamps[-14:]]
            returns = np.diff(recent_spots)
            gains = returns[returns > 0]
            losses = -returns[returns < 0]
            
            avg_gain = np.mean(gains) if len(gains) > 0 else 0
            avg_loss = np.mean(losses) if len(losses) > 0 else 0
            
            if avg_loss > 0:
                rs = avg_gain / avg_loss
                features[30] = 100 - (100 / (1 + rs))
            else:
                features[30] = 100 if avg_gain > 0 else 50
        else:
            features[30] = 50
        
        # ADX (simplified)
        features[31] = 25
        
        # ============================================================================
        # FEATURES 32-33: Time Features
        # ============================================================================
        # Hours to expiry (would need expiry column)
        features[32] = 48  # Placeholder
        
        # Minutes since market open
        market_open = target_time.replace(hour=9, minute=15, second=0, microsecond=0)
        features[33] = max(0, (target_time - market_open).total_seconds() / 60)
        
        return features
    
    def _calculate_max_pain(self, df: pd.DataFrame, strikes: np.ndarray) -> float:
        """Calculate max pain strike"""
        if len(strikes) == 0:
            return df['spot'].iloc[0]
        
        pain = {}
        for strike in strikes:
            call_pain = df[(df['option_type'] == 'CE') & (df['strike'] < strike)]
            put_pain = df[(df['option_type'] == 'PE') & (df['strike'] > strike)]
            
            call_loss = ((strike - call_pain['strike']) * call_pain['oi']).sum()
            put_loss = ((put_pain['strike'] - strike) * put_pain['oi']).sum()
            
            pain[strike] = call_loss + put_loss
        
        return min(pain, key=pain.get) if pain else df['spot'].iloc[0]
    
    def extract_features_batch(
        self, 
        symbol: str,
        start_time: datetime,
        end_time: datetime
    ) -> Tuple[np.ndarray, pd.DatetimeIndex]:
        """Extract features for multiple timestamps"""
        
        # Generate timestamps
        timestamps = pd.date_range(start_time, end_time, freq='5min')
        features_list = []
        
        for ts in timestamps:
            features = self.extract_features_from_db(symbol, ts)
            features_list.append(features)
        
        return np.array(features_list), timestamps


if __name__ == "__main__":
    # Test feature extraction
    engineer = QuantumEdgeFeatureEngineer()
    
    print("Testing feature extraction...")
    features = engineer.extract_features_from_db('NIFTY')
    
    print(f"\nFeature vector shape: {features.shape}")
    print(f"\nFeature values:")
    for i, (name, value) in enumerate(zip(engineer.FEATURE_NAMES, features)):
        print(f"  [{i:2d}] {name:30s}: {value:10.4f}")
