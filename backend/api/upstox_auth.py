"""
Upstox Authentication API
Handles OAuth flow through the backend
"""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
import requests
import json
import time
import socket
import asyncio
from pathlib import Path
from urllib.parse import quote, unquote
import logging

from backend.core.config import config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/upstox", tags=["upstox-auth"])

def load_credentials():
    """Load Upstox credentials from config"""
    global UPSTOX_CLIENT_ID, UPSTOX_CLIENT_SECRET, UPSTOX_REDIRECT_URI
    
    import os
    
    # Load from config
    UPSTOX_CLIENT_ID = config.get('upstox.client_id', '831e3836-d40e-411d-b659-63aaa41942b6')
    UPSTOX_REDIRECT_URI = config.get('upstox.redirect_uri', 'http://localhost:5001/callback')
    
    # Try environment variable first
    UPSTOX_CLIENT_SECRET = os.environ.get('UPSTOX_CLIENT_SECRET')
    
    # Try config file
    if not UPSTOX_CLIENT_SECRET:
        UPSTOX_CLIENT_SECRET = config.get('upstox.client_secret')
    
    # Try legacy credentials file
    if not UPSTOX_CLIENT_SECRET:
        try:
            cred_file = Path.home() / "Algo" / "upstox_credentials.json"
            if cred_file.exists():
                with open(cred_file) as f:
                    creds = json.load(f)
                    UPSTOX_CLIENT_SECRET = creds.get('client_secret')
        except Exception:
            pass
    
    if not UPSTOX_CLIENT_SECRET:
        logger.warning("⚠️  Upstox client_secret not configured. Set UPSTOX_CLIENT_SECRET environment variable or update config.yaml")
        return False
    
    return True

@router.get("/token/status")
async def get_token_status():
    """Check if Upstox token exists and is valid"""
    try:
        token_file = Path(config.settings.upstox_token_file)
        
        if not token_file.exists():
            return {
                "status": "missing",
                "message": "No token file found",
                "valid": False
            }
        
        with open(token_file) as f:
            token_data = json.load(f)
        
        access_token = token_data.get('access_token')
        created_at = token_data.get('created_at', 0)
        
        if not access_token:
            return {
                "status": "invalid",
                "message": "Token file exists but no access token",
                "valid": False
            }
        
        # Check token age (Upstox tokens expire in 24 hours)
        age_hours = (time.time() - created_at) / 3600
        is_expired = age_hours > 24
        
        # Test token with Upstox API
        try:
            response = requests.get(
                "https://api.upstox.com/v2/user/profile",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=5
            )
            is_valid = response.status_code == 200
        except Exception:
            is_valid = False
        
        return {
            "status": "expired" if is_expired else ("valid" if is_valid else "invalid"),
            "message": f"Token age: {age_hours:.1f} hours" if not is_expired else "Token expired",
            "valid": is_valid and not is_expired,
            "age_hours": round(age_hours, 1),
            "created_at": created_at
        }
        
    except Exception as e:
        logger.error(f"Error checking token status: {e}")
        return {
            "status": "error",
            "message": str(e),
            "valid": False
        }

@router.post("/token/start-auth")
async def start_auth_flow():
    """Start the upstox_auth_working.py script to handle OAuth"""
    try:
        import subprocess
        from pathlib import Path

        # Ensure credentials exist before proceeding
        if not load_credentials():
            raise HTTPException(
                status_code=500,
                detail="Upstox credentials not configured. Set UPSTOX_CLIENT_SECRET env var or update config."
            )

        client_id = config.get('upstox.client_id', '831e3836-d40e-411d-b659-63aaa41942b6')
        redirect_uri = config.get('upstox.redirect_uri', 'http://localhost:5001/callback')

        # Launch local helper only when redirecting back to localhost:5001
        if redirect_uri.startswith('http://localhost:5001'):
            def _is_port_in_use(port: int) -> bool:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.settimeout(0.5)
                    return sock.connect_ex(('127.0.0.1', port)) == 0

            if _is_port_in_use(5001):
                logger.info("Auth server already running on port 5001")
            else:
                script_path = Path(__file__).parent.parent.parent / "upstox_auth_working.py"

                if not script_path.exists():
                    raise HTTPException(
                        status_code=500,
                        detail="upstox_auth_working.py not found"
                    )

                try:
                    helper_proc = subprocess.Popen(
                        ['python3', str(script_path)],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE
                    )
                except FileNotFoundError as exc:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to launch auth helper: {exc}"
                    )

                # Give it time to start
                await asyncio.sleep(2)

                if helper_proc.poll() is not None:
                    stdout, stderr = helper_proc.communicate(timeout=1)
                    error_output = (stderr or stdout or b'').decode('utf-8', errors='ignore').strip()
                    logger.error("Auth helper exited early: %s", error_output)
                    raise HTTPException(
                        status_code=500,
                        detail=f"Auth helper exited: {error_output or 'unknown error'}"
                    )

                if not _is_port_in_use(5001):
                    logger.error("Auth helper failed to bind to port 5001")
                    helper_proc.terminate()
                    raise HTTPException(
                        status_code=500,
                        detail="Auth helper did not start on port 5001"
                    )

                logger.info("✓ Auth server started on port 5001")
        else:
            logger.info("Using FastAPI callback for Upstox auth (no local helper needed)")
        
        # Return the authorization URL for front-end to redirect the user
        encoded_redirect = quote(redirect_uri, safe='')
        auth_url = (
            "https://api.upstox.com/v2/login/authorization/dialog"
            f"?response_type=code&client_id={client_id}&redirect_uri={encoded_redirect}"
        )
        
        return {
            "status": "success",
            "auth_url": auth_url,
            "message": "Authorization server started. Browser will open automatically."
        }
        
    except Exception as e:
        logger.error(f"Error starting auth flow: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/callback", response_class=HTMLResponse)
