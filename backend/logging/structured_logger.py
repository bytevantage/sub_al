"""
Structured JSON Logging
Provides structured logging with better debugging capabilities
"""

import json
import logging
import time
import traceback
from datetime import datetime
from typing import Dict, Any, Optional
from pythonjsonlogger import jsonlogger

from backend.core.logger import get_logger

class StructuredJSONLogger:
    """Enhanced structured logging with JSON format"""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(f"structured.{name}")
        self.setup_json_formatter()
        
        # Additional context fields
        self.default_context = {
            'service': 'trading_engine',
            'version': '1.0.0',
            'environment': 'production'
        }
    
    def setup_json_formatter(self):
        """Setup JSON formatter for structured logging"""
        
        # Create custom JSON formatter
        class CustomJSONFormatter(jsonlogger.JsonFormatter):
            def add_fields(self, log_record, record, message_dict):
                super().add_fields(log_record, record, message_dict)
                
                # Add custom fields
                if not log_record.get('timestamp'):
                    log_record['timestamp'] = now_ist().isoformat()
                
                if not log_record.get('level'):
                    log_record['level'] = record.levelname
                
                # Add function and line info for debugging
                if log_record.get('level') in ['ERROR', 'CRITICAL']:
                    log_record['function'] = record.funcName
                    log_record['line'] = record.lineno
                    log_record['module'] = record.module
                
                # Add process info for performance tracking
                log_record['process_id'] = record.process
                log_record['thread_id'] = record.thread
        
        # Remove existing handlers
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        # Add JSON handler
        handler = logging.StreamHandler()
        handler.setFormatter(CustomJSONFormatter(
            '%(timestamp)s %(level)s %(name)s %(message)s'
        ))
        
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
    
    def _log_with_context(self, level: str, message: str, **context):
        """Log message with structured context"""
        
        # Merge default context with provided context
        log_context = {**self.default_context, **context}
        
        # Add performance metrics if available
        if 'duration' in context:
            log_context['performance_ms'] = round(context['duration'] * 1000, 2)
        
        # Add error details for error levels
        if level in ['ERROR', 'CRITICAL'] and 'error' not in context:
            log_context['error'] = traceback.format_exc()
        
        # Log with JSON formatter
        getattr(self.logger, level.lower())(message, extra=log_context)
    
    def info(self, message: str, **context):
        """Info level log with context"""
        self._log_with_context('INFO', message, **context)
    
    def warning(self, message: str, **context):
        """Warning level log with context"""
        self._log_with_context('WARNING', message, **context)
    
    def error(self, message: str, **context):
        """Error level log with context"""
        self._log_with_context('ERROR', message, **context)
    
    def critical(self, message: str, **context):
        """Critical level log with context"""
        self._log_with_context('CRITICAL', message, **context)
    
    def debug(self, message: str, **context):
        """Debug level log with context"""
        self._log_with_context('DEBUG', message, **context)
    
    def log_api_request(self, method: str, endpoint: str, status_code: int, 
                       response_time: float, user_id: Optional[str] = None, **context):
        """Log API request with structured data"""
        
        self.info(
            f"API {method} {endpoint}",
            event_type='api_request',
            method=method,
            endpoint=endpoint,
            status_code=status_code,
            response_time=response_time,
            user_id=user_id,
            **context
        )
    
    def log_database_query(self, query_type: str, table: str, duration: float, 
                          rows_affected: Optional[int] = None, **context):
        """Log database query performance"""
        
        self.info(
            f"Database {query_type} on {table}",
            event_type='database_query',
            query_type=query_type,
            table=table,
            duration=duration,
            rows_affected=rows_affected,
            **context
        )
    
    def log_cache_operation(self, operation: str, cache_type: str, key: str, 
                           hit: Optional[bool] = None, duration: float = 0, **context):
        """Log cache operations"""
        
        self.info(
            f"Cache {operation} {key}",
            event_type='cache_operation',
            operation=operation,
            cache_type=cache_type,
            key=key,
            hit=hit,
            duration=duration,
            **context
        )
    
    def log_trading_event(self, event_type: str, symbol: str, strategy: str, 
                         quantity: Optional[int] = None, price: Optional[float] = None, **context):
        """Log trading events"""
        
        self.info(
            f"Trading {event_type} for {symbol}",
            event_type='trading_event',
            trading_event=event_type,
            symbol=symbol,
            strategy=strategy,
            quantity=quantity,
            price=price,
            **context
        )
    
    def log_market_data(self, data_type: str, symbol: str, source: str, 
                       records_count: Optional[int] = None, **context):
        """Log market data events"""
        
        self.info(
            f"Market data {data_type} for {symbol}",
            event_type='market_data',
            data_type=data_type,
            symbol=symbol,
            source=source,
            records_count=records_count,
            **context
        )
    
    def log_health_check(self, check_name: str, status: str, response_time: float, 
                         **context):
        """Log health check results"""
        
        level = 'info' if status == 'healthy' else 'warning' if status == 'warning' else 'error'
        
        self._log_with_context(
            level.upper(),
            f"Health check {check_name}: {status}",
            event_type='health_check',
            check_name=check_name,
            status=status,
            response_time=response_time,
            **context
        )
    
    def log_performance_metric(self, metric_name: str, value: float, unit: str, **context):
        """Log performance metrics"""
        
        self.info(
            f"Performance metric {metric_name}: {value} {unit}",
            event_type='performance_metric',
            metric_name=metric_name,
            value=value,
            unit=unit,
            **context
        )
    
    def log_error_with_context(self, error: Exception, context: Dict[str, Any], **extra_context):
        """Log error with full context"""
        
        self.error(
            f"Error: {str(error)}",
            event_type='error',
            error_type=type(error).__name__,
            error_message=str(error),
            context=context,
            **extra_context
        )
    
    def log_business_event(self, event_name: str, **context):
        """Log business events for analytics"""
        
        self.info(
            f"Business event: {event_name}",
            event_type='business_event',
            business_event=event_name,
            **context
        )
    
    def log_security_event(self, event_type: str, severity: str, **context):
        """Log security events"""
        
        level = 'warning' if severity == 'medium' else 'error' if severity == 'high' else 'critical'
        
        self._log_with_context(
            level.upper(),
            f"Security event: {event_type}",
            event_type='security_event',
            security_event=event_type,
            severity=severity,
            **context
        )
    
    def create_child_logger(self, name: str, **additional_context):
        """Create child logger with additional context"""
        
        child_logger = StructuredJSONLogger(name)
        child_logger.default_context.update(self.default_context)
        child_logger.default_context.update(additional_context)
        
        return child_logger

