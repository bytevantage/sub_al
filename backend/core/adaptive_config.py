"""
Adaptive Configuration System
Dynamically adjusts trading parameters based on market conditions and performance
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
import statistics
import logging

logger = logging.getLogger(__name__)


@dataclass
class MarketRegime:
    """Market regime classification"""
    volatility_regime: str  # 'low', 'normal', 'high', 'extreme'
    trend_regime: str  # 'bullish', 'bearish', 'sideways'
    volume_regime: str  # 'low', 'normal', 'high'
    confidence: float  # 0-1 confidence in classification
    last_updated: datetime


@dataclass
class AdaptiveThresholds:
    """Dynamically adjusted thresholds"""
    min_signal_strength: float
    max_positions: int
    per_trade_risk_percent: float
    strategy_watchdog_win_rate: float
    strategy_watchdog_consecutive_losses: int
    last_adjusted: datetime


class AdaptiveConfigurationManager:
    """
    Manages adaptive configuration adjustments based on:
    1. Market volatility and regime
    2. Recent trading performance
    3. System health metrics
    4. Time-based adjustments
    """

    def __init__(self):
        self.market_regime = MarketRegime('normal', 'sideways', 'normal', 0.5, datetime.min)
        self.adaptive_thresholds = AdaptiveThresholds(
            min_signal_strength=75.0,
            max_positions=5,
            per_trade_risk_percent=1.0,
            strategy_watchdog_win_rate=45.0,
            strategy_watchdog_consecutive_losses=5,
            last_adjusted=datetime.now()
        )

        # Historical data for analysis
        self.recent_signals = []
        self.recent_trades = []
        self.market_volatility_history = []
        self.performance_history = []

        # Adjustment parameters
        self.adjustment_interval = timedelta(minutes=15)
        self.min_history_points = 20
        self.max_history_points = 100

    def update_market_regime(self, market_data: Dict) -> MarketRegime:
        """
        Classify current market regime based on volatility, trend, and volume
        """
        try:
            # Extract key metrics
            vix = market_data.get('volatility', {}).get('india_vix', 20.0)
            spot_price = market_data.get('spot_price', 0)
            pcr = market_data.get('pcr', 1.0)
            volume = market_data.get('volume', 0)

            # Volatility regime
            if vix < 15:
                vol_regime = 'low'
                vol_confidence = 0.8
            elif vix < 25:
                vol_regime = 'normal'
                vol_confidence = 0.9
            elif vix < 35:
                vol_regime = 'high'
                vol_confidence = 0.8
            else:
                vol_regime = 'extreme'
                vol_confidence = 0.9

            # Trend regime based on recent price action and PCR
            if pcr > 1.3:
                trend_regime = 'bearish'  # High PCR suggests bearish sentiment
            elif pcr < 0.8:
                trend_regime = 'bullish'  # Low PCR suggests bullish sentiment
            else:
                trend_regime = 'sideways'

            trend_confidence = min(abs(pcr - 1.0) * 2, 0.8)  # Higher confidence with extreme PCR

            # Volume regime (simplified - would need volume history)
            vol_regime_market = 'normal'  # Placeholder
            volume_confidence = 0.6

            # Overall confidence
            total_confidence = (vol_confidence + trend_confidence + volume_confidence) / 3

            self.market_regime = MarketRegime(
                volatility_regime=vol_regime,
                trend_regime=trend_regime,
                volume_regime=vol_regime_market,
                confidence=total_confidence,
                last_updated=datetime.now()
            )

            logger.info(
                f"Market regime updated: Vol={vol_regime}({vix:.1f}), "
                f"Trend={trend_regime}(PCR={pcr:.2f}), Confidence={total_confidence:.2f}"
            )

            return self.market_regime

        except Exception as e:
            logger.error(f"Error updating market regime: {e}")
            return self.market_regime

    def update_performance_data(self, trade_result: Optional[Dict] = None, signal_data: Optional[Dict] = None):
        """
        Update performance tracking data
        """
        if trade_result:
            self.recent_trades.append({
                'timestamp': datetime.now(),
                'pnl': trade_result.get('pnl', 0),
                'strategy': trade_result.get('strategy', 'unknown'),
                'is_winning': trade_result.get('pnl', 0) > 0
            })

            # Keep only recent data
            cutoff = datetime.now() - timedelta(hours=24)
            self.recent_trades = [
                t for t in self.recent_trades
                if t['timestamp'] > cutoff
            ][:self.max_history_points]

        if signal_data:
            self.recent_signals.append({
                'timestamp': datetime.now(),
                'strength': signal_data.get('strength', 0),
                'strategy': signal_data.get('strategy', 'unknown'),
                'accepted': signal_data.get('accepted', False)
            })

            # Keep only recent data
            cutoff = datetime.now() - timedelta(hours=4)
            self.recent_signals = [
                s for s in self.recent_signals
                if s['timestamp'] > cutoff
            ][:self.max_history_points]

    def should_adjust_thresholds(self) -> bool:
        """
        Check if thresholds should be adjusted based on time and data availability
        """
        time_since_adjustment = datetime.now() - self.adaptive_thresholds.last_adjusted

        return (
            time_since_adjustment >= self.adjustment_interval and
            len(self.recent_trades) >= self.min_history_points and
            len(self.recent_signals) >= self.min_history_points
        )

    def adjust_thresholds(self) -> AdaptiveThresholds:
        """
        Dynamically adjust trading thresholds based on current conditions
        """
        try:
            # Calculate recent performance metrics
            recent_win_rate = self._calculate_recent_win_rate()
            recent_signal_acceptance = self._calculate_signal_acceptance_rate()
            recent_volatility = self._calculate_recent_volatility()

            # Base thresholds from market regime
            base_thresholds = self._get_regime_base_thresholds()

            # Adjust based on performance
            performance_multipliers = self._calculate_performance_multipliers(
                recent_win_rate, recent_signal_acceptance
            )

            # Apply adjustments
            adjusted_min_strength = min(
                base_thresholds['min_signal_strength'] * performance_multipliers['signal_strength'],
                85  # Cap at 85 to prevent being too loose
            )

            adjusted_max_positions = max(
                int(base_thresholds['max_positions'] * performance_multipliers['positions']),
                3  # Minimum 3 positions
            )

            adjusted_risk_percent = min(
                base_thresholds['per_trade_risk_percent'] * performance_multipliers['risk'],
                2.5  # Cap at 2.5%
            )

            # Adjust strategy watchdog thresholds
            adjusted_watchdog_win_rate = max(
                base_thresholds['strategy_watchdog_win_rate'] * performance_multipliers['watchdog_win_rate'],
                30  # Minimum 30%
            )

            adjusted_consecutive_losses = max(
                int(base_thresholds['strategy_watchdog_consecutive_losses'] * performance_multipliers['watchdog_losses']),
                3  # Minimum 3 losses
            )

            # Update thresholds
            self.adaptive_thresholds = AdaptiveThresholds(
                min_signal_strength=round(adjusted_min_strength, 1),
                max_positions=adjusted_max_positions,
                per_trade_risk_percent=round(adjusted_risk_percent, 2),
                strategy_watchdog_win_rate=round(adjusted_watchdog_win_rate, 1),
                strategy_watchdog_consecutive_losses=adjusted_consecutive_losses,
                last_adjusted=datetime.now()
            )

            logger.info(
                f"Thresholds adjusted: Signal Strength {adjusted_min_strength:.1f}, "
                f"Max Positions {adjusted_max_positions}, Risk {adjusted_risk_percent:.2f}%, "
                f"Watchdog Win Rate {adjusted_watchdog_win_rate:.1f}%, "
                f"Consecutive Losses {adjusted_consecutive_losses}"
            )

            return self.adaptive_thresholds

        except Exception as e:
            logger.error(f"Error adjusting thresholds: {e}")
            return self.adaptive_thresholds

    def _calculate_recent_win_rate(self) -> float:
        """Calculate win rate from recent trades"""
        if not self.recent_trades:
            return 0.5  # Neutral assumption

        recent_wins = sum(1 for t in self.recent_trades if t['is_winning'])
        return recent_wins / len(self.recent_trades)

    def _calculate_signal_acceptance_rate(self) -> float:
        """Calculate what percentage of signals are being accepted"""
        if not self.recent_signals:
            return 0.5

        accepted = sum(1 for s in self.recent_signals if s['accepted'])
        return accepted / len(self.recent_signals)

    def _calculate_recent_volatility(self) -> float:
        """Calculate recent market volatility"""
        if not self.market_volatility_history:
            return 20.0  # Default VIX

        return statistics.mean(self.market_volatility_history[-10:])  # Last 10 points

    def _get_regime_base_thresholds(self) -> Dict[str, float]:
        """Get base thresholds for current market regime"""
        regime = self.market_regime

        # Base thresholds by volatility regime
        if regime.volatility_regime == 'low':
            base = {
                'min_signal_strength': 70.0,
                'max_positions': 8,
                'per_trade_risk_percent': 1.5,
                'strategy_watchdog_win_rate': 40.0,
                'strategy_watchdog_consecutive_losses': 6
            }
        elif regime.volatility_regime == 'normal':
            base = {
                'min_signal_strength': 75.0,
                'max_positions': 5,
                'per_trade_risk_percent': 1.0,
                'strategy_watchdog_win_rate': 45.0,
                'strategy_watchdog_consecutive_losses': 5
            }
        elif regime.volatility_regime == 'high':
            base = {
                'min_signal_strength': 80.0,
                'max_positions': 3,
                'per_trade_risk_percent': 0.7,
                'strategy_watchdog_win_rate': 50.0,
                'strategy_watchdog_consecutive_losses': 4
            }
        else:  # extreme
            base = {
                'min_signal_strength': 85.0,
                'max_positions': 2,
                'per_trade_risk_percent': 0.5,
                'strategy_watchdog_win_rate': 55.0,
                'strategy_watchdog_consecutive_losses': 3
            }

        # Adjust for trend regime
        if regime.trend_regime == 'bullish':
            base['min_signal_strength'] -= 5  # Easier in trending markets
        elif regime.trend_regime == 'bearish':
            base['min_signal_strength'] -= 5  # Easier in trending markets

        return base

    def _calculate_performance_multipliers(self, win_rate: float, signal_acceptance: float) -> Dict[str, float]:
        """Calculate adjustment multipliers based on performance"""

        # If performance is poor, relax thresholds to get more opportunities
        # If performance is good, tighten thresholds to maintain quality

        if win_rate < 0.35:  # Poor performance
            signal_multiplier = 0.85  # Lower signal strength threshold
            position_multiplier = 1.2  # Allow more positions
            risk_multiplier = 1.3  # Increase risk per trade
            watchdog_win_rate_multiplier = 0.8  # Lower watchdog threshold
            watchdog_losses_multiplier = 1.4  # Allow more consecutive losses
        elif win_rate < 0.45:  # Below average
            signal_multiplier = 0.9
            position_multiplier = 1.1
            risk_multiplier = 1.15
            watchdog_win_rate_multiplier = 0.9
            watchdog_losses_multiplier = 1.2
        elif win_rate > 0.65:  # Excellent performance
            signal_multiplier = 1.1  # Tighten signal requirements
            position_multiplier = 0.8  # Reduce position count
            risk_multiplier = 0.8  # Reduce risk per trade
            watchdog_win_rate_multiplier = 1.1
            watchdog_losses_multiplier = 0.8
        else:  # Average performance (40-60% win rate)
            signal_multiplier = 1.0
            position_multiplier = 1.0
            risk_multiplier = 1.0
            watchdog_win_rate_multiplier = 1.0
            watchdog_losses_multiplier = 1.0

        # Adjust based on signal acceptance rate
        if signal_acceptance < 0.1:  # Very few signals accepted
            signal_multiplier *= 0.9  # Lower threshold to get more signals
            position_multiplier *= 1.1
        elif signal_acceptance > 0.3:  # Many signals accepted
            signal_multiplier *= 1.05  # Slightly tighten to maintain quality

        return {
            'signal_strength': signal_multiplier,
            'positions': position_multiplier,
            'risk': risk_multiplier,
            'watchdog_win_rate': watchdog_win_rate_multiplier,
            'watchdog_losses': watchdog_losses_multiplier
        }

    def get_current_thresholds(self) -> Dict[str, Any]:
        """Get current adaptive thresholds"""
        return {
            'min_signal_strength': self.adaptive_thresholds.min_signal_strength,
            'max_positions': self.adaptive_thresholds.max_positions,
            'per_trade_risk_percent': self.adaptive_thresholds.per_trade_risk_percent,
            'strategy_watchdog_win_rate': self.adaptive_thresholds.strategy_watchdog_win_rate,
            'strategy_watchdog_consecutive_losses': self.adaptive_thresholds.strategy_watchdog_consecutive_losses,
            'market_regime': {
                'volatility': self.market_regime.volatility_regime,
                'trend': self.market_regime.trend_regime,
                'volume': self.market_regime.volume_regime,
                'confidence': self.market_regime.confidence
            },
            'performance_metrics': {
                'recent_win_rate': self._calculate_recent_win_rate(),
                'signal_acceptance_rate': self._calculate_signal_acceptance_rate(),
                'recent_trades_count': len(self.recent_trades),
                'recent_signals_count': len(self.recent_signals)
            },
            'last_adjusted': self.adaptive_thresholds.last_adjusted.isoformat()
        }

    def reset_to_defaults(self):
        """Reset adaptive thresholds to default values"""
        self.adaptive_thresholds = AdaptiveThresholds(
            min_signal_strength=75.0,
            max_positions=5,
            per_trade_risk_percent=1.0,
            strategy_watchdog_win_rate=45.0,
            strategy_watchdog_consecutive_losses=5,
            last_adjusted=datetime.now()
        )
        logger.info("Adaptive thresholds reset to defaults")

    def force_adjustment(self):
        """Force an immediate threshold adjustment"""
        if len(self.recent_trades) >= self.min_history_points:
            self.adjust_thresholds()
        else:
            logger.warning("Not enough trade history for adjustment")


# Global instance
adaptive_config = AdaptiveConfigurationManager()