async def oauth_callback(code: str = None, error: str = None):
    """Handle OAuth callback from Upstox"""
    
    if error:
        return f"""
        <html>
        <head><title>Authorization Failed</title></head>
        <body style="font-family: Arial; padding: 50px; text-align: center;">
            <h1 style="color: red;">❌ Authorization Failed</h1>
            <p><strong>Error:</strong> {error}</p>
            <p>Please close this window and try again.</p>
        </body>
        </html>
        """
    
    if not code:
        return """
        <html>
        <head><title>Error</title></head>
        <body style="font-family: Arial; padding: 50px; text-align: center;">
            <h1 style="color: red;">❌ No Authorization Code</h1>
            <p>The authorization code was not received.</p>
        </body>
        </html>
        """
    
    # Load credentials
    if not load_credentials():
        return """
        <html>
        <head><title>Configuration Error</title></head>
        <body style="font-family: Arial; padding: 50px; text-align: center;">
            <h1 style="color: red;">❌ Configuration Error</h1>
            <p>Client secret not configured. Please set UPSTOX_CLIENT_SECRET environment variable.</p>
            <p>Or create ~/Algo/upstox_credentials.json with your credentials.</p>
        </body>
        </html>
        """
    
    try:
        # Exchange authorization code for access token
        token_url = "https://api.upstox.com/v2/login/authorization/token"
        headers = {
            "accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        data = {
            "code": code,
            "client_id": UPSTOX_CLIENT_ID,
            "client_secret": UPSTOX_CLIENT_SECRET,
            "redirect_uri": UPSTOX_REDIRECT_URI,
            "grant_type": "authorization_code"
        }
        
        logger.info("Exchanging authorization code for access token...")
        response = requests.post(token_url, headers=headers, data=data, timeout=10)
        
        if response.status_code != 200:
            error_msg = response.json().get('errors', [{}])[0].get('message', 'Unknown error')
            return f"""
            <html>
            <head><title>Token Exchange Failed</title></head>
            <body style="font-family: Arial; padding: 50px; text-align: center;">
                <h1 style="color: red;">❌ Token Exchange Failed</h1>
                <p><strong>Error:</strong> {error_msg}</p>
                <p>Status Code: {response.status_code}</p>
            </body>
            </html>
            """
        
        token_data = response.json()
        token_data['created_at'] = int(time.time())
        
        # Save token to file
        token_file = Path(config.settings.upstox_token_file)
        token_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(token_file, 'w') as f:
            json.dump(token_data, f, indent=2)
        
        logger.info(f"✅ Token saved to {token_file}")
        
        # Also save backup to ~/Algo
        backup_file = Path.home() / "Algo" / "upstoxtoken.json"
        backup_file.parent.mkdir(parents=True, exist_ok=True)
        with open(backup_file, 'w') as f:
            json.dump(token_data, f, indent=2)
        
        logger.info(f"✅ Backup saved to {backup_file}")
        
        return """
        <html>
        <head>
            <title>Authorization Successful</title>
            <script>
                setTimeout(function() {
                    window.close();
                }, 3000);
            </script>
        </head>
        <body style="font-family: Arial; padding: 50px; text-align: center;">
            <h1 style="color: green;">✅ Authorization Successful!</h1>
            <p>Access token has been saved successfully.</p>
            <p>This window will close automatically in 3 seconds...</p>
            <p style="margin-top: 30px; color: #666;">
                <small>If it doesn't close, you can close it manually.</small>
            </p>
        </body>
        </html>
        """
        
    except Exception as e:
        logger.error(f"Error in OAuth callback: {e}")
        return f"""
        <html>
        <head><title>Error</title></head>
        <body style="font-family: Arial; padding: 50px; text-align: center;">
            <h1 style="color: red;">❌ Error Processing Authorization</h1>
            <p><strong>Error:</strong> {str(e)}</p>
        </body>
        </html>
        """

@router.post("/token/refresh")
async def refresh_token():
    """Trigger token refresh (redirect to auth flow)"""
    return await start_auth_flow()


async def trigger_oauth_flow() -> bool:
    """
    Programmatically trigger OAuth flow for automatic token refresh
    Used by the token manager service
    """
    try:
        result = await start_auth_flow()
        return result.get('status') == 'success'
    except Exception as e:
        logger.error(f"Failed to trigger OAuth flow: {e}")
        return False