# Global structured logger instances
_structured_loggers: Dict[str, StructuredJSONLogger] = {}

def get_structured_logger(name: str) -> StructuredJSONLogger:
    """Get structured logger instance"""
    global _structured_loggers
    
    if name not in _structured_loggers:
        _structured_loggers[name] = StructuredJSONLogger(name)
    
    return _structured_loggers[name]

# Convenience functions for common logging patterns
def log_api_call(method: str, endpoint: str, status: int, duration: float, **context):
    """Convenience function for API logging"""
    logger = get_structured_logger('api')
    logger.log_api_request(method, endpoint, status, duration, **context)

def log_database_operation(operation: str, table: str, duration: float, **context):
    """Convenience function for database logging"""
    logger = get_structured_logger('database')
    logger.log_database_query(operation, table, duration, **context)

def log_cache_hit(cache_type: str, key: str, hit: bool, duration: float = 0, **context):
    """Convenience function for cache logging"""
    logger = get_structured_logger('cache')
    logger.log_cache_operation('get' if hit else 'miss', cache_type, key, hit, duration, **context)

def log_trade_event(event: str, symbol: str, strategy: str, **context):
    """Convenience function for trade logging"""
    logger = get_structured_logger('trading')
    logger.log_trading_event(event, symbol, strategy, **context)

def log_market_data_update(data_type: str, symbol: str, source: str, **context):
    """Convenience function for market data logging"""
    logger = get_structured_logger('market_data')
    logger.log_market_data(data_type, symbol, source, **context)
