"""
Market Data Monitor
Monitors data quality and implements fallback mechanisms
"""

import asyncio
from typing import Dict, Optional, List, Callable
from datetime import datetime, timedelta
from collections import deque
from enum import Enum

from backend.core.logger import get_logger

logger = get_logger(__name__)


class DataQuality(Enum):
    """Data quality levels"""
    EXCELLENT = "excellent"  # Fresh, complete data
    GOOD = "good"           # Slightly delayed but usable
    POOR = "poor"           # Stale or incomplete
    FAILED = "failed"       # No data available


class MarketDataMonitor:
    """
    Monitors market data quality and reliability
    
    Features:
    - Stale data detection
    - Missing data tracking
    - Quality scoring
    - Fallback mechanisms
    - Streaming failure alerts
    """
    
    def __init__(self, config: Dict):
        self.config = config
        
        # Thresholds
        self.stale_threshold_seconds = config.get('stale_threshold_seconds', 5)
        self.critical_threshold_seconds = config.get('critical_threshold_seconds', 10)
        self.min_quality_score = config.get('min_quality_score', 0.7)
        
        # Data tracking
        self.last_update_times: Dict[str, datetime] = {}
        self.update_history: Dict[str, deque] = {}
        self.quality_scores: Dict[str, float] = {}
        self.failure_counts: Dict[str, int] = {}
        
        # Alerts
        self.alert_callbacks: List[Callable] = []
        self.consecutive_failures = 0
        self.max_consecutive_failures = config.get('max_consecutive_failures', 3)
        
        # Fallback state
        self.using_fallback = False
        self.fallback_provider = None
        
    def register_alert_callback(self, callback: Callable):
        """Register callback for data quality alerts"""
        self.alert_callbacks.append(callback)
        
    async def validate_data(
        self,
        symbol: str,
        data: Dict,
        timestamp: Optional[datetime] = None
    ) -> tuple[bool, DataQuality, Optional[str]]:
        """
        Validate market data quality
        
        Args:
            symbol: Instrument symbol
            data: Market data dict
            timestamp: Data timestamp (defaults to now)
            
        Returns:
            (is_valid, quality_level, error_message)
        """
        
        timestamp = timestamp or datetime.now()
        issues = []
        
        # 1. Check data freshness
        freshness_issue = self._check_freshness(symbol, timestamp)
        if freshness_issue:
            issues.append(freshness_issue)
            
        # 2. Check completeness
        completeness_issue = self._check_completeness(symbol, data)
        if completeness_issue:
            issues.append(completeness_issue)
            
        # 3. Check reasonableness
        reasonableness_issue = self._check_reasonableness(symbol, data)
        if reasonableness_issue:
            issues.append(reasonableness_issue)
            
        # Calculate quality score
        quality_score = self._calculate_quality_score(issues, timestamp)
        self.quality_scores[symbol] = quality_score
        
        # Determine quality level
        if quality_score >= 0.9:
            quality = DataQuality.EXCELLENT
        elif quality_score >= 0.7:
            quality = DataQuality.GOOD
        elif quality_score >= 0.5:
            quality = DataQuality.POOR
        else:
            quality = DataQuality.FAILED
            
        # Track update
        self.last_update_times[symbol] = timestamp
        if symbol not in self.update_history:
            self.update_history[symbol] = deque(maxlen=100)
        self.update_history[symbol].append({
            'timestamp': timestamp,
            'quality': quality.value,
            'score': quality_score
        })
        
        # Handle failures
        is_valid = quality_score >= self.min_quality_score
        if not is_valid:
            await self._handle_validation_failure(symbol, issues, quality)
        else:
            # Reset failure count on success
            self.failure_counts[symbol] = 0
            self.consecutive_failures = 0
            
        error_message = "; ".join(issues) if issues else None
        
        return is_valid, quality, error_message
        
    def _check_freshness(self, symbol: str, timestamp: datetime) -> Optional[str]:
        """Check if data is fresh"""
        now = datetime.now()
        age_seconds = (now - timestamp).total_seconds()
        
        if age_seconds > self.critical_threshold_seconds:
            return f"CRITICAL: Data is {age_seconds:.1f}s old (>{self.critical_threshold_seconds}s)"
        elif age_seconds > self.stale_threshold_seconds:
            return f"WARNING: Data is {age_seconds:.1f}s old (>{self.stale_threshold_seconds}s)"
            
        return None
        
    def _check_completeness(self, symbol: str, data: Dict) -> Optional[str]:
        """Check if all required fields are present"""
        required_fields = ['ltp', 'bid', 'ask', 'volume']
        missing_fields = [f for f in required_fields if f not in data or data[f] is None]
        
        if missing_fields:
            return f"Missing fields: {', '.join(missing_fields)}"
            
        return None
        
    def _check_reasonableness(self, symbol: str, data: Dict) -> Optional[str]:
        """Check if data values are reasonable"""
        issues = []
        
        # Check prices are positive
        for field in ['ltp', 'bid', 'ask']:
            if field in data and data[field] is not None:
                if data[field] <= 0:
                    issues.append(f"{field} is non-positive: {data[field]}")
                    
        # Check bid <= ltp <= ask (if all present)
        if all(f in data and data[f] is not None for f in ['bid', 'ltp', 'ask']):
            bid, ltp, ask = data['bid'], data['ltp'], data['ask']
            
            if bid > ltp:
                issues.append(f"bid ({bid}) > ltp ({ltp})")
            if ltp > ask:
                issues.append(f"ltp ({ltp}) > ask ({ask})")
            if bid > ask:
                issues.append(f"bid ({bid}) > ask ({ask})")
                
        # Check spread reasonableness (shouldn't be >20% of price)
        if all(f in data and data[f] is not None for f in ['bid', 'ask', 'ltp']):
            spread = data['ask'] - data['bid']
            spread_percent = (spread / data['ltp'] * 100) if data['ltp'] > 0 else 0
            
            if spread_percent > 20:
                issues.append(f"Excessive spread: {spread_percent:.1f}%")
                
        # Check IV reasonableness (if present)
        if 'iv' in data and data['iv'] is not None:
            iv = data['iv']
            if iv < 0 or iv > 200:
                issues.append(f"Unreasonable IV: {iv:.1f}%")
                
        return "; ".join(issues) if issues else None
        
    def _calculate_quality_score(self, issues: List[str], timestamp: datetime) -> float:
        """Calculate data quality score (0-1)"""
        score = 1.0
        
        # Penalize based on issues
        critical_issues = sum(1 for issue in issues if 'CRITICAL' in issue)
        warning_issues = sum(1 for issue in issues if 'WARNING' in issue)
        other_issues = len(issues) - critical_issues - warning_issues
        
        score -= critical_issues * 0.5
        score -= warning_issues * 0.2
        score -= other_issues * 0.1
        
        # Penalize based on age
        age_seconds = (datetime.now() - timestamp).total_seconds()
        if age_seconds > self.stale_threshold_seconds:
            age_penalty = min(0.3, (age_seconds - self.stale_threshold_seconds) / 10 * 0.1)
            score -= age_penalty
            
        return max(0.0, score)
        
    async def _handle_validation_failure(
        self,
        symbol: str,
        issues: List[str],
        quality: DataQuality
    ):
        """Handle data validation failure"""
        
        # Track failure
        self.failure_counts[symbol] = self.failure_counts.get(symbol, 0) + 1
        self.consecutive_failures += 1
        
        logger.error(
            f"❌ Data validation failed for {symbol}\n"
            f"Quality: {quality.value}\n"
            f"Issues: {'; '.join(issues)}\n"
            f"Consecutive failures: {self.consecutive_failures}"
        )
        
        # Trigger alerts if threshold exceeded
        if self.consecutive_failures >= self.max_consecutive_failures:
            await self._trigger_alerts(symbol, issues, quality)
            
        # Consider fallback
        if not self.using_fallback and self.consecutive_failures >= self.max_consecutive_failures:
            await self._activate_fallback()
            
    async def _trigger_alerts(
        self,
        symbol: str,
        issues: List[str],
        quality: DataQuality
    ):
        """Trigger all registered alert callbacks"""
        
        alert_data = {
            'symbol': symbol,
            'issues': issues,
            'quality': quality.value,
            'consecutive_failures': self.consecutive_failures,
            'timestamp': datetime.now().isoformat()
        }
        
        logger.critical(
            f"🚨 DATA QUALITY ALERT 🚨\n"
            f"Symbol: {symbol}\n"
            f"Consecutive failures: {self.consecutive_failures}\n"
            f"Issues: {'; '.join(issues)}"
        )
        
        for callback in self.alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(alert_data)
                else:
                    callback(alert_data)
            except Exception as e:
                logger.error(f"Error in alert callback: {e}")
                
    async def _activate_fallback(self):
        """Activate fallback data provider"""
        self.using_fallback = True
        
        logger.warning(
            "⚠️ Activating fallback data provider due to repeated failures"
        )
        
        # TODO: Implement actual fallback provider switch
        # For now, just log the event
        
    def get_quality_report(self) -> Dict:
        """Get comprehensive quality report"""
        now = datetime.now()
        
        report = {
            'timestamp': now.isoformat(),
            'using_fallback': self.using_fallback,
            'consecutive_failures': self.consecutive_failures,
            'symbols': {}
        }
        
        for symbol, last_update in self.last_update_times.items():
            age_seconds = (now - last_update).total_seconds()
            
            report['symbols'][symbol] = {
                'last_update': last_update.isoformat(),
                'age_seconds': round(age_seconds, 1),
                'quality_score': self.quality_scores.get(symbol, 0),
                'failure_count': self.failure_counts.get(symbol, 0),
                'is_stale': age_seconds > self.stale_threshold_seconds,
                'is_critical': age_seconds > self.critical_threshold_seconds
            }
            
        return report
        
    def is_symbol_healthy(self, symbol: str) -> bool:
        """Check if symbol has healthy data"""
        if symbol not in self.last_update_times:
            return False
            
        # Check age
        age_seconds = (datetime.now() - self.last_update_times[symbol]).total_seconds()
        if age_seconds > self.critical_threshold_seconds:
            return False
            
        # Check quality score
        if self.quality_scores.get(symbol, 0) < self.min_quality_score:
            return False
            
        return True
        
    async def check_streaming_health(self) -> bool:
        """Check overall streaming health"""
        
        if not self.last_update_times:
            logger.warning("No market data updates received")
            return False
            
        # Check how many symbols are healthy
        total_symbols = len(self.last_update_times)
        healthy_symbols = sum(1 for symbol in self.last_update_times if self.is_symbol_healthy(symbol))
        
        health_percent = healthy_symbols / total_symbols * 100 if total_symbols > 0 else 0
        
        if health_percent < 50:
            logger.error(
                f"⚠️ Streaming health critical: only {health_percent:.0f}% symbols healthy"
            )
            return False
            
        return True
