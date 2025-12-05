"""
Reversal Detector
Detects potential market reversals using various technical indicators
"""

from typing import Dict, Optional, Tuple, List
import numpy as np
from datetime import datetime, timedelta

class ReversalSignal:
    """Reversal signal object"""
    def __init__(self, signal_type: str, severity: str, description: str):
        self.signal_type = signal_type
        self.severity = severity
        self.description = description

class ReversalDetector:
    """
    Detects potential market reversals using technical analysis
    """
    
    def __init__(self):
        self.min_periods = 10  # Minimum periods for calculations
        
    def update(self, market_state: Dict) -> List[ReversalSignal]:
        """
        Update reversal detector with new market state
        
        Args:
            market_state: Current market state with price/volume data
            
        Returns:
            List of reversal signals
        """
        signals = []
        
        try:
            for symbol in ['NIFTY', 'SENSEX']:
                symbol_data = market_state.get(symbol, {})
                if not symbol_data:
                    continue
                    
                spot_price = symbol_data.get('spot_price', 0)
                if spot_price == 0:
                    continue
                
                # Get recent price data from market state
                price_history = symbol_data.get('price_history', [])
                volume_history = symbol_data.get('volume_history', [])
                
                if len(price_history) < self.min_periods:
                    continue
                
                # Detect reversals
                reversal_result = self.detect_reversal(price_history, volume_history)
                
                if reversal_result.get('reversal_signal'):
                    severity = 'high' if reversal_result.get('confidence', 0) > 0.7 else 'medium'
                    signal = ReversalSignal(
                        signal_type=reversal_result.get('signal_type', 'unknown'),
                        severity=severity,
                        description=reversal_result.get('reason', 'Reversal detected')
                    )
                    signals.append(signal)
                    
        except Exception as e:
            # Return empty list on error to avoid breaking the monitoring loop
            pass
            
        return signals
        
    def detect_reversal(self, prices: list, volumes: list = None, rsi_values: list = None) -> Dict:
        """
        Detect potential reversal signals
        
        Args:
            prices: List of price data (closing prices)
            volumes: List of volume data (optional)
            rsi_values: List of RSI values (optional)
            
        Returns:
            Dictionary with reversal signals
        """
        if len(prices) < self.min_periods:
            return {
                'reversal_signal': False,
                'signal_type': None,
                'confidence': 0.0,
                'reason': 'Insufficient data'
            }
        
        signals = []
        
        # Check for RSI divergence
        if rsi_values and len(rsi_values) >= self.min_periods:
            rsi_signal = self._check_rsi_divergence(prices, rsi_values)
            if rsi_signal['signal']:
                signals.append(rsi_signal)
        
        # Check for volume-based reversal
        if volumes and len(volumes) >= self.min_periods:
            volume_signal = self._check_volume_reversal(prices, volumes)
            if volume_signal['signal']:
                signals.append(volume_signal)
        
        # Check for price pattern reversal
        price_signal = self._check_price_reversal(prices)
        if price_signal['signal']:
            signals.append(price_signal)
        
        # Aggregate signals
        if signals:
            # Calculate overall confidence
            total_confidence = sum(s['confidence'] for s in signals)
            avg_confidence = total_confidence / len(signals)
            
            # Determine signal type (bearish or bullish)
            bullish_signals = [s for s in signals if s['type'] == 'bullish']
            bearish_signals = [s for s in signals if s['type'] == 'bearish']
            
            signal_type = None
            if len(bullish_signals) > len(bearish_signals):
                signal_type = 'bullish'
            elif len(bearish_signals) > len(bullish_signals):
                signal_type = 'bearish'
            
            return {
                'reversal_signal': True,
                'signal_type': signal_type,
                'confidence': avg_confidence,
                'signals': signals,
                'reason': f"Detected {len(signals)} reversal signals"
            }
        
        return {
            'reversal_signal': False,
            'signal_type': None,
            'confidence': 0.0,
            'reason': 'No reversal signals detected'
        }
    
    def _check_rsi_divergence(self, prices: list, rsi_values: list) -> Dict:
        """
        Check for RSI divergence (price makes new high/low but RSI doesn't)
        
        Args:
            prices: List of prices
            rsi_values: List of RSI values
            
        Returns:
            Signal dictionary
        """
        if len(prices) < 5 or len(rsi_values) < 5:
            return {'signal': False, 'type': None, 'confidence': 0.0}
        
        # Get recent data
        recent_prices = prices[-5:]
        recent_rsi = rsi_values[-5:]
        
        # Check for bullish divergence (price lower, RSI higher)
        if (recent_prices[-1] < min(recent_prices[:-1]) and 
            recent_rsi[-1] > min(recent_rsi[:-1]) and
            recent_rsi[-1] < 30):  # Oversold condition
            return {
                'signal': True,
                'type': 'bullish',
                'confidence': 0.7,
                'reason': 'Bullish RSI divergence in oversold territory'
            }
        
        # Check for bearish divergence (price higher, RSI lower)
        if (recent_prices[-1] > max(recent_prices[:-1]) and 
            recent_rsi[-1] < max(recent_rsi[:-1]) and
            recent_rsi[-1] > 70):  # Overbought condition
            return {
                'signal': True,
                'type': 'bearish',
                'confidence': 0.7,
                'reason': 'Bearish RSI divergence in overbought territory'
            }
        
        return {'signal': False, 'type': None, 'confidence': 0.0}
    
    def _check_volume_reversal(self, prices: list, volumes: list) -> Dict:
        """
        Check for volume-based reversal signals
        
        Args:
            prices: List of prices
            volumes: List of volumes
            
        Returns:
            Signal dictionary
        """
        if len(prices) < 3 or len(volumes) < 3:
            return {'signal': False, 'type': None, 'confidence': 0.0}
        
        # Calculate average volume
        avg_volume = np.mean(volumes[:-1])
        recent_volume = volumes[-1]
        
        # Check for exhaustion move (high volume reversal)
        volume_ratio = recent_volume / avg_volume if avg_volume > 0 else 1
        
        # Price change
        price_change = (prices[-1] - prices[-2]) / prices[-2]
        
        # Bullish reversal: price down with high volume
        if price_change < -0.02 and volume_ratio > 2.0:
            return {
                'signal': True,
                'type': 'bullish',
                'confidence': min(0.8, volume_ratio / 3),
                'reason': f'High volume ({volume_ratio:.1f}x avg) on price decline'
            }
        
        # Bearish reversal: price up with high volume
        if price_change > 0.02 and volume_ratio > 2.0:
            return {
                'signal': True,
                'type': 'bearish',
                'confidence': min(0.8, volume_ratio / 3),
                'reason': f'High volume ({volume_ratio:.1f}x avg) on price rise'
            }
        
        return {'signal': False, 'type': None, 'confidence': 0.0}
    
    def _check_price_reversal(self, prices: list) -> Dict:
        """
        Check for price pattern reversal signals
        
        Args:
            prices: List of prices
            
        Returns:
            Signal dictionary
        """
        if len(prices) < 5:
            return {'signal': False, 'type': None, 'confidence': 0.0}
        
        # Simple momentum reversal check
        recent_prices = prices[-5:]
        
        # Calculate short-term trend
        if len(recent_prices) >= 3:
            short_trend = (recent_prices[-1] - recent_prices[-3]) / recent_prices[-3]
            
            # Check for sudden reversal in direction
            if len(recent_prices) >= 4:
                prev_trend = (recent_prices[-2] - recent_prices[-4]) / recent_prices[-4]
                
                # Bullish reversal: was down, now up
                if prev_trend < -0.01 and short_trend > 0.01:
                    return {
                        'signal': True,
                        'type': 'bullish',
                        'confidence': 0.5,
                        'reason': 'Short-term bullish reversal'
                    }
                
                # Bearish reversal: was up, now down
                if prev_trend > 0.01 and short_trend < -0.01:
                    return {
                        'signal': True,
                        'type': 'bearish',
                        'confidence': 0.5,
                        'reason': 'Short-term bearish reversal'
                    }
        
        return {'signal': False, 'type': None, 'confidence': 0.0}
    
    def get_support_resistance_levels(self, prices: list, window: int = 20) -> Tuple[float, float]:
        """
        Calculate basic support and resistance levels
        
        Args:
            prices: List of prices
            window: Lookback window
            
        Returns:
            Tuple of (support_level, resistance_level)
        """
        if len(prices) < window:
            return 0.0, 0.0
        
        recent_prices = prices[-window:]
        
        support_level = min(recent_prices)
        resistance_level = max(recent_prices)
        
        return support_level, resistance_level
    
    def is_near_support_resistance(self, current_price: float, prices: list, window: int = 20, threshold: float = 0.02) -> Dict:
        """
        Check if price is near support or resistance levels
        
        Args:
            current_price: Current price
            prices: List of historical prices
            window: Lookback window
            threshold: Distance threshold (percentage)
            
        Returns:
            Dictionary with support/resistance information
        """
        support, resistance = self.get_support_resistance_levels(prices, window)
        
        if support == 0.0 or resistance == 0.0:
            return {'near_support': False, 'near_resistance': False}
        
        # Calculate distances
        support_distance = (current_price - support) / support
        resistance_distance = (resistance - current_price) / resistance
        
        near_support = abs(support_distance) <= threshold
        near_resistance = abs(resistance_distance) <= threshold
        
        return {
            'near_support': near_support,
            'near_resistance': near_resistance,
            'support_level': support,
            'resistance_level': resistance,
            'support_distance_pct': support_distance * 100,
            'resistance_distance_pct': resistance_distance * 100
        }
