"""
Technical Indicators Module

Calculates technical indicators for market analysis and ML feature extraction.
"""

from typing import List, Dict, Tuple, Optional
import numpy as np
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class TechnicalIndicators:
    """
    Calculates technical indicators from price data.
    
    Indicators supported:
    - RSI (Relative Strength Index)
    - MACD (Moving Average Convergence Divergence)
    - Bollinger Bands
    - ATR (Average True Range)
    - Multi-instrument correlations
    """
    
    def __init__(self):
        self.price_history: Dict[str, List[Tuple[datetime, float]]] = {}
        self.max_history_points = 200  # Keep last 200 data points
    
    def update_price(self, symbol: str, price: float, timestamp: datetime = None):
        """
        Update price history for a symbol.
        
        Args:
            symbol: Instrument symbol (e.g., 'NIFTY', 'BANKNIFTY')
            price: Current price
            timestamp: Timestamp (default: now)
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        if symbol not in self.price_history:
            self.price_history[symbol] = []
        
        self.price_history[symbol].append((timestamp, price))
        
        # Keep only recent history
        if len(self.price_history[symbol]) > self.max_history_points:
            self.price_history[symbol] = self.price_history[symbol][-self.max_history_points:]
    
    def get_prices(self, symbol: str) -> List[float]:
        """Get price list for a symbol"""
        if symbol not in self.price_history:
            return []
        return [price for _, price in self.price_history[symbol]]
    
    def calculate_rsi(self, symbol: str, period: int = 14) -> Optional[float]:
        """
        Calculate Relative Strength Index.
        
        RSI = 100 - (100 / (1 + RS))
        where RS = Average Gain / Average Loss
        
        Args:
            symbol: Instrument symbol
            period: RSI period (default: 14)
        
        Returns:
            RSI value (0-100) or None if insufficient data
        """
        prices = self.get_prices(symbol)
        
        if len(prices) < period + 1:
            return None
        
        # Calculate price changes
        deltas = np.diff(prices[-period-1:])
        
        # Separate gains and losses
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        # Calculate average gain and loss
        avg_gain = np.mean(gains)
        avg_loss = np.mean(losses)
        
        if avg_loss == 0:
            return 100.0  # No losses, maximum RSI
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return round(rsi, 2)
    
    def calculate_macd(
        self, 
        symbol: str, 
        fast_period: int = 12, 
        slow_period: int = 26, 
        signal_period: int = 9
    ) -> Optional[Dict[str, float]]:
        """
        Calculate MACD (Moving Average Convergence Divergence).
        
        MACD = EMA(fast) - EMA(slow)
        Signal = EMA(MACD, signal_period)
        Histogram = MACD - Signal
        
        Args:
            symbol: Instrument symbol
            fast_period: Fast EMA period (default: 12)
            slow_period: Slow EMA period (default: 26)
            signal_period: Signal line period (default: 9)
        
        Returns:
            Dict with 'macd', 'signal', 'histogram' or None
        """
        prices = self.get_prices(symbol)
        
        if len(prices) < slow_period + signal_period:
            return None
        
        prices_array = np.array(prices)
        
        # Calculate EMAs
        ema_fast = self._calculate_ema(prices_array, fast_period)
        ema_slow = self._calculate_ema(prices_array, slow_period)
        
        # MACD line
        macd_line = ema_fast - ema_slow
        
        # Signal line (EMA of MACD)
        signal_line = self._calculate_ema(macd_line, signal_period)
        
        # Histogram
        histogram = macd_line[-1] - signal_line[-1]
        
        return {
            'macd': round(macd_line[-1], 2),
            'signal': round(signal_line[-1], 2),
            'histogram': round(histogram, 2)
        }
    
    def calculate_bollinger_bands(
        self, 
        symbol: str, 
        period: int = 20, 
        std_dev: float = 2.0
    ) -> Optional[Dict[str, float]]:
        """
        Calculate Bollinger Bands.
        
        Middle Band = SMA(period)
        Upper Band = Middle + (std_dev * standard_deviation)
        Lower Band = Middle - (std_dev * standard_deviation)
        
        Args:
            symbol: Instrument symbol
            period: Moving average period (default: 20)
            std_dev: Standard deviation multiplier (default: 2.0)
        
        Returns:
            Dict with 'upper', 'middle', 'lower', 'width' or None
        """
        prices = self.get_prices(symbol)
        
        if len(prices) < period:
            return None
        
        recent_prices = prices[-period:]
        
        # Calculate middle band (SMA)
        middle = np.mean(recent_prices)
        
        # Calculate standard deviation
        std = np.std(recent_prices)
        
        # Calculate bands
        upper = middle + (std_dev * std)
        lower = middle - (std_dev * std)
        width = upper - lower
        
        # Calculate % position within bands
        current_price = prices[-1]
        pct_b = (current_price - lower) / width if width != 0 else 0.5
        
        return {
            'upper': round(upper, 2),
            'middle': round(middle, 2),
            'lower': round(lower, 2),
            'width': round(width, 2),
            'pct_b': round(pct_b, 3)  # % position in band (0-1)
        }
    
    def calculate_atr(
        self, 
        symbol: str, 
        period: int = 14,
        high_prices: List[float] = None,
        low_prices: List[float] = None
    ) -> Optional[float]:
        """
        Calculate Average True Range.
        
        ATR measures volatility.
        
        Args:
            symbol: Instrument symbol
            period: ATR period (default: 14)
            high_prices: Optional high prices list
            low_prices: Optional low prices list
        
        Returns:
            ATR value or None
        """
        prices = self.get_prices(symbol)
        
        if len(prices) < period + 1:
            return None
        
        # If high/low not provided, use close prices as approximation
        if high_prices is None or low_prices is None:
            high_prices = prices
            low_prices = prices
        
        # Calculate true ranges
        true_ranges = []
        for i in range(1, len(prices)):
            high_low = high_prices[i] - low_prices[i]
            high_close = abs(high_prices[i] - prices[i-1])
            low_close = abs(low_prices[i] - prices[i-1])
            true_range = max(high_low, high_close, low_close)
            true_ranges.append(true_range)
        
        # Calculate ATR (simple average of true ranges)
        if len(true_ranges) < period:
            return None
        
        atr = np.mean(true_ranges[-period:])
        return round(atr, 2)
    
    def calculate_correlation(
        self, 
        symbol1: str, 
        symbol2: str, 
        window: int = 20
    ) -> Optional[float]:
        """
        Calculate correlation between two instruments.
        
        Args:
            symbol1: First instrument symbol
            symbol2: Second instrument symbol
            window: Rolling window for correlation (default: 20)
        
        Returns:
            Correlation coefficient (-1 to 1) or None
        """
        prices1 = self.get_prices(symbol1)
        prices2 = self.get_prices(symbol2)
        
        if len(prices1) < window or len(prices2) < window:
            return None
        
        # Get aligned recent prices
        recent1 = np.array(prices1[-window:])
        recent2 = np.array(prices2[-window:])
        
        # Calculate correlation
        correlation = np.corrcoef(recent1, recent2)[0, 1]
        
        return round(correlation, 3)
    
    def calculate_returns(self, symbol: str, period: int = 1) -> Optional[float]:
        """
        Calculate percentage returns over period.
        
        Args:
            symbol: Instrument symbol
            period: Lookback period (default: 1)
        
        Returns:
            Percentage return or None
        """
        prices = self.get_prices(symbol)
        
        if len(prices) < period + 1:
            return None
        
        old_price = prices[-(period + 1)]
        current_price = prices[-1]
        
        if old_price == 0:
            return None
        
        returns = ((current_price - old_price) / old_price) * 100
        return round(returns, 2)
    
    def calculate_volatility(self, symbol: str, window: int = 20) -> Optional[float]:
        """
        Calculate rolling volatility (standard deviation of returns).
        
        Args:
            symbol: Instrument symbol
            window: Rolling window (default: 20)
        
        Returns:
            Volatility percentage or None
        """
        prices = self.get_prices(symbol)
        
        if len(prices) < window + 1:
            return None
        
        recent_prices = prices[-window-1:]
        returns = np.diff(recent_prices) / recent_prices[:-1]
        volatility = np.std(returns) * 100
        
        return round(volatility, 2)
    
    def get_all_indicators(self, symbol: str) -> Dict[str, any]:
        """
        Calculate all indicators for a symbol.
        
        Args:
            symbol: Instrument symbol
        
        Returns:
            Dictionary with all available indicators
        """
        indicators = {
            'rsi': self.calculate_rsi(symbol),
            'macd': self.calculate_macd(symbol),
            'bollinger': self.calculate_bollinger_bands(symbol),
            'atr': self.calculate_atr(symbol),
            'returns_1d': self.calculate_returns(symbol, 1),
            'returns_5d': self.calculate_returns(symbol, 5),
            'volatility': self.calculate_volatility(symbol),
            'data_points': len(self.get_prices(symbol))
        }
        
        return indicators

    def get_timeframe_snapshot(self, symbol: str, windows: Dict[str, int]) -> Dict[str, Optional[float]]:
        """Return percentage returns for requested lookback windows (by data points)."""
        prices = self.get_prices(symbol)
        snapshot: Dict[str, Optional[float]] = {}

        if not prices:
            for label in windows.keys():
                snapshot[f'return_{label}'] = None
            return snapshot

        latest_price = prices[-1]
        for label, window in windows.items():
            if window <= 0 or len(prices) <= window:
                snapshot[f'return_{label}'] = None
                continue

            past_price = prices[-(window + 1)]
            if past_price is None or past_price == 0:
                snapshot[f'return_{label}'] = None
                continue

            change_pct = ((latest_price - past_price) / past_price) * 100
            snapshot[f'return_{label}'] = round(change_pct, 2)

        return snapshot
    
    def _calculate_ema(self, prices: np.ndarray, period: int) -> np.ndarray:
        """
        Calculate Exponential Moving Average.
        
        Args:
            prices: Price array
            period: EMA period
        
        Returns:
            EMA array
        """
        ema = np.zeros_like(prices)
        ema[0] = prices[0]
        
        multiplier = 2 / (period + 1)
        
        for i in range(1, len(prices)):
            ema[i] = (prices[i] * multiplier) + (ema[i-1] * (1 - multiplier))
        
        return ema
    
    def get_feature_vector(self, primary_symbol: str, secondary_symbols: List[str] = None) -> Dict:
        """
        Get comprehensive feature vector for ML model.
        
        Args:
            primary_symbol: Primary instrument (e.g., 'NIFTY')
            secondary_symbols: Other instruments for correlation (e.g., ['BANKNIFTY'])
        
        Returns:
            Dictionary with all features
        """
        features = {}
        
        # Primary symbol indicators
        primary_indicators = self.get_all_indicators(primary_symbol)
        features.update({f'{primary_symbol}_{k}': v for k, v in primary_indicators.items()})
        
        # Correlations with secondary symbols
        if secondary_symbols:
            for secondary in secondary_symbols:
                corr = self.calculate_correlation(primary_symbol, secondary)
                features[f'corr_{primary_symbol}_{secondary}'] = corr
        
        # Time-based features
        now = datetime.now()
        features['hour_of_day'] = now.hour
        features['day_of_week'] = now.weekday()
        features['is_market_hours'] = 1 if 9 <= now.hour <= 15 else 0
        features['time_to_close'] = max(0, 15.5 - (now.hour + now.minute/60))
        
        return features
    
    def clear_history(self, symbol: str = None):
        """Clear price history for a symbol or all symbols"""
        if symbol:
            if symbol in self.price_history:
                del self.price_history[symbol]
        else:
            self.price_history.clear()
