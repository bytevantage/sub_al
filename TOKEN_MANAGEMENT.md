# Automated Token Management System

## Overview

Professional automated token management system that handles Upstox API token lifecycle:
- 🔄 **Automatic token refresh** before expiry
- ⏰ **Continuous monitoring** with 30-minute check intervals
- 🎯 **Proactive refresh** 1 hour before expiration
- 🔔 **Dashboard notifications** with countdown timer
- 🛡️ **Graceful fallback** to manual OAuth when auto-refresh fails
- 🔐 **Secure credential management** via environment variables

## Architecture

### Components

1. **Token Manager Service** (`backend/services/token_manager.py`)
   - Background service running throughout application lifecycle
   - Monitors token expiry every 30 minutes
   - Attempts automatic refresh 1 hour before expiration
   - Validates tokens with Upstox API
   - Retries up to 3 times on failure

2. **Token Status API** (`backend/api/token_status.py`)
   - `/api/token/status` - Real-time token health information
   - `/api/token/force-refresh` - Manual refresh trigger
   - Returns countdown, expiry time, validation status

3. **Dashboard Integration** (`frontend/dashboard/`)
   - Live token countdown in header
   - Color-coded status (Green >3h, Orange <3h, Red <1h)
   - Automatic notifications at critical thresholds
   - One-click manual refresh option

4. **OAuth Handler** (`backend/api/upstox_auth.py`)
   - Professional OAuth flow implementation
   - Automatic callback handling
   - Token storage with backup
   - Browser auto-open and auto-close

## Configuration

### Environment Variables

Create a `.env` file with your credentials:

```bash
# Upstox API Credentials
UPSTOX_CLIENT_ID=your_client_id_here
UPSTOX_CLIENT_SECRET=your_client_secret_here
UPSTOX_REDIRECT_URI=http://localhost:5001/callback
```

**Security Best Practices:**
- ✅ Never commit `.env` to version control
- ✅ Use `.env.example` as template
- ✅ Rotate secrets regularly
- ✅ Use different credentials for dev/prod

### Alternative: Config File

Update `config/config.yaml`:

```yaml
upstox:
  client_id: "your_client_id_here"
  client_secret: "your_client_secret_here"
  redirect_uri: "http://localhost:5001/callback"
```

## How It Works

### Automatic Token Refresh Flow

```
┌─────────────────────────────────────────┐
│  1. Token Manager starts with system    │
│     Checks token status every 30 min    │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  2. Detects token expires in <1 hour    │
│     Triggers automatic refresh          │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  3. Launches OAuth flow                 │
│     Opens browser for authentication    │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  4. User authorizes (if needed)         │
│     Callback receives new token         │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  5. Token saved to file with backup     │
│     Backend reloads token automatically │
└─────────────────────────────────────────┘
```

### Dashboard Notification Flow

| Time Remaining | Status | Action |
|----------------|--------|--------|
| >3 hours | 🟢 Green | Silent monitoring |
| 1-3 hours | 🟠 Orange | Show countdown |
| <1 hour | 🔴 Red | Warning banner + auto-refresh |
| Expired | ❌ Red | Error banner + manual action required |

## Usage

### For End Users

1. **Normal Operation**
   - System monitors token automatically
   - No action needed if auto-refresh succeeds
   - Dashboard shows countdown in header

2. **When Token Expires Soon**
   - Orange countdown appears in header
   - System attempts auto-refresh
   - Continue working normally

3. **If Auto-Refresh Fails**
   - Red "Token Expired" notification appears
   - Click "refresh manually" link
   - Complete OAuth in browser (auto-opens)
   - Token updates automatically

### For Developers

**Start the system:**
```bash
docker-compose up -d
```

**Check token status:**
```bash
curl http://localhost:8000/api/token/status | jq
```

**Force manual refresh:**
```bash
curl -X POST http://localhost:8000/api/token/force-refresh
```

**View token manager logs:**
```bash
docker logs trading_engine | grep "Token manager"
```

## API Reference

### GET `/api/token/status`

Returns comprehensive token status:

```json
{
  "valid": true,
  "time_remaining_seconds": 75600,
  "time_remaining_hours": 21.0,
  "expiry_time": "2024-11-18T10:00:00",
  "needs_refresh": false,
  "message": "Token valid",
  "api_validated": true
}
```

