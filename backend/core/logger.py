"""
Logging Configuration Module
Centralized logging for the trading system
"""

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from datetime import datetime
from pythonjsonlogger import jsonlogger


class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors for console output"""
    
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record):
        log_color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{log_color}{record.levelname}{self.RESET}"
        return super().format(record)


class TradingLogger:
    """Centralized logger for trading system"""
    
    def __init__(self, name: str = "TradingSystem", log_dir: str = "data/logs"):
        self.name = name
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        self.logger.handlers.clear()
        
        # Console Handler with colors
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = ColoredFormatter(
            '%(asctime)s | %(levelname)s | %(name)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        # File Handler - Rotating
        log_file = self.log_dir / f"trading_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=100 * 1024 * 1024,  # 100MB
            backupCount=10
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)
        
        # JSON Handler for structured logs
        json_file = self.log_dir / f"trading_{datetime.now().strftime('%Y%m%d')}.json"
        json_handler = RotatingFileHandler(
            json_file,
            maxBytes=100 * 1024 * 1024,
            backupCount=10
        )
        json_formatter = jsonlogger.JsonFormatter(
            '%(asctime)s %(levelname)s %(name)s %(funcName)s %(lineno)d %(message)s'
        )
        json_handler.setFormatter(json_formatter)
        self.logger.addHandler(json_handler)
        
    def get_logger(self) -> logging.Logger:
        """Get the logger instance"""
        return self.logger


# Global logger instance
trading_logger = TradingLogger()
logger = trading_logger.get_logger()


def get_logger(name: str = None) -> logging.Logger:
    """Get logger instance - module level function for imports"""
    if name:
        return logging.getLogger(f"TradingSystem.{name}")
    return logger


# Specialized loggers
def get_strategy_logger(strategy_name: str) -> logging.Logger:
    """Get logger for specific strategy"""
    return logging.getLogger(f"TradingSystem.Strategy.{strategy_name}")


def get_execution_logger() -> logging.Logger:
    """Get logger for execution layer"""
    return logging.getLogger("TradingSystem.Execution")


def get_data_logger() -> logging.Logger:
    """Get logger for data layer"""
    return logging.getLogger("TradingSystem.Data")


def get_ml_logger() -> logging.Logger:
    """Get logger for ML layer"""
    return logging.getLogger("TradingSystem.ML")
