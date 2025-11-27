#!/usr/bin/env python3
"""
Trading Engine Monitor & Auto-Restart Service
Monitors trading engine health and automatically restarts on crashes
"""

import os
import sys
import time
import signal
import psutil
import subprocess
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any
import requests
import json

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from backend.core.logger import get_logger
from backend.core.timezone_utils import now_ist, is_market_hours, IST

logger = get_logger(__name__)

class TradingEngineMonitor:
    """Monitors and manages trading engine process"""
    
    def __init__(self):
        self.project_root = project_root
        self.log_file = project_root / "data" / "logs" / "monitor.log"
        self.trading_log = project_root / "data" / "logs" / f"trading_{datetime.now(IST).strftime('%Y%m%d')}.log"
        self.pid_file = project_root / "data" / "trading_engine.pid"
        self.health_check_url = "http://localhost:8000/health"
        self.positions_url = "http://localhost:8000/api/dashboard/open-positions"
        self.emergency_close_url = "http://localhost:8000/emergency/positions/close"
        
        # Monitoring settings
        self.check_interval = 30  # seconds
        self.max_restart_attempts = 5
        self.restart_backoff = 60  # seconds
        self.crash_threshold = 3  # crashes within time_window
        self.time_window = timedelta(minutes=30)
        
        # State tracking
        self.restart_attempts = 0
        self.last_restart = None
        self.crash_times = []
        self.trading_process = None
        self.running = True
        
        # Setup logging
        self.setup_logging()
        
    def setup_logging(self):
        """Setup monitor logging"""
        handler = logging.FileHandler(self.log_file)
        handler.setFormatter(logging.Formatter(
            '%(asctime)s | %(levelname)s | %(name)s | %(message)s'
        ))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        
    def is_process_running(self) -> bool:
        """Check if trading engine process is running"""
        try:
            # Check by process name
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    cmdline = ' '.join(proc.info['cmdline'] or [])
                    if 'python' in proc.info['name'].lower() and 'main.py' in cmdline:
                        if 'backend.main' in cmdline or 'main.py' in cmdline:
                            return True
                except (psutil.NoSuchProcess, TypeError):
                    continue
                    
            return False
            
        except Exception as e:
            logger.error(f"Error checking process: {e}")
            return False
            
    def is_api_healthy(self) -> bool:
        """Check if API is responding"""
        try:
            response = requests.get(self.health_check_url, timeout=5)
            return response.status_code == 200 and response.json().get('status') == 'ok'
        except Exception as e:
            logger.debug(f"API health check failed: {e}")
            return False
            
    def is_trading_active(self) -> bool:
        """Check if trading loop is active by checking recent logs"""
        try:
            if not self.trading_log.exists():
                return False
                
            # Check last 5 minutes of logs for trading_loop activity
            five_min_ago = datetime.now(IST) - timedelta(minutes=5)
            with open(self.trading_log, 'r') as f:
                for line in f:
                    if 'trading_loop:' in line and 'Market closed' not in line:
                        # Parse timestamp from log
                        try:
                            timestamp_str = line.split(' | ')[0]
                            log_time = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                            log_time = log_time.replace(tzinfo=IST)
                            if log_time > five_min_ago:
                                return True
                        except (ValueError, IndexError):
                            continue
            return False
            
        except Exception as e:
            logger.error(f"Error checking trading activity: {e}")
            return False
            
    def check_positions_after_eod(self) -> bool:
        """Check if there are open positions after EOD (3:30 PM)"""
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
            return False
            
        except Exception as e:
            logger.error(f"Error checking positions after EOD: {e}")
            return False
            
    def emergency_close_positions(self) -> bool:
        """Emergency close all positions"""
        try:
            payload = {
                "reason": "Emergency EOD close - trading engine crashed",
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
                return False
                
        except Exception as e:
            logger.error(f"Error in emergency close: {e}")
            return False
            
    def start_trading_engine(self) -> bool:
        """Start the trading engine process"""
        try:
            logger.info("🚀 Starting trading engine...")
            
            # Change to project directory
            os.chdir(self.project_root)
            
            # Start trading engine
            cmd = [sys.executable, "-m", "backend.main"]
            with open(self.trading_log, 'a') as log_file:
                self.trading_process = subprocess.Popen(
                    cmd,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    preexec_fn=os.setsid if os.name != 'nt' else None
                )
                
            # Save PID
            with open(self.pid_file, 'w') as f:
                f.write(str(self.trading_process.pid))
                
            # Wait a bit and check if started
            time.sleep(5)
            if self.is_process_running():
                logger.info(f"✅ Trading engine started (PID: {self.trading_process.pid})")
                self.restart_attempts = 0
                return True
            else:
                logger.error("❌ Trading engine failed to start")
                return False
                
        except Exception as e:
            logger.error(f"Error starting trading engine: {e}")
            return False
            
    def stop_trading_engine(self) -> bool:
        """Stop the trading engine gracefully"""
        try:
            if self.pid_file.exists():
                with open(self.pid_file, 'r') as f:
                    pid = int(f.read().strip())
                    
                if psutil.pid_exists(pid):
                    process = psutil.Process(pid)
                    logger.info(f"🛑 Stopping trading engine (PID: {pid})")
                    
                    # Try graceful shutdown first
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except psutil.TimeoutExpired:
                        # Force kill if graceful shutdown fails
                        process.kill()
                        process.wait(timeout=5)
                        
                    logger.info("✅ Trading engine stopped")
                    return True
                    
            # Cleanup PID file
            if self.pid_file.exists():
                self.pid_file.unlink()
                
            return True
            
        except Exception as e:
            logger.error(f"Error stopping trading engine: {e}")
            return False
            
    def handle_crash(self):
        """Handle trading engine crash"""
        now = datetime.now(IST)
        self.crash_times.append(now)
        
        # Clean old crash times
        self.crash_times = [t for t in self.crash_times if now - t < self.time_window]
        
        logger.warning(f"🔴 Trading engine crash detected! Crashes in last {self.time_window}: {len(self.crash_times)}")
        
        # Check for open positions if it's during or after market hours
        if is_market_hours() or datetime.now(IST).time() >= datetime.strptime("15:25", "%H:%M").time():
            self.emergency_close_positions()
            
        # Check if we've exceeded crash threshold
        if len(self.crash_times) >= self.crash_threshold:
            logger.error(f"🚨 CRASH THRESHOLD EXCEEDED: {len(self.crash_times)} crashes in {self.time_window}")
            logger.error("⏸️ SUSPENDING AUTO-RESTART - Manual intervention required")
            self.running = False
            return
            
        # Check restart attempts
        if self.restart_attempts >= self.max_restart_attempts:
            logger.error(f"🚨 MAX RESTART ATTEMPTS EXCEEDED: {self.restart_attempts}")
            self.running = False
            return
            
        # Backoff if restarting too frequently
        if self.last_restart and (now - self.last_restart) < timedelta(seconds=self.restart_backoff):
            wait_time = self.restart_backoff - int((now - self.last_restart).total_seconds())
            logger.info(f"⏳ Waiting {wait_time}s before restart...")
            time.sleep(wait_time)
            
        # Attempt restart
        self.restart_attempts += 1
        self.last_restart = now
        logger.info(f"🔄 Restart attempt {self.restart_attempts}/{self.max_restart_attempts}")
        
        if self.start_trading_engine():
            logger.info("✅ Trading engine restarted successfully")
        else:
            logger.error("❌ Failed to restart trading engine")
            
    def monitor(self):
        """Main monitoring loop"""
        logger.info("👁️ Trading Engine Monitor started")
        
        while self.running:
            try:
                # Check process health
                process_running = self.is_process_running()
                api_healthy = self.is_api_healthy()
                trading_active = self.is_trading_active()
                
                # Log status
                logger.debug(f"Status: Process={process_running}, API={api_healthy}, Trading={trading_active}")
                
                # Determine if crash occurred
                is_crashed = not process_running or not api_healthy
                
                # Special handling during market hours
                if is_market_hours():
                    if not trading_active and process_running:
                        logger.warning("⚠️ Process running but trading loop inactive")
                        is_crashed = True
                        
                # Handle crash
                if is_crashed:
                    self.handle_crash()
                else:
                    # Reset crash counter on successful run
                    if self.restart_attempts > 0:
                        logger.info("✅ Trading engine stable - resetting crash counter")
                        self.restart_attempts = 0
                        self.crash_times.clear()
                        
                # Check for positions after EOD
                if self.check_positions_after_eod():
                    self.emergency_close_positions()
                    
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                
            time.sleep(self.check_interval)
            
        logger.info("👋 Trading Engine Monitor stopped")
        
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum} - shutting down...")
        self.running = False
        self.stop_trading_engine()
        sys.exit(0)
        
def main():
    """Main entry point"""
    monitor = TradingEngineMonitor()
    
    # Setup signal handlers
    signal.signal(signal.SIGTERM, monitor.signal_handler)
    signal.signal(signal.SIGINT, monitor.signal_handler)
    
    try:
        # Start trading engine if not running
        if not monitor.is_process_running():
            monitor.start_trading_engine()
        else:
            logger.info("✅ Trading engine already running")
            
        # Start monitoring
        monitor.monitor()
        
    except KeyboardInterrupt:
        monitor.signal_handler(signal.SIGINT, None)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
