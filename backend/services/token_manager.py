"""
Automated Upstox Token Management Service

Handles automatic token refresh, validation, and expiry monitoring.
Runs as a background service and attempts to refresh tokens before they expire.
"""
import os
import json
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict
from pathlib import Path
import httpx

logger = logging.getLogger(__name__)


class TokenManager:
    """Manages Upstox API token lifecycle with automatic refresh"""
    
    def __init__(self, config_path: str = "config/upstox_token.json"):
        self.config_path = Path(config_path)
        self.token_data: Optional[Dict] = None
        self.refresh_task: Optional[asyncio.Task] = None
        self.is_running = False
        
        # Token refresh settings
        self.REFRESH_BEFORE_EXPIRY = timedelta(hours=1)  # Refresh 1 hour before expiry
        self.CHECK_INTERVAL = timedelta(minutes=15)  # Check every 15 minutes (reduced from 30)
        self.MAX_RETRY_ATTEMPTS = 3
        
    async def start(self):
        """Start the token management service"""
        if self.is_running:
            logger.warning("Token manager already running")
            return
            
        self.is_running = True
        self.refresh_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Token manager service started")
        
    async def stop(self):
        """Stop the token management service"""
        self.is_running = False
        if self.refresh_task:
            self.refresh_task.cancel()
            try:
                await self.refresh_task
            except asyncio.CancelledError:
                pass
        logger.info("Token manager service stopped")
        
    def load_token(self) -> Optional[Dict]:
        """Load token from file"""
        try:
            if not self.config_path.exists():
                logger.error(f"Token file not found: {self.config_path}")
                return None
                
            with open(self.config_path, 'r') as f:
                self.token_data = json.load(f)
                
            return self.token_data
        except Exception as e:
            logger.error(f"Failed to load token: {e}")
            return None
            
    def save_token(self, token_data: Dict):
        """Save token to file"""
        try:
            # Create backup
            if self.config_path.exists():
                backup_path = self.config_path.with_suffix('.backup.json')
                with open(self.config_path, 'r') as f:
                    with open(backup_path, 'w') as backup:
                        backup.write(f.read())
                        
            # Save new token
            with open(self.config_path, 'w') as f:
                json.dump(token_data, f, indent=2)
                
            self.token_data = token_data
            logger.info("Token saved successfully")
            
            # Also save to backup location
            backup_location = Path.home() / "Algo" / "upstoxtoken.json"
            backup_location.parent.mkdir(parents=True, exist_ok=True)
            with open(backup_location, 'w') as f:
                json.dump(token_data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to save token: {e}")
            raise
            
    def get_token_expiry(self) -> Optional[datetime]:
        """Get token expiration time"""
        if not self.token_data:
            return None
            
        try:
            # First, try to extract expiry from the JWT token itself
            access_token = self.token_data.get('access_token', '')
            if access_token:
                try:
                    import base64
                    import json
                    # JWT format: header.payload.signature
                    parts = access_token.split('.')
                    if len(parts) >= 2:
                        # Decode payload (add padding if needed)
                        payload = parts[1]
                        payload += '=' * (4 - len(payload) % 4)
                        decoded = base64.urlsafe_b64decode(payload)
                        payload_data = json.loads(decoded)
                        
                        # Upstox JWT has 'exp' field (Unix timestamp)
                        if 'exp' in payload_data:
                            return datetime.fromtimestamp(payload_data['exp'])
                except Exception as e:
                    logger.debug(f"Could not decode JWT expiry: {e}")
            
            # Fallback: Upstox tokens expire at 3:30 AM next day, not 24 hours
            created_at = self.token_data.get('created_at')
            if not created_at:
                return None
            
            created_dt = datetime.fromtimestamp(created_at)
            
            # Token expires at 3:30 AM the next trading day
            # If created before 3:30 AM, expires same day at 3:30 AM
            # If created after 3:30 AM, expires next day at 3:30 AM
            expiry_time = created_dt.replace(hour=3, minute=30, second=0, microsecond=0)
            
            if created_dt.time() >= expiry_time.time():
                # Created after 3:30 AM, expires next day
                expiry_time += timedelta(days=1)
            
            return expiry_time
        except Exception as e:
            logger.error(f"Failed to calculate token expiry: {e}")
            return None
            
    def time_until_expiry(self) -> Optional[timedelta]:
        """Get time remaining until token expires"""
        expiry = self.get_token_expiry()
        if not expiry:
            return None
            
        return expiry - datetime.now()
        
    def is_token_valid(self) -> bool:
        """Check if current token is still valid"""
        time_left = self.time_until_expiry()
        if not time_left:
            return False
            
        return time_left.total_seconds() > 0
        
    def needs_refresh(self) -> bool:
        """Check if token needs to be refreshed"""
        time_left = self.time_until_expiry()
        if not time_left:
            return True
            
        return time_left < self.REFRESH_BEFORE_EXPIRY
        
    def validate_token_locally(self) -> bool:
        """Validate token by checking expiry time locally (no API calls)"""
        if not self.token_data or 'access_token' not in self.token_data:
            logger.debug("No token data found")
            return False
            
        # Check token expiry locally
        time_left = self.time_until_expiry()
        if not time_left:
            logger.debug("Could not determine token expiry")
            return False
            
        if time_left.total_seconds() <= 0:
            logger.warning("Token has expired locally")
            return False
            
        # Token is valid based on expiry time
        logger.debug(f"Token valid locally, expires in {time_left.total_seconds() / 3600:.1f} hours")
        return True
            
    async def refresh_token(self) -> bool:
        """
        Attempt to refresh the token automatically
        
        NOTE: Upstox API v2 doesn't provide refresh_token mechanism.
        Tokens must be re-authorized through OAuth flow.
        This method will trigger the OAuth flow programmatically.
        """
        logger.info("Attempting automatic token refresh...")
        
        try:
            from backend.core.config import Settings
            from backend.api.upstox_auth import trigger_oauth_flow
            
            # Trigger OAuth flow (this will require user interaction)
            success = await trigger_oauth_flow()
            
            if success:
                # Reload token after refresh
                self.load_token()
                logger.info("Token refresh successful")
                return True
            else:
                logger.error("Token refresh failed")
                return False
                
        except Exception as e:
            logger.error(f"Token refresh error: {e}")
            return False
            
    async def _monitoring_loop(self):
        """Background loop that monitors token status"""
        logger.info("Token monitoring loop started")
        
        while self.is_running:
            try:
                # Load current token
                self.load_token()
                
                if not self.token_data:
                    logger.warning("No token found, waiting for manual authentication")
                    await asyncio.sleep(self.CHECK_INTERVAL.total_seconds())
                    continue
                    
                # Check if token needs refresh
                if self.needs_refresh():
                    time_left = self.time_until_expiry()
                    if time_left and time_left.total_seconds() > 0:
                        logger.warning(
                            f"Token expires in {time_left}, attempting refresh..."
                        )
                    else:
                        logger.error("Token has already expired!")
                        
                    # Attempt refresh with retries
                    for attempt in range(self.MAX_RETRY_ATTEMPTS):
                        if await self.refresh_token():
                            break
                        else:
                            logger.warning(
                                f"Refresh attempt {attempt + 1}/{self.MAX_RETRY_ATTEMPTS} failed"
                            )
                            await asyncio.sleep(60)  # Wait 1 minute before retry
                    else:
                        logger.error("All refresh attempts failed, manual intervention required")
                        
                else:
                    time_left = self.time_until_expiry()
                    if time_left:
                        logger.info(
                            f"Token valid, expires in {time_left.total_seconds() / 3600:.1f} hours"
                        )
                        
                # Wait before next check
                await asyncio.sleep(self.CHECK_INTERVAL.total_seconds())
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(60)  # Wait before retry
                
        logger.info("Token monitoring loop stopped")
        
    def get_status(self) -> Dict:
        """Get current token status for API/dashboard"""
        if not self.token_data:
            return {
                "valid": False,
                "message": "No token found",
                "requires_auth": True
            }
            
        time_left = self.time_until_expiry()
        expiry = self.get_token_expiry()
        
        if not time_left or time_left.total_seconds() <= 0:
            return {
                "valid": False,
                "expired": True,
                "expiry_time": expiry.isoformat() if expiry else None,
                "message": "Token expired",
                "requires_auth": True
            }
            
        return {
            "valid": True,
            "time_remaining_seconds": int(time_left.total_seconds()),
            "time_remaining_hours": round(time_left.total_seconds() / 3600, 1),
            "expiry_time": expiry.isoformat() if expiry else None,
            "needs_refresh": self.needs_refresh(),
            "message": "Token valid"
        }


# Global singleton instance
_token_manager: Optional[TokenManager] = None


def get_token_manager() -> TokenManager:
    """Get the global token manager instance"""
    global _token_manager
    if _token_manager is None:
        _token_manager = TokenManager()
    return _token_manager
