"""
Data Quality Monitor

Monitors data quality across market feeds, option chains, and technical indicators.
Detects anomalies, stale data, and feed health issues to prevent bad trades.

Features:
- Stale data detection (timestamp checks)
- Strike filtering anomaly detection (excessive removal %)
- Feed health monitoring (API response times, failures)
- Prometheus metrics integration
- Alerting thresholds with logging

Usage:
    # Initialize monitor
    monitor = get_data_quality_monitor()
    
    # Check market state quality
    issues = monitor.check_market_state(market_state)
    if issues:
        logger.warning(f"Data quality issues: {issues}")
    
    # Record API call
    monitor.record_api_call('upstox', duration_ms=150, success=True)
    
    # Get quality report
    report = monitor.get_quality_report()
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from collections import deque
import time

logger = logging.getLogger(__name__)


@dataclass
class DataQualityIssue:
    """Represents a data quality issue"""
    severity: str  # 'critical', 'warning', 'info'
    category: str  # 'stale_data', 'strike_filtering', 'feed_health', 'missing_data'
    message: str
    timestamp: str
    details: Dict[str, Any]
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class FeedHealthMetrics:
    """Health metrics for a data feed"""
    feed_name: str
    total_calls: int
    successful_calls: int
    failed_calls: int
    avg_response_time_ms: float
    max_response_time_ms: float
    last_success_time: Optional[str]
    last_failure_time: Optional[str]
    failure_rate: float
    
    def to_dict(self) -> Dict:
        return asdict(self)


class DataQualityMonitor:
    """
    Monitors data quality and detects anomalies.
    
    Thresholds (configurable):
    - Stale data: > 5 minutes old
    - Strike removal: > 70% filtered out
    - API response time: > 2000ms (warning), > 5000ms (critical)
    - API failure rate: > 10% (warning), > 30% (critical)
    """
    
    def __init__(
        self,
        stale_threshold_seconds: int = 300,  # 5 minutes
        strike_removal_warning: float = 0.70,  # 70%
        strike_removal_critical: float = 0.90,  # 90%
        api_response_warning_ms: float = 2000,  # 2 seconds
        api_response_critical_ms: float = 5000,  # 5 seconds
        api_failure_warning_rate: float = 0.10,  # 10%
        api_failure_critical_rate: float = 0.30,  # 30%
    ):
        # Thresholds
        self.stale_threshold_seconds = stale_threshold_seconds
        self.strike_removal_warning = strike_removal_warning
        self.strike_removal_critical = strike_removal_critical
        self.api_response_warning_ms = api_response_warning_ms
        self.api_response_critical_ms = api_response_critical_ms
        self.api_failure_warning_rate = api_failure_warning_rate
        self.api_failure_critical_rate = api_failure_critical_rate
        
        # Tracking
        self.issues_history = deque(maxlen=1000)  # Last 1000 issues
        self.api_metrics = {}  # Feed name -> list of (timestamp, duration_ms, success)
        self.api_metrics_window = 1000  # Track last 1000 calls per feed
        
        logger.info("✓ DataQualityMonitor initialized")
    
    def check_market_state(self, market_state: Dict) -> List[DataQualityIssue]:
        """
        Comprehensive check of market state quality.
        
        Args:
            market_state: Market state dictionary from MarketDataManager
        
        Returns:
            List of data quality issues (empty if all OK)
        """
        issues = []
        
        # Check 1: Stale data detection
        stale_issues = self._check_stale_data(market_state)
        issues.extend(stale_issues)
        
        # Check 2: Missing critical fields
        missing_issues = self._check_missing_fields(market_state)
        issues.extend(missing_issues)
        
        # Check 3: Strike filtering anomalies
        strike_issues = self._check_strike_filtering(market_state)
        issues.extend(strike_issues)
        
        # Check 4: Data consistency
        consistency_issues = self._check_data_consistency(market_state)
        issues.extend(consistency_issues)
        
        # Record issues
        for issue in issues:
            self.issues_history.append(issue)
            
            # Log based on severity
            if issue.severity == 'critical':
                logger.error(f"🚨 DATA QUALITY CRITICAL: {issue.message}")
            elif issue.severity == 'warning':
                logger.warning(f"⚠️  DATA QUALITY WARNING: {issue.message}")
            else:
                logger.info(f"ℹ️  DATA QUALITY INFO: {issue.message}")
        
        return issues
    
    def _check_stale_data(self, market_state: Dict) -> List[DataQualityIssue]:
        """Check if market data is stale"""
        issues = []
        
        timestamp_str = market_state.get('timestamp')
        if not timestamp_str:
            issues.append(DataQualityIssue(
                severity='critical',
                category='stale_data',
                message='Market state missing timestamp',
                timestamp=datetime.now().isoformat(),
                details={'market_state': market_state}
            ))
            return issues
        
        try:
            # Parse timestamp
            data_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            current_time = datetime.now(data_time.tzinfo) if data_time.tzinfo else datetime.now()
            
            age_seconds = (current_time - data_time).total_seconds()
            
            if age_seconds > self.stale_threshold_seconds:
                issues.append(DataQualityIssue(
                    severity='critical' if age_seconds > self.stale_threshold_seconds * 2 else 'warning',
                    category='stale_data',
                    message=f'Market data is {age_seconds:.0f}s old (threshold: {self.stale_threshold_seconds}s)',
                    timestamp=current_time.isoformat(),
                    details={
                        'data_timestamp': timestamp_str,
                        'age_seconds': age_seconds,
                        'threshold_seconds': self.stale_threshold_seconds
                    }
                ))
        
        except Exception as e:
            issues.append(DataQualityIssue(
                severity='warning',
                category='stale_data',
                message=f'Failed to parse timestamp: {e}',
                timestamp=datetime.now().isoformat(),
                details={'timestamp_str': timestamp_str, 'error': str(e)}
            ))
        
        return issues
    
    def _check_missing_fields(self, market_state: Dict) -> List[DataQualityIssue]:
        """Check for missing critical fields"""
        issues = []
        
        # Required fields
        required_fields = ['symbol', 'spot_price', 'timestamp']
        
        for field in required_fields:
            if field not in market_state or market_state[field] is None:
                issues.append(DataQualityIssue(
                    severity='critical',
                    category='missing_data',
                    message=f'Critical field missing: {field}',
                    timestamp=datetime.now().isoformat(),
                    details={'field': field, 'market_state_keys': list(market_state.keys())}
                ))
        
        # Optional but important fields
        optional_fields = ['option_chain', 'technical_indicators', 'total_call_oi', 'total_put_oi']
        
        for field in optional_fields:
            if field not in market_state or market_state[field] is None:
                issues.append(DataQualityIssue(
                    severity='warning',
                    category='missing_data',
                    message=f'Optional field missing: {field}',
                    timestamp=datetime.now().isoformat(),
                    details={'field': field}
                ))
        
        return issues
    
    def _check_strike_filtering(self, market_state: Dict) -> List[DataQualityIssue]:
        """Check for excessive strike filtering anomalies"""
        issues = []
        
        option_chain = market_state.get('option_chain')
        if not option_chain:
            return issues  # Already flagged in missing_fields check
        
        # Check if we have metadata about filtering
        original_strikes = option_chain.get('_original_strike_count', 0)
        filtered_strikes = option_chain.get('_filtered_strike_count', 0)
        
        if original_strikes > 0:
            removal_rate = 1 - (filtered_strikes / original_strikes)
            
            if removal_rate > self.strike_removal_critical:
                issues.append(DataQualityIssue(
                    severity='critical',
                    category='strike_filtering',
                    message=f'Excessive strike filtering: {removal_rate*100:.1f}% removed (threshold: {self.strike_removal_critical*100:.0f}%)',
                    timestamp=datetime.now().isoformat(),
                    details={
                        'original_strikes': original_strikes,
                        'filtered_strikes': filtered_strikes,
                        'removal_rate': removal_rate,
                        'threshold': self.strike_removal_critical
                    }
                ))
            elif removal_rate > self.strike_removal_warning:
                issues.append(DataQualityIssue(
                    severity='warning',
                    category='strike_filtering',
                    message=f'High strike filtering: {removal_rate*100:.1f}% removed (threshold: {self.strike_removal_warning*100:.0f}%)',
                    timestamp=datetime.now().isoformat(),
                    details={
                        'original_strikes': original_strikes,
                        'filtered_strikes': filtered_strikes,
                        'removal_rate': removal_rate,
                        'threshold': self.strike_removal_warning
                    }
                ))
        
        # Check if we have any strikes at all
        calls = option_chain.get('calls', [])
        puts = option_chain.get('puts', [])
        
        if not calls and not puts:
            issues.append(DataQualityIssue(
                severity='critical',
                category='strike_filtering',
                message='Option chain has zero strikes after filtering',
                timestamp=datetime.now().isoformat(),
                details={'original_strikes': original_strikes}
            ))
        
        return issues
    
    def _check_data_consistency(self, market_state: Dict) -> List[DataQualityIssue]:
        """Check data consistency (logical validations)"""
        issues = []
        
        # Check 1: Spot price sanity
        spot_price = market_state.get('spot_price', 0)
        if spot_price <= 0:
            issues.append(DataQualityIssue(
                severity='critical',
                category='missing_data',
                message=f'Invalid spot price: {spot_price}',
                timestamp=datetime.now().isoformat(),
                details={'spot_price': spot_price}
            ))
        elif spot_price < 10000 or spot_price > 30000:
            # Assume NIFTY trading range
            issues.append(DataQualityIssue(
                severity='warning',
                category='missing_data',
                message=f'Spot price out of expected range: {spot_price}',
                timestamp=datetime.now().isoformat(),
                details={'spot_price': spot_price, 'expected_range': (10000, 30000)}
            ))
        
        # Check 2: OI consistency
        total_call_oi = market_state.get('total_call_oi', 0)
        total_put_oi = market_state.get('total_put_oi', 0)
        total_oi = market_state.get('total_oi', 0)
        
        if total_call_oi < 0 or total_put_oi < 0 or total_oi < 0:
            issues.append(DataQualityIssue(
                severity='critical',
                category='missing_data',
                message='Negative OI values detected',
                timestamp=datetime.now().isoformat(),
                details={
                    'total_call_oi': total_call_oi,
                    'total_put_oi': total_put_oi,
                    'total_oi': total_oi
                }
            ))
        
        # Check 3: Option chain structure
        option_chain = market_state.get('option_chain')
        if option_chain:
            calls = option_chain.get('calls', [])
            puts = option_chain.get('puts', [])
            
            if isinstance(calls, list) and isinstance(puts, list):
                if len(calls) != len(puts):
                    issues.append(DataQualityIssue(
                        severity='info',
                        category='missing_data',
                        message=f'Unequal call/put strikes: {len(calls)} calls, {len(puts)} puts',
                        timestamp=datetime.now().isoformat(),
                        details={'num_calls': len(calls), 'num_puts': len(puts)}
                    ))
        
        return issues
    
    def record_api_call(self, feed_name: str, duration_ms: float, success: bool):
        """
        Record an API call for feed health monitoring.
        
        Args:
            feed_name: Name of the feed (e.g., 'upstox', 'nse')
            duration_ms: Response time in milliseconds
            success: Whether the call succeeded
        """
        if feed_name not in self.api_metrics:
            self.api_metrics[feed_name] = deque(maxlen=self.api_metrics_window)
        
        self.api_metrics[feed_name].append({
            'timestamp': datetime.now().isoformat(),
            'duration_ms': duration_ms,
            'success': success
        })
        
        # Check if this call triggered any thresholds
        if not success:
            logger.warning(f"⚠️  API call failed: {feed_name} (duration: {duration_ms:.0f}ms)")
        elif duration_ms > self.api_response_critical_ms:
            logger.error(f"🚨 API response time critical: {feed_name} ({duration_ms:.0f}ms > {self.api_response_critical_ms:.0f}ms)")
        elif duration_ms > self.api_response_warning_ms:
            logger.warning(f"⚠️  API response time slow: {feed_name} ({duration_ms:.0f}ms > {self.api_response_warning_ms:.0f}ms)")
    
    def get_feed_health(self, feed_name: str) -> Optional[FeedHealthMetrics]:
        """
        Get health metrics for a specific feed.
        
        Args:
            feed_name: Name of the feed
        
        Returns:
            FeedHealthMetrics or None if feed not tracked
        """
        if feed_name not in self.api_metrics:
            return None
        
        calls = list(self.api_metrics[feed_name])
        
        if not calls:
            return None
        
        total_calls = len(calls)
        successful_calls = sum(1 for c in calls if c['success'])
        failed_calls = total_calls - successful_calls
        
        durations = [c['duration_ms'] for c in calls if c['success']]
        avg_response_time_ms = sum(durations) / len(durations) if durations else 0
        max_response_time_ms = max(durations) if durations else 0
        
        last_success = next((c['timestamp'] for c in reversed(calls) if c['success']), None)
        last_failure = next((c['timestamp'] for c in reversed(calls) if not c['success']), None)
        
        failure_rate = failed_calls / total_calls if total_calls > 0 else 0
        
        return FeedHealthMetrics(
            feed_name=feed_name,
            total_calls=total_calls,
            successful_calls=successful_calls,
            failed_calls=failed_calls,
            avg_response_time_ms=avg_response_time_ms,
            max_response_time_ms=max_response_time_ms,
            last_success_time=last_success,
            last_failure_time=last_failure,
            failure_rate=failure_rate
        )
    
    def check_feed_health(self, feed_name: str) -> List[DataQualityIssue]:
        """
        Check feed health and return any issues.
        
        Args:
            feed_name: Name of the feed
        
        Returns:
            List of data quality issues
        """
        issues = []
        
        health = self.get_feed_health(feed_name)
        if not health:
            return issues
        
        # Check failure rate
        if health.failure_rate > self.api_failure_critical_rate:
            issues.append(DataQualityIssue(
                severity='critical',
                category='feed_health',
                message=f'{feed_name} failure rate critical: {health.failure_rate*100:.1f}% (threshold: {self.api_failure_critical_rate*100:.0f}%)',
                timestamp=datetime.now().isoformat(),
                details=health.to_dict()
            ))
        elif health.failure_rate > self.api_failure_warning_rate:
            issues.append(DataQualityIssue(
                severity='warning',
                category='feed_health',
                message=f'{feed_name} failure rate high: {health.failure_rate*100:.1f}% (threshold: {self.api_failure_warning_rate*100:.0f}%)',
                timestamp=datetime.now().isoformat(),
                details=health.to_dict()
            ))
        
        # Check average response time
        if health.avg_response_time_ms > self.api_response_critical_ms:
            issues.append(DataQualityIssue(
                severity='critical',
                category='feed_health',
                message=f'{feed_name} avg response time critical: {health.avg_response_time_ms:.0f}ms (threshold: {self.api_response_critical_ms:.0f}ms)',
                timestamp=datetime.now().isoformat(),
                details=health.to_dict()
            ))
        elif health.avg_response_time_ms > self.api_response_warning_ms:
            issues.append(DataQualityIssue(
                severity='warning',
                category='feed_health',
                message=f'{feed_name} avg response time slow: {health.avg_response_time_ms:.0f}ms (threshold: {self.api_response_warning_ms:.0f}ms)',
                timestamp=datetime.now().isoformat(),
                details=health.to_dict()
            ))
        
        return issues
    
    def get_quality_report(self) -> Dict:
        """
        Generate comprehensive data quality report.
        
        Returns:
            Dictionary with quality metrics and recent issues
        """
        report = {
            'timestamp': datetime.now().isoformat(),
            'recent_issues': [issue.to_dict() for issue in list(self.issues_history)[-50:]],  # Last 50 issues
            'feed_health': {},
            'summary': {
                'total_issues_tracked': len(self.issues_history),
                'critical_issues_last_hour': 0,
                'warning_issues_last_hour': 0,
            }
        }
        
        # Add feed health for all tracked feeds
        for feed_name in self.api_metrics.keys():
            health = self.get_feed_health(feed_name)
            if health:
                report['feed_health'][feed_name] = health.to_dict()
        
        # Count recent issues by severity
        one_hour_ago = datetime.now() - timedelta(hours=1)
        
        for issue in self.issues_history:
            try:
                issue_time = datetime.fromisoformat(issue.timestamp)
                if issue_time > one_hour_ago:
                    if issue.severity == 'critical':
                        report['summary']['critical_issues_last_hour'] += 1
                    elif issue.severity == 'warning':
                        report['summary']['warning_issues_last_hour'] += 1
            except:
                pass
        
        return report
    
    def reset_metrics(self):
        """Reset all metrics (useful for testing or daily resets)"""
        self.issues_history.clear()
        self.api_metrics.clear()
        logger.info("✓ Data quality metrics reset")


# Global instance
_monitor = None


def get_data_quality_monitor() -> DataQualityMonitor:
    """Get global DataQualityMonitor instance"""
    global _monitor
    if _monitor is None:
        _monitor = DataQualityMonitor()
    return _monitor
