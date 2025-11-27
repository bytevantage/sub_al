#!/usr/bin/env python3
"""
Simple Trading Engine Health Monitor
Monitors trading engine health and sends alerts
"""

import os
import sys
import time
import requests
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from backend.core.timezone_utils import now_ist, is_market_hours, IST

# Setup logging
log_file = project_root / "data" / "logs" / "health_monitor.log"
log_file.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class HealthMonitor:
    """Simple health monitor for trading engine"""
    
    def __init__(self):
        self.health_url = "http://localhost:8000/health"
        self.positions_url = "http://localhost:8000/api/dashboard/open-positions"
        self.emergency_close_url = "http://localhost:8000/emergency/positions/close"
        self.check_interval = 60  # seconds
        self.last_healthy = None
        self.unhealthy_count = 0
        self.max_unhealthy = 3
        
    def check_api_health(self) -> bool:
        """Check if API is responding"""
        try:
            response = requests.get(self.health_url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return data.get('status') == 'ok'
        except Exception as e:
            logger.debug(f"API health check failed: {e}")
        return False
        
    def check_positions_after_eod(self) -> bool:
        """Check if there are open positions after EOD"""
        try:
            now = datetime.now(IST)
            if now.time() < datetime.strptime("15:35", "%H:%M").time():
                return False  # Not EOD yet
                
            response = requests.get(self.positions_url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                positions = data.get('data', {}).get('positions', [])
                if positions and len(positions) > 0:
                    logger.warning(f"🚨 Found {len(positions)} open positions after EOD!")
                    return True
        except Exception as e:
            logger.error(f"Error checking positions after EOD: {e}")
        return False
        
    def emergency_close_positions(self) -> bool:
        """Emergency close all positions"""
        try:
            payload = {
                "reason": "Emergency EOD close - health monitor alert",
                "close_all": True
            }
            headers = {
                "Content-Type": "application/json",
                "x-api-key": "EMERGENCY_KEY_123"
            }
            
            response = requests.post(self.emergency_close_url, json=payload, headers=headers, timeout=10)
            if response.status_code == 200:
                result = response.json()
                logger.info(f"✅ Emergency close successful: {result.get('message')}")
                return True
            else:
                logger.error(f"❌ Emergency close failed: {response.text}")
        except Exception as e:
            logger.error(f"Error in emergency close: {e}")
        return False
        
    def check_trading_activity(self) -> bool:
        """Check if trading loop is active by checking recent logs"""
        try:
            trading_log = project_root / "data" / "logs" / f"trading_{datetime.now(IST).strftime('%Y%m%d')}.log"
            if not trading_log.exists():
                return False
                
            # Check last 10 minutes of logs for trading_loop activity
            ten_min_ago = datetime.now(IST) - timedelta(minutes=10)
            with open(trading_log, 'r') as f:
                for line in reversed(f.readlines()):  # Check from end
                    if 'trading_loop:' in line:
                        # Parse timestamp from log
                        try:
                            timestamp_str = line.split(' | ')[0]
                            log_time = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                            log_time = log_time.replace(tzinfo=IST)
                            if log_time > ten_min_ago:
                                # Check if it's not just "market closed" messages
                                if "Market closed" not in line:
                                    return True
                        except (ValueError, IndexError):
                            continue
                        break  # Found trading_loop entry, stop checking
            return False
            
        except Exception as e:
            logger.error(f"Error checking trading activity: {e}")
            return False
            
    def monitor(self):
        """Main monitoring loop"""
        logger.info("🏥 Health Monitor started")
        
        while True:
            try:
                now = datetime.now(IST)
                api_healthy = self.check_api_health()
                trading_active = self.check_trading_activity()
                
                # Log status
                status = f"API={'✅' if api_healthy else '❌'}, Trading={'✅' if trading_active else '❌'}"
                logger.info(f"[{now.strftime('%H:%M:%S')}] Status: {status}")
                
                # Check for issues
                if not api_healthy:
                    self.unhealthy_count += 1
                    logger.warning(f"⚠️ API unhealthy (count: {self.unhealthy_count}/{self.max_unhealthy})")
                else:
                    self.unhealthy_count = 0
                    self.last_healthy = now
                    
                # Check if we should alert
                if self.unhealthy_count >= self.max_unhealthy:
                    logger.error(f"🚨 CRITICAL: API unhealthy for {self.unhealthy_count} checks!")
                    # TODO: Send notification (email, webhook, etc.)
                    
                # Check for positions after EOD
                if self.check_positions_after_eod():
                    self.emergency_close_positions()
                    
                # Special checks during market hours
                if is_market_hours():
                    if not trading_active and api_healthy:
                        logger.warning("⚠️ API healthy but trading loop inactive during market hours")
                        
                # Sleep until next check
                time.sleep(self.check_interval)
                
            except KeyboardInterrupt:
                logger.info("👋 Health Monitor stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(30)  # Wait before retrying
                
def main():
    """Main entry point"""
    monitor = HealthMonitor()
    
    try:
        # Initial health check
        if monitor.check_api_health():
            logger.info("✅ API is healthy")
        else:
            logger.warning("⚠️ API is not healthy")
            
        # Start monitoring
        monitor.monitor()
        
    except KeyboardInterrupt:
        logger.info("👋 Health Monitor stopped")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
