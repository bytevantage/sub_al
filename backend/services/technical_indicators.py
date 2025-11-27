"""
Technical Indicators Calculator
Provides multi-timeframe technical analysis for trading strategies
"""

import numpy as np
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import asyncio


class TechnicalIndicators:
    """Calculate technical indicators across multiple timeframes"""
    
    def __init__(self, upstox_client):
        self.upstox_client = upstox_client
        self.indicator_cache = {}
        self.cache_duration = 300  # 5 minutes
        
    async def get_multi_timeframe_analysis(
        self, 
        instrument_key: str, 
        timeframes: List[str] = None
    ) -> Dict:
        """
        Get technical indicators across multiple timeframes
        
        Args:
            instrument_key: Upstox instrument key
            timeframes: List of timeframes (default: ['5minute', '15minute', '1hour'])
            
        Returns:
            Dict with indicators for each timeframe
        """
        if timeframes is None:
            timeframes = ['5minute', '15minute', '1hour']
            
        cache_key = f"{instrument_key}_{'-'.join(timeframes)}"
        
        # Check cache
        if cache_key in self.indicator_cache:
            cached = self.indicator_cache[cache_key]
            age = (datetime.now() - cached['timestamp']).total_seconds()
            if age < self.cache_duration:
                return cached['data']
        
        # Fetch historical data for each timeframe
        results = {}
        
        for timeframe in timeframes:
            try:
                indicators = await self._calculate_indicators_for_timeframe(
                    instrument_key, timeframe
                )
                results[timeframe] = indicators
            except Exception as e:
                print(f"Error calculating indicators for {timeframe}: {e}")
                results[timeframe] = None
        
        # Cache results
        self.indicator_cache[cache_key] = {
            'data': results,
            'timestamp': datetime.now()
        }
        
        return results
    
    async def _calculate_indicators_for_timeframe(
        self, 
        instrument_key: str, 
        timeframe: str
    ) -> Dict:
        """Calculate indicators for a specific timeframe"""
        
        # Get historical data from Upstox
        end_date = datetime.now()
        
        # Determine lookback based on timeframe
        lookback_days = {
            '1minute': 1,
            '5minute': 2,
            '15minute': 5,
            '30minute': 10,
            '1hour': 20,
            '1day': 100
        }.get(timeframe, 5)
        
        start_date = end_date - timedelta(days=lookback_days)
        
        # Fetch historical data
        try:
            historical_data = await asyncio.to_thread(
                self.upstox_client.get_historical_candle_data,
                instrument_key,
                timeframe,
                start_date.strftime('%Y-%m-%d'),
                end_date.strftime('%Y-%m-%d')
            )
            
            if not historical_data or 'data' not in historical_data:
                return {}
                
            candles = historical_data['data'].get('candles', [])
            
            if not candles or len(candles) < 20:  # Need at least 20 candles
                return {}
            
            # Extract OHLC data
            closes = np.array([float(c[4]) for c in candles])  # close is index 4
            highs = np.array([float(c[2]) for c in candles])   # high is index 2
            lows = np.array([float(c[3]) for c in candles])    # low is index 3
            
            # Calculate indicators
            vix_value = self._calculate_vix(closes)
            adx_value = self._calculate_adx(highs, lows, closes)
            
            print(f"Debug: Calculated VIX={vix_value}, ADX={adx_value} for {timeframe} (candles: {len(candles)})")
            
            indicators = {
                'rsi': self._calculate_rsi(closes),
                'macd': self._calculate_macd(closes),
                'sma_20': self._calculate_sma(closes, 20),
                'sma_50': self._calculate_sma(closes, 50) if len(closes) >= 50 else None,
                'ema_9': self._calculate_ema(closes, 9),
                'ema_21': self._calculate_ema(closes, 21),
                'bollinger_bands': self._calculate_bollinger_bands(closes),
                'atr': self._calculate_atr(highs, lows, closes),
                'current_price': float(closes[-1]),
                'trend': self._determine_trend(closes),
                'vix': vix_value,  # India VIX proxy
                'adx': adx_value  # ADX trend strength
            }
            
            return indicators
            
        except Exception as e:
            print(f"Error fetching historical data for {instrument_key} {timeframe}: {e}")
            return {}
    
    def _calculate_rsi(self, prices: np.ndarray, period: int = 14) -> Optional[float]:
        """Calculate Relative Strength Index"""
        if len(prices) < period + 1:
            return None
            
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains[:period])
        avg_loss = np.mean(losses[:period])
        
        for i in range(period, len(deltas)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        
        if avg_loss == 0:
            return 100.0
            
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return float(rsi)
    
    def _calculate_macd(self, prices: np.ndarray) -> Optional[Dict]:
        """Calculate MACD indicator"""
        if len(prices) < 26:
            return None
            
        ema_12 = self._calculate_ema(prices, 12)
        ema_26 = self._calculate_ema(prices, 26)
        
        if ema_12 is None or ema_26 is None:
            return None
            
        macd_line = ema_12 - ema_26
        
        # Calculate signal line (9-day EMA of MACD)
        # For simplicity, we'll use a simple moving average
        signal_line = macd_line  # Simplified
        
        histogram = macd_line - signal_line
        
        return {
            'macd': float(macd_line),
            'signal': float(signal_line),
            'histogram': float(histogram)
        }
    
    def _calculate_sma(self, prices: np.ndarray, period: int) -> Optional[float]:
        """Calculate Simple Moving Average"""
        if len(prices) < period:
            return None
        return float(np.mean(prices[-period:]))
    
    def _calculate_ema(self, prices: np.ndarray, period: int) -> Optional[float]:
        """Calculate Exponential Moving Average"""
        if len(prices) < period:
            return None
            
        multiplier = 2 / (period + 1)
        ema = prices[0]
        
        for price in prices[1:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))
            
        return float(ema)
    
    def _calculate_bollinger_bands(self, prices: np.ndarray, period: int = 20) -> Optional[Dict]:
        """Calculate Bollinger Bands"""
        if len(prices) < period:
            return None
            
        sma = np.mean(prices[-period:])
        std = np.std(prices[-period:])
        
        return {
            'upper': float(sma + (2 * std)),
            'middle': float(sma),
            'lower': float(sma - (2 * std))
        }
    
    def _calculate_atr(
        self, 
        highs: np.ndarray, 
        lows: np.ndarray, 
        closes: np.ndarray, 
        period: int = 14
    ) -> Optional[float]:
        """Calculate Average True Range"""
        if len(highs) < period + 1:
            return None
            
        tr_list = []
        for i in range(1, len(highs)):
            high_low = highs[i] - lows[i]
            high_close = abs(highs[i] - closes[i-1])
            low_close = abs(lows[i] - closes[i-1])
            tr = max(high_low, high_close, low_close)
            tr_list.append(tr)
        
        atr = np.mean(tr_list[-period:])
        return float(atr)
    
    def _calculate_vix(self, prices: np.ndarray, period: int = 20) -> Optional[float]:
        """
        Calculate VIX proxy from historical price volatility
        This is a simplified version of India VIX calculation
        """
        if len(prices) < period:
            return None
            
        # Calculate daily returns
        returns = np.diff(prices) / prices[:-1]
        
        # Calculate standard deviation of returns (volatility)
        volatility = np.std(returns[-period:])
        
        # Convert to annualized volatility (VIX-style)
        # Multiply by sqrt(252) for annualization, then by 100 for percentage
        vix_proxy = volatility * np.sqrt(252) * 100
        
        return float(vix_proxy)
    
    def _calculate_adx(self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> Optional[float]:
        """
        Calculate Average Directional Index (ADX) for trend strength
        ADX > 25 = Strong trend, ADX < 20 = Weak/No trend
        """
        if len(highs) < period + 1:
            return None
            
        # Calculate True Range
        tr_list = []
        for i in range(1, len(highs)):
            high_low = highs[i] - lows[i]
            high_close = abs(highs[i] - closes[i-1])
            low_close = abs(lows[i] - closes[i-1])
            tr = max(high_low, high_close, low_close)
            tr_list.append(tr)
        
        # Calculate +DM and -DM
        plus_dm = []
        minus_dm = []
        
        for i in range(1, len(highs)):
            up_move = highs[i] - highs[i-1]
            down_move = lows[i-1] - lows[i]
            
            if up_move > down_move and up_move > 0:
                plus_dm.append(up_move)
            else:
                plus_dm.append(0)
                
            if down_move > up_move and down_move > 0:
                minus_dm.append(down_move)
            else:
                minus_dm.append(0)
        
        # Calculate smoothed averages
        atr_smoothed = []
        plus_di_smoothed = []
        minus_di_smoothed = []
        
        # Initial smoothing
        atr_smoothed.append(np.mean(tr_list[:period]))
        plus_di_smoothed.append(np.mean(plus_dm[:period]))
        minus_di_smoothed.append(np.mean(minus_dm[:period]))
        
        # Subsequent smoothing
        for i in range(period, len(tr_list)):
            atr_smoothed.append((atr_smoothed[-1] * (period - 1) + tr_list[i]) / period)
            plus_di_smoothed.append((plus_di_smoothed[-1] * (period - 1) + plus_dm[i]) / period)
            minus_di_smoothed.append((minus_di_smoothed[-1] * (period - 1) + minus_dm[i]) / period)
        
        # Calculate +DI and -DI
        plus_di = []
        minus_di = []
        
        for i in range(len(atr_smoothed)):
            if atr_smoothed[i] > 0:
                plus_di.append((plus_di_smoothed[i] / atr_smoothed[i]) * 100)
                minus_di.append((minus_di_smoothed[i] / atr_smoothed[i]) * 100)
            else:
                plus_di.append(0)
                minus_di.append(0)
        
        # Calculate DX and ADX
        dx_list = []
        for i in range(len(plus_di)):
            di_diff = abs(plus_di[i] - minus_di[i])
            di_sum = plus_di[i] + minus_di[i]
            if di_sum > 0:
                dx = (di_diff / di_sum) * 100
                dx_list.append(dx)
            else:
                dx_list.append(0)
        
        # Calculate ADX (smoothed DX)
        if len(dx_list) >= period:
            adx = np.mean(dx_list[-period:])
        else:
            adx = np.mean(dx_list) if dx_list else 0
        
        return float(adx)
    
    def _determine_trend(self, prices: np.ndarray) -> str:
        """Determine overall trend direction"""
        if len(prices) < 20:
            return "neutral"
            
        # Simple trend determination using recent price action
        recent_prices = prices[-20:]
        first_half = np.mean(recent_prices[:10])
        second_half = np.mean(recent_prices[10:])
        
        diff_pct = ((second_half - first_half) / first_half) * 100
        
        if diff_pct > 1.0:
            return "bullish"
        elif diff_pct < -1.0:
            return "bearish"
        else:
            return "neutral"
