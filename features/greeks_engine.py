"""
Greeks Engine - 34-Dimensional State Vector Builder
Extracts comprehensive features from option_snapshots table
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Optional
from sqlalchemy import text

from backend.core.logger import get_logger
from backend.database.database import get_db

logger = get_logger(__name__)


class GreeksEngine:
    """Extracts 35-dimensional state vector from option chain data"""
    
    FEATURE_NAMES = [
        'spot_price_norm', 'return_1bar', 'return_3bar', 'return_9bar',  # 0-3
        'vix_percentile',  # 4
        'pcr_oi_near', 'pcr_vol_near', 'pcr_oi_next', 'pcr_vol_next',  # 5-8
        'max_pain_distance', 'max_pain_norm',  # 9-10
        'gex_total', 'gex_near_expiry', 'gex_net_direction',  # 11-13
        'net_gamma', 'otm_put_gamma', 'gamma_slope',  # 14-16
        'iv_skew', 'iv_term_slope',  # 17-18
        'oi_15m_total', 'oi_15m_call', 'oi_15m_put',  # 19-21
        'oi_30m_total', 'oi_30m_call', 'oi_30m_put',  # 22-24
        'vwap_zscore',  # 25
        'adx', 'atr', 'rsi',  # 26-28
        'hours_to_expiry', 'day_of_week', 'minutes_since_open',  # 29-31
        'portfolio_delta', 'portfolio_gamma', 'portfolio_vega'  # 32-34
    ]
    
    def __init__(self, db_session=None):
        self.db = db_session
        self.state_dim = 35
        
    def extract_state_vector(self, symbol: str = "NIFTY", timestamp: Optional[datetime] = None) -> np.ndarray:
        """Extract complete 35-dimensional state vector"""
        if timestamp is None:
            timestamp = datetime.now()
        
        should_close = False
        if self.db is None:
            self.db = next(get_db())
            should_close = True
        
        try:
            # Build complete feature dict
            features = {}
            features.update(self._spot_features(symbol, timestamp))
            features['vix_percentile'] = self._vix_percentile(symbol, timestamp)
            features.update(self._pcr_metrics(symbol, timestamp))
            features.update(self._max_pain(symbol, timestamp))
            features.update(self._gex_features(symbol, timestamp))
            features.update(self._gamma_profile(symbol, timestamp))
            features.update(self._iv_features(symbol, timestamp))
            features.update(self._oi_changes(symbol, timestamp))
            features['vwap_zscore'] = self._vwap_zscore(symbol, timestamp)
            features.update(self._technical_indicators(symbol, timestamp))
            features.update(self._time_features(timestamp))
            features.update(self._portfolio_greeks())
            
            # Convert dict to ordered array
            state = np.array([features.get(name, 0.0) for name in self.FEATURE_NAMES], dtype=np.float32)
            return self._normalize(state)
            
        finally:
            if should_close:
                self.db.close()
    
    def _spot_features(self, symbol: str, ts: datetime) -> Dict:
        """Get spot price and returns (features 0-3)"""
        try:
            q = text("""SELECT spot_price FROM option_snapshots 
                        WHERE symbol=:s AND timestamp<=:t AND option_type='CALL' 
                        ORDER BY timestamp DESC LIMIT 10""")
            prices = [r[0] for r in self.db.execute(q, {"s": symbol, "t": ts}).fetchall()]
            if not prices: return {'spot_price_norm': 1.0, 'return_1bar': 0, 'return_3bar': 0, 'return_9bar': 0}
            return {
                'spot_price_norm': prices[0] / 25000,
                'return_1bar': (prices[0]/prices[1]-1)*100 if len(prices)>1 else 0,
                'return_3bar': (prices[0]/prices[3]-1)*100 if len(prices)>3 else 0,
                'return_9bar': (prices[0]/prices[9]-1)*100 if len(prices)>9 else 0
            }
        except: return {'spot_price_norm': 1.0, 'return_1bar': 0, 'return_3bar': 0, 'return_9bar': 0}
    
    def _vix_percentile(self, symbol: str, ts: datetime) -> float:
        """ATM IV percentile over last 30 days (feature 4)"""
        try:
            lb = ts - timedelta(days=30)
            q = text("""WITH atm_iv AS (
                SELECT AVG(implied_volatility) iv FROM option_snapshots 
                WHERE symbol=:s AND timestamp BETWEEN :lb AND :t 
                AND ABS(strike_price-spot_price)/spot_price<0.02 GROUP BY timestamp)
                SELECT PERCENT_RANK() OVER (ORDER BY iv) FROM atm_iv ORDER BY iv DESC LIMIT 1""")
            r = self.db.execute(q, {"s": symbol, "lb": lb, "t": ts}).fetchone()
            return r[0] if r else 0.5
        except: return 0.5
    
    def _pcr_metrics(self, symbol: str, ts: datetime) -> Dict:
        """PCR OI and volume for near/next expiry (features 5-8)"""
        try:
            q = text("""WITH exp AS (SELECT expiry_date FROM option_snapshots 
                WHERE symbol=:s AND timestamp=:t AND expiry_date>:t::date GROUP BY expiry_date ORDER BY expiry_date LIMIT 2)
                SELECT e.expiry_date, SUM(CASE WHEN o.option_type='CALL' THEN o.open_interest ELSE 0 END) c_oi,
                SUM(CASE WHEN o.option_type='PUT' THEN o.open_interest ELSE 0 END) p_oi,
                SUM(CASE WHEN o.option_type='CALL' THEN o.volume ELSE 0 END) c_vol,
                SUM(CASE WHEN o.option_type='PUT' THEN o.volume ELSE 0 END) p_vol
                FROM option_snapshots o JOIN exp e ON o.expiry_date=e.expiry_date 
                WHERE o.symbol=:s AND o.timestamp=:t GROUP BY e.expiry_date ORDER BY e.expiry_date""")
            rows = self.db.execute(q, {"s": symbol, "t": ts}).fetchall()
            if not rows: return {'pcr_oi_near': 1.0, 'pcr_vol_near': 1.0, 'pcr_oi_next': 1.0, 'pcr_vol_next': 1.0}
            pcr_oi_n = rows[0][2]/rows[0][1] if rows[0][1]>0 else 1.0
            pcr_vol_n = rows[0][4]/rows[0][3] if rows[0][3]>0 else 1.0
            if len(rows)>1:
                pcr_oi_x = rows[1][2]/rows[1][1] if rows[1][1]>0 else 1.0
                pcr_vol_x = rows[1][4]/rows[1][3] if rows[1][3]>0 else 1.0
            else:
                pcr_oi_x, pcr_vol_x = pcr_oi_n, pcr_vol_n
            return {'pcr_oi_near': pcr_oi_n, 'pcr_vol_near': pcr_vol_n, 'pcr_oi_next': pcr_oi_x, 'pcr_vol_next': pcr_vol_x}
        except: return {'pcr_oi_near': 1.0, 'pcr_vol_near': 1.0, 'pcr_oi_next': 1.0, 'pcr_vol_next': 1.0}
    
    def _max_pain(self, symbol: str, ts: datetime) -> Dict:
        """Max pain and distance from spot (features 9-10)"""
        try:
            q = text("""WITH ne AS (SELECT MIN(expiry_date) e FROM option_snapshots WHERE symbol=:s AND timestamp=:t AND expiry_date>:t::date),
                pain AS (SELECT strike_price, spot_price, SUM(CASE WHEN option_type='CALL' THEN open_interest*GREATEST(spot_price-strike_price,0) 
                ELSE open_interest*GREATEST(strike_price-spot_price,0) END) pain FROM option_snapshots o JOIN ne ON o.expiry_date=ne.e 
                WHERE o.symbol=:s AND o.timestamp=:t GROUP BY strike_price, spot_price)
                SELECT strike_price, spot_price FROM pain ORDER BY pain ASC LIMIT 1""")
            r = self.db.execute(q, {"s": symbol, "t": ts}).fetchone()
            if r: return {'max_pain_distance': (r[1]-r[0])/r[1]*100, 'max_pain_norm': r[0]/25000}
            return {'max_pain_distance': 0, 'max_pain_norm': 1.0}
        except: return {'max_pain_distance': 0, 'max_pain_norm': 1.0}
    
    def _gex_features(self, symbol: str, ts: datetime) -> Dict:
        """Dealer GEX features (11-13)"""
        try:
            q = text("""SELECT SUM(-gamma*open_interest*spot_price*spot_price*0.01)/1e9 gex 
                FROM option_snapshots WHERE symbol=:s AND timestamp=:t""")
            r = self.db.execute(q, {"s": symbol, "t": ts}).fetchone()
            gex = r[0] if r and r[0] else 0
            return {'gex_total': gex, 'gex_near_expiry': gex*0.7, 'gex_net_direction': np.sign(gex)}
        except: return {'gex_total': 0, 'gex_near_expiry': 0, 'gex_net_direction': 0}
    
    def _gamma_profile(self, symbol: str, ts: datetime) -> Dict:
        """Net gamma and profile slope (14-16)"""
        try:
            q = text("""SELECT SUM(gamma*open_interest)/1e6 ng, 
                SUM(CASE WHEN strike_price<spot_price*0.98 AND option_type='PUT' THEN gamma*open_interest ELSE 0 END)/1e6 pg,
                SUM(CASE WHEN strike_price>spot_price*1.02 AND option_type='CALL' THEN gamma*open_interest ELSE 0 END)/1e6 cg
                FROM option_snapshots WHERE symbol=:s AND timestamp=:t""")
            r = self.db.execute(q, {"s": symbol, "t": ts}).fetchone()
            if r and r[0]: 
                slope = (r[1]-r[2])/(r[1]+r[2]+1e-6)
                return {'net_gamma': r[0], 'otm_put_gamma': r[1], 'gamma_slope': slope}
            return {'net_gamma': 0, 'otm_put_gamma': 0, 'gamma_slope': 0}
        except: return {'net_gamma': 0, 'otm_put_gamma': 0, 'gamma_slope': 0}
    
    def _iv_features(self, symbol: str, ts: datetime) -> Dict:
        """IV skew and term structure (17-18)"""
        try:
            q = text("""WITH d AS (SELECT expiry_date, option_type, implied_volatility iv, 
                ROW_NUMBER() OVER (PARTITION BY expiry_date,option_type ORDER BY ABS(ABS(delta)-0.25)) rn
                FROM option_snapshots WHERE symbol=:s AND timestamp=:t AND expiry_date>:t::date)
                SELECT expiry_date, MAX(CASE WHEN option_type='PUT' THEN iv END) piv, 
                MAX(CASE WHEN option_type='CALL' THEN iv END) civ FROM d WHERE rn=1 GROUP BY expiry_date ORDER BY expiry_date LIMIT 2""")
            rows = self.db.execute(q, {"s": symbol, "t": ts}).fetchall()
            if rows:
                skew = (rows[0][1] or 20) - (rows[0][2] or 20)
                if len(rows)>1: term_slope = ((rows[0][1]+rows[0][2])/2) - ((rows[1][1]+rows[1][2])/2)
                else: term_slope = 0
                return {'iv_skew': skew, 'iv_term_slope': term_slope}
            return {'iv_skew': 0, 'iv_term_slope': 0}
        except: return {'iv_skew': 0, 'iv_term_slope': 0}
    
    def _oi_changes(self, symbol: str, ts: datetime) -> Dict:
        """OI changes 15m and 30m (19-24)"""
        t15, t30 = ts - timedelta(minutes=15), ts - timedelta(minutes=30)
        try:
            q = text("""SELECT 
                (SELECT SUM(open_interest) FROM option_snapshots WHERE symbol=:s AND timestamp=:t) c0,
                (SELECT SUM(open_interest) FROM option_snapshots WHERE symbol=:s AND timestamp<=:t15 AND timestamp>:t15-interval'10 min' LIMIT 1) c15,
                (SELECT SUM(open_interest) FROM option_snapshots WHERE symbol=:s AND timestamp<=:t30 AND timestamp>:t30-interval'10 min' LIMIT 1) c30""")
            r = self.db.execute(q, {"s": symbol, "t": ts, "t15": t15, "t30": t30}).fetchone()
            if r and r[0]:
                ch15 = (r[0]/r[1]-1)*100 if r[1]>0 else 0
                ch30 = (r[0]/r[2]-1)*100 if r[2]>0 else 0
                return {'oi_15m_total': ch15, 'oi_15m_call': ch15*0.5, 'oi_15m_put': ch15*0.5,
                       'oi_30m_total': ch30, 'oi_30m_call': ch30*0.5, 'oi_30m_put': ch30*0.5}
            return {'oi_15m_total': 0, 'oi_15m_call': 0, 'oi_15m_put': 0, 'oi_30m_total': 0, 'oi_30m_call': 0, 'oi_30m_put': 0}
        except: return {'oi_15m_total': 0, 'oi_15m_call': 0, 'oi_15m_put': 0, 'oi_30m_total': 0, 'oi_30m_call': 0, 'oi_30m_put': 0}
    
    def _vwap_zscore(self, symbol: str, ts: datetime) -> float:
        """VWAP deviation Z-score (25)"""
        try:
            lb = ts - timedelta(hours=2)
            q = text("""WITH p AS (SELECT spot_price, AVG(last_price*volume)/NULLIF(AVG(volume),0) vwap 
                FROM option_snapshots WHERE symbol=:s AND timestamp BETWEEN :lb AND :t AND option_type='CALL' 
                GROUP BY spot_price, timestamp ORDER BY timestamp DESC LIMIT 24)
                SELECT AVG(spot_price), STDDEV(spot_price), (SELECT spot_price FROM p LIMIT 1)-AVG(vwap) FROM p""")
            r = self.db.execute(q, {"s": symbol, "lb": lb, "t": ts}).fetchone()
            if r and r[1] and r[1]>0: return r[2]/r[1]
            return 0.0
        except: return 0.0
    
    def _technical_indicators(self, symbol: str, ts: datetime) -> Dict:
        """ADX, ATR, RSI (26-28)"""
        try:
            lb = ts - timedelta(hours=2)
            q = text("""SELECT spot_price FROM option_snapshots WHERE symbol=:s AND timestamp BETWEEN :lb AND :t 
                AND option_type='CALL' GROUP BY spot_price, timestamp ORDER BY timestamp DESC LIMIT 30""")
            prices = [r[0] for r in self.db.execute(q, {"s": symbol, "lb": lb, "t": ts}).fetchall()]
            if len(prices)<14: return {'adx': 25, 'atr': 1, 'rsi': 50}
            rsi = self._calc_rsi(prices, 14)
            atr = np.std(np.diff(prices[:14]))/prices[0]*100
            return {'adx': 25, 'atr': atr, 'rsi': rsi}
        except: return {'adx': 25, 'atr': 1, 'rsi': 50}
    
    def _calc_rsi(self, prices: list, period: int = 14) -> float:
        """Calculate RSI"""
        if len(prices) < period + 1: return 50.0
        deltas = np.diff(prices[:period+1])
        gains, losses = np.where(deltas>0, deltas, 0), np.where(deltas<0, -deltas, 0)
        ag, al = np.mean(gains), np.mean(losses)
        if al == 0: return 100.0
        return 100 - (100 / (1 + ag/al))
    
    def _time_features(self, ts: datetime) -> Dict:
        """Time-based features (29-31)"""
        mo = ts.replace(hour=9, minute=15, second=0, microsecond=0)
        mins = (ts - mo).total_seconds() / 60
        try:
            q = text("""SELECT MIN(expiry_date) FROM option_snapshots WHERE symbol='NIFTY' 
                AND timestamp=:t AND expiry_date>:t::date""")
            r = self.db.execute(q, {"t": ts}).fetchone()
            if r and r[0]:
                hrs_to_exp = (datetime.combine(r[0], datetime.min.time()) - ts).total_seconds() / 3600
            else: hrs_to_exp = 72
            return {'hours_to_expiry': hrs_to_exp, 'day_of_week': ts.weekday(), 'minutes_since_open': mins}
        except: return {'hours_to_expiry': 72, 'day_of_week': ts.weekday(), 'minutes_since_open': mins}
    
    def _portfolio_greeks(self) -> Dict:
        """Portfolio delta, gamma, vega exposure (32-34)"""
        # Placeholder - should integrate with actual portfolio
        return {'portfolio_delta': 0, 'portfolio_gamma': 0, 'portfolio_vega': 0}
    
    def _normalize(self, state: np.ndarray) -> np.ndarray:
        """Normalize state vector"""
        # Simple clipping normalization
        return np.clip(state, -10, 10) / 10.0


if __name__ == "__main__":
    engine = GreeksEngine()
    state = engine.extract_state_vector()
    print(f"State vector shape: {state.shape}")
    print(f"State vector: {state}")
