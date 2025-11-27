"""
Configuration Management Module
Loads and manages application configuration
"""

import os
import yaml
import json
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application Settings"""
    
    # Trading Configuration
    mode: str = Field(default="paper", env="MODE")
    initial_capital: float = Field(default=100000, env="INITIAL_CAPITAL")
    
    # Risk Management
    risk_percent: float = Field(default=3, env="RISK_PERCENT")
    min_signal_strength: int = Field(default=75, env="MIN_SIGNAL_STRENGTH")
    
    # Database
    db_host: str = Field(default="localhost", env="DB_HOST")
    db_port: int = Field(default=5432, env="DB_PORT")
    db_name: str = Field(default="trading_db", env="DB_NAME")
    db_user: str = Field(default="trading_user", env="DB_USER")
    db_password: str = Field(default="trading_pass", env="DB_PASSWORD")
    
    # Redis
    redis_host: str = Field(default="localhost", env="REDIS_HOST")
    redis_port: int = Field(default=6379, env="REDIS_PORT")
    
    # API
    api_host: str = Field(default="0.0.0.0", env="API_HOST")
    api_port: int = Field(default=8000, env="API_PORT")
    
    # Upstox
    upstox_token_file: str = Field(default="config/upstox_token.json", env="UPSTOX_TOKEN_FILE")
    upstox_client_secret: Optional[str] = Field(default=None, env="UPSTOX_CLIENT_SECRET")
    
    # Feature Flags
    enable_ml: bool = Field(default=True, env="ENABLE_ML")
    enable_backtesting: bool = Field(default=True, env="ENABLE_BACKTESTING")
    enable_paper_trading: bool = Field(default=True, env="ENABLE_PAPER_TRADING")
    enable_live_trading: bool = Field(default=False, env="ENABLE_LIVE_TRADING")
    
    # SAC Training Configuration (Systems Operator)
    sac_online_only_weekdays: bool = Field(default=True, env="SAC_ONLINE_ONLY_WEEKDAYS")
    sac_exploration_noise: float = Field(default=0.05, env="SAC_EXPLORATION_NOISE")
    sac_max_noise_after_days: int = Field(default=30, env="SAC_MAX_NOISE_AFTER_DAYS")
    
    class Config:
        env_file = ".env"
        case_sensitive = False


class ConfigManager:
    """Manages application configuration from YAML and environment"""
    
    def __init__(self, config_path: str = "config/config.yaml"):
        self.config_path = Path(config_path)
        self.settings = Settings()
        self.config: Dict[str, Any] = {}
        self.load_config()
        
    def load_config(self) -> None:
        """Load configuration from YAML file"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    self.config = yaml.safe_load(f)
                print(f"✓ Configuration loaded from {self.config_path}")
            else:
                print(f"⚠ Configuration file not found: {self.config_path}")
                self.config = self._get_default_config()
        except Exception as e:
            print(f"✗ Error loading configuration: {e}")
            self.config = self._get_default_config()

        self._apply_env_overrides()
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key (supports nested keys with dot notation)"""
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
                
        return value if value is not None else default
    
    def get_upstox_token(self) -> Optional[str]:
        """Load Upstox access token from file"""
        try:
            token_path = Path(self.settings.upstox_token_file)
            
            # Try JSON format first (from upstox_auth_working.py)
            if token_path.exists():
                with open(token_path, 'r') as f:
                    token_data = json.load(f)
                    return token_data.get('access_token')
            
            # Fallback to text format
            txt_path = Path("config/upstox_token.txt")
            if txt_path.exists():
                with open(txt_path, 'r') as f:
                    return f.read().strip()
                    
            print("⚠ No Upstox token file found. Please run upstox_auth_working.py")
            return None
            
        except Exception as e:
            print(f"✗ Error loading Upstox token: {e}")
            return None
    
    def get_database_url(self) -> str:
        """Get PostgreSQL database URL"""
        return (
            f"postgresql://{self.settings.db_user}:{self.settings.db_password}"
            f"@{self.settings.db_host}:{self.settings.db_port}/{self.settings.db_name}"
        )
    
    def get_redis_url(self) -> str:
        """Get Redis connection URL"""
        return f"redis://{self.settings.redis_host}:{self.settings.redis_port}/0"
    
    def is_live_mode(self) -> bool:
        """Check if system is in live trading mode"""
        return self.settings.mode.lower() == "live" and self.settings.enable_live_trading
    
    def is_paper_mode(self) -> bool:
        """Check if system is in paper trading mode"""
        return self.settings.mode.lower() == "paper"
    
    def get_sac_training_config(self) -> Dict[str, Any]:
        """Get SAC training configuration"""
        return {
            'online_only_weekdays': self.settings.sac_online_only_weekdays,
            'full_retrain_days': self.get('sac_training.full_retrain_days', ['Friday', 'Sunday']),
            'exploration_noise': self.settings.sac_exploration_noise,
            'max_noise_after_days': self.settings.sac_max_noise_after_days,
            'critic_loss_alert_threshold': self.get('sac_training.critic_loss_alert_threshold', 3.0),
            'model_path': self.get('sac_meta_controller.model_path', 'models/sac_prod_latest.pth')
        }

    def _get_default_config(self) -> Dict[str, Any]:
        """Return default configuration"""
        return {
            'trading': {
                'mode': 'paper',
                'initial_capital': 100000,
                'max_positions': 5,
                'signal_cooldown_seconds': 300
            },
            'risk': {
                'daily_loss_limit_percent': 3,
                'per_trade_risk_percent': 1,
                'max_capital_at_risk_percent': 10,
                'min_signal_strength': 75
            }
        }

    def _apply_env_overrides(self) -> None:
        """Apply environment variable overrides for sensitive settings"""
        override_password = os.getenv("CIRCUIT_BREAKER_OVERRIDE_PASSWORD")
        safety_config = self.config.setdefault('safety', {}).setdefault('circuit_breaker', {})

        if override_password:
            safety_config['override_password'] = override_password
        else:
            current_password = safety_config.get('override_password')
            if not current_password or current_password == 'OVERRIDE123':
                print(
                    "⚠ Warning: CIRCUIT_BREAKER_OVERRIDE_PASSWORD not set. "
                    "Using default override password; update environment variable for production."
                )


# Global configuration instance
config = ConfigManager()
