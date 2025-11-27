#!/usr/bin/env python3
"""
Trading Engine Startup Manager
Ensures trading engine starts with backend and manages it properly
"""

import os
import sys
import time
import signal
import subprocess
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from backend.core.timezone_utils import now_ist, IST

# Setup logging
log_file = project_root / "data" / "logs" / "startup_manager.log"
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

class StartupManager:
    """Manages trading engine startup with backend"""
    
    def __init__(self):
        self.backend_process = None
        self.trading_process = None
        self.running = True
        
    def start_backend(self) -> bool:
        """Start the backend API server"""
        try:
            logger.info("🚀 Starting backend API server...")
            
            # Change to project directory
            os.chdir(project_root)
            
            # Start backend using uvicorn
            cmd = [
                sys.executable, "-m", "uvicorn",
                "backend.main:app",
                "--host", "0.0.0.0",
                "--port", "8000",
                "--reload"
            ]
            
            self.backend_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )
            
            # Wait for backend to start
            logger.info("⏳ Waiting for backend to start...")
            time.sleep(10)
            
            # Check if backend is responding
            import requests
            try:
                response = requests.get("http://localhost:8000/health", timeout=5)
                if response.status_code == 200:
                    logger.info("✅ Backend API server started successfully")
                    return True
                else:
                    logger.error(f"❌ Backend returned status {response.status_code}")
            except Exception as e:
                logger.error(f"❌ Backend health check failed: {e}")
                
            return False
            
        except Exception as e:
            logger.error(f"Error starting backend: {e}")
            return False
            
    def stop_backend(self):
        """Stop the backend server"""
        if self.backend_process:
            logger.info("🛑 Stopping backend server...")
            self.backend_process.terminate()
            try:
                self.backend_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.backend_process.kill()
                self.backend_process.wait()
            logger.info("✅ Backend server stopped")
            
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum} - shutting down...")
        self.running = False
        self.stop_backend()
        sys.exit(0)
        
    def run(self):
        """Main entry point"""
        logger.info("🎯 Trading Engine Startup Manager")
        
        # Setup signal handlers
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)
        
        try:
            # Start backend
            if not self.start_backend():
                logger.error("❌ Failed to start backend")
                sys.exit(1)
                
            # Keep running and monitor backend
            while self.running:
                try:
                    # Check if backend process is still running
                    if self.backend_process.poll() is not None:
                        logger.warning("⚠️ Backend process died, restarting...")
                        if not self.start_backend():
                            logger.error("❌ Failed to restart backend")
                            break
                            
                    # Check backend health
                    try:
                        import requests
                        response = requests.get("http://localhost:8000/health", timeout=5)
                        if response.status_code != 200:
                            logger.warning("⚠️ Backend unhealthy, checking...")
                    except:
                        logger.warning("⚠️ Backend health check failed")
                        
                    time.sleep(30)  # Check every 30 seconds
                    
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    logger.error(f"Error in main loop: {e}")
                    time.sleep(10)
                    
        finally:
            self.stop_backend()
            logger.info("👋 Startup Manager stopped")

def main():
    """Main entry point"""
    manager = StartupManager()
    manager.run()

if __name__ == "__main__":
    main()
