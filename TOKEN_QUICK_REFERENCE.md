# Token Management - Quick Reference Card

## 🎯 At a Glance

**What it does:** Automatically refreshes your Upstox API token before it expires  
**How often:** Checks every 30 minutes, refreshes 1 hour before expiry  
**Your action:** None! System handles everything automatically  

## 📊 Dashboard Indicators

| Indicator | Meaning | Action |
|-----------|---------|--------|
| 🟢 Token: 15.2h | Healthy (>3 hours) | None needed |
| 🟠 Token: 2.5h | Warning (1-3 hours) | System auto-refreshing |
| 🔴 Token: 45m | Critical (<1 hour) | Watch for completion |
| ❌ Token: EXPIRED | Failed auto-refresh | Click to refresh manually |

## 🚨 What To Do If...

### "Token Expiring Soon" (Orange Banner)
✅ **Nothing!** System is handling it  
- Auto-refresh is in progress
- Continue working normally
- Will update automatically

### "Token Expired" (Red Banner)
⚠️ **Manual action needed:**
1. Click "refresh manually" link in banner
2. Browser opens to Upstox login
3. Authorize the application
4. Browser closes automatically
5. Dashboard updates with new token

## 🔧 Quick Commands

### Check Token Status
```bash
curl http://localhost:8000/api/token/status | jq .time_remaining_hours
```

### Force Manual Refresh
```bash
curl -X POST http://localhost:8000/api/token/force-refresh
```

### View System Logs
```bash
docker logs trading_engine | grep -i token
```

### Restart System
```bash
docker-compose restart trading-engine
```

## 📍 Important Locations

| What | Where |
|------|-------|
| Current token | `config/upstox_token.json` |
| Token backup | `~/Algo/upstoxtoken.json` |
| Credentials | `.env` file or `config/config.yaml` |
| Logs | `docker logs trading_engine` |
| Dashboard | http://localhost:8000/dashboard |
| API Status | http://localhost:8000/api/token/status |

## 🕐 Token Lifecycle

```
Hour 0 ──────────────────────────────────────────────────> Hour 24
   │                                              │         │
   │                                              │         │
New Token                                   Auto-Refresh   Expiry
Created                                     Triggered      (if not refreshed)
                                           (at 23 hours)
```

## 💡 Pro Tips

1. **Check Dashboard Daily** - Glance at token countdown in header
2. **Don't Panic on Warnings** - System is designed to handle automatically
3. **Keep Credentials Secure** - Store in `.env`, not in code
4. **Monitor Logs** - Watch for "manual intervention required" messages
5. **Test Occasionally** - Force refresh to ensure OAuth flow works

## 📞 Troubleshooting

| Issue | Solution |
|-------|----------|
| Token not refreshing | Check logs: `docker logs trading_engine \| grep -i token` |
| Dashboard not showing countdown | Hard refresh: Cmd+Shift+R |
| OAuth callback fails | Verify port 5001 not blocked |
| Token shows expired immediately | Check system clock is synchronized |

## ✅ Health Check Checklist

Weekly verification:
- [ ] Token countdown visible in dashboard header
- [ ] Token shows > 20 hours remaining
- [ ] No error banners on dashboard
- [ ] Can access `/api/token/status` endpoint
- [ ] Logs show "Token manager service started"

## 🔐 Security Reminders

- ✅ Never commit `.env` to git
- ✅ Use different credentials for dev/prod
- ✅ Rotate secrets quarterly
- ✅ Monitor logs for unauthorized access
- ✅ Keep system and dependencies updated

## 📚 Documentation

- **Full Guide:** `TOKEN_MANAGEMENT.md`
- **Implementation Details:** `TOKEN_SYSTEM_IMPLEMENTATION.md`
- **User Manual:** `docs/USER_MANUAL.md`

## 🆘 Emergency Contacts

If system completely fails:
1. Run manual script: `python3 upstox_auth_working.py`
2. Restart backend: `docker-compose restart trading-engine`
3. Check all troubleshooting steps above
4. Review full documentation

---

**Remember:** The system is designed to work automatically. You should rarely need to take manual action! 🎉