### POST `/api/token/force-refresh`

Manually trigger token refresh:

```json
{
  "status": "success",
  "message": "Token refresh initiated successfully"
}
```

## Monitoring & Alerts

### Log Messages

**Healthy Operation:**
```
✓ Token manager service started
✓ Token valid, expires in 18.3 hours
✓ Token refresh successful
```

**Warning Signs:**
```
⚠️ Token expires in 0:45:00, attempting refresh...
⚠️ Refresh attempt 1/3 failed
```

**Critical Issues:**
```
❌ Token has already expired!
❌ All refresh attempts failed, manual intervention required
```

### Dashboard Indicators

1. **Token Status Badge** (top right)
   - Shows time remaining
   - Color changes based on urgency

2. **Notification Banners**
   - Auto-appear at critical thresholds
   - Provide direct action links

3. **Settings Modal**
   - Shows detailed token information
   - Manual refresh button

## Troubleshooting

### Issue: Token not refreshing automatically

**Symptoms:** Token expires but system doesn't refresh
**Solution:**
1. Check logs: `docker logs trading_engine --tail 50 | grep -i token`
2. Verify credentials in `.env` or `config.yaml`
3. Ensure port 5001 is not blocked
4. Try manual refresh via dashboard

### Issue: OAuth callback fails

**Symptoms:** Browser opens but shows error page
**Solution:**
1. Verify redirect URI matches exactly: `http://localhost:5001/callback`
2. Check client_id and client_secret are correct
3. Ensure no other service is using port 5001
4. Check firewall/antivirus settings

### Issue: Dashboard shows "Token Expired" immediately

**Symptoms:** New token shows as expired
**Solution:**
1. Check system clock is synchronized
2. Verify token file has correct timestamp
3. Run: `cat config/upstox_token.json | jq .created_at`
4. Compare with: `date +%s`

## Comparison: Old vs New System

| Feature | Old Manual Script | New Automated System |
|---------|-------------------|----------------------|
| Refresh Method | Run script daily | Automatic background service |
| User Action | Manual every 24h | None (unless failure) |
| Monitoring | None | Continuous with logs |
| Warnings | None | Dashboard + notifications |
| Retry Logic | Single attempt | 3 attempts with backoff |
| API Validation | No | Yes, every check |
| Dashboard Integration | Separate process | Fully integrated |
| Production Ready | ❌ No | ✅ Yes |

## Best Practices

### For Production Deployment

1. **Use Environment Variables**
   ```bash
   export UPSTOX_CLIENT_SECRET="your_secret"
   docker-compose up -d
   ```

2. **Enable Logging**
   ```yaml
   # config.yaml
   logging:
     level: INFO
     file: logs/token_manager.log
   ```

3. **Set Up Monitoring**
   - Monitor token manager logs
   - Alert on "manual intervention required"
   - Track refresh success rate

4. **Test Failure Scenarios**
   - Simulate expired token
   - Test manual refresh flow
   - Verify notification system

### Security Checklist

- [ ] Client secret in environment variables (not hardcoded)
- [ ] `.env` file in `.gitignore`
- [ ] Token files have restricted permissions (600)
- [ ] OAuth callback URL uses HTTPS in production
- [ ] Credentials rotated regularly
- [ ] Backup token files encrypted at rest

## Migration Guide

### From Manual Script to Automated System

1. **Backup current token:**
   ```bash
   cp config/upstox_token.json config/upstox_token.backup.json
   ```

2. **Set environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

3. **Restart system:**
   ```bash
   docker-compose down
   docker-compose up -d
   ```

4. **Verify token manager started:**
   ```bash
   docker logs trading_engine | grep "Token manager service started"
   ```

5. **Check dashboard:**
   - Open http://localhost:8000/dashboard
   - Look for token countdown in header

## Support

For issues or questions:
1. Check logs: `docker logs trading_engine`
2. Review troubleshooting section above
3. Test with manual refresh first
4. Verify credentials are correct

## Future Enhancements

Planned improvements:
- [ ] Email/SMS alerts for critical token issues
- [ ] Multi-user token management
- [ ] Token usage analytics
- [ ] Prometheus metrics for token health
- [ ] Automated credential rotation
- [ ] Support for multiple broker APIs
