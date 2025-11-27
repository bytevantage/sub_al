# 🔧 Upstox Token Fetch - Troubleshooting Guide

## ❌ Error: "Check your 'client_id' and 'redirect_uri'"

This error means the credentials in the script don't match what's registered in your Upstox developer account.

---

## 🎯 **SOLUTION: Use the Interactive Token Fetcher**

### **Step 1: Get Your Correct Upstox Credentials**

1. **Go to Upstox Developer Portal**
   ```
   https://api.upstox.com/
   ```

2. **Login** with your Upstox trading account

3. **Navigate to**: Dashboard → **My Apps**

4. **Click on your app** (or create a new one if you don't have one)

5. **Copy these 3 values**:
   - **App ID** (also called Client ID) - Example: `a1b2c3d4-e5f6-7890-abcd-ef1234567890`
   - **App Secret** (also called Client Secret) - Example: `abc123xyz`
   - **Redirect URI** - Example: `http://localhost:5000/callback`

**⚠️ IMPORTANT**: The Redirect URI must match **EXACTLY** (including http vs https, localhost vs 127.0.0.1, port number, etc.)

---

### **Step 2: Run the Interactive Token Fetcher**

```bash
cd /Users/srbhandary/Documents/Projects/srb-algo
python3 fetch_upstox_token.py
```

The script will:
1. ✅ Ask you to enter your credentials interactively
2. ✅ Show you what it's using (so you can verify)
3. ✅ Save credentials for future use
4. ✅ Open browser with correct authorization URL
5. ✅ Handle the callback and save token

**Example Session:**
```
═══════════════════════════════════════════════════════════
🔐 Upstox Token Fetcher - Interactive Setup
═══════════════════════════════════════════════════════════

First, get your credentials from Upstox Developer Portal:
👉 https://api.upstox.com/

Go to: My Apps → [Your App Name]

─────────────────────────────────────────────────────────────
Enter your Client ID (App ID): a1b2c3d4-e5f6-7890-abcd-ef1234567890
─────────────────────────────────────────────────────────────
Enter your Client Secret (App Secret): abc123xyz
─────────────────────────────────────────────────────────────

📋 Common Redirect URIs:
  1. http://localhost:5000/callback
  2. http://127.0.0.1:5000/callback
  3. Custom (enter your own)

Select option (1/2/3) or press Enter for option 1: 1

═══════════════════════════════════════════════════════════
✅ Configuration Summary:
═══════════════════════════════════════════════════════════
Client ID:     a1b2c3d4-e5f6-7890-abcd-ef1234567890
Client Secret: abc1...3xyz
Redirect URI:  http://localhost:5000/callback

⚠️  IMPORTANT: Verify that your Redirect URI in Upstox portal
   EXACTLY matches: http://localhost:5000/callback

Continue with these settings? (y/n): y
```

---

### **Step 3: Complete Authorization in Browser**

After you confirm, the script will:
1. **Open your browser** to Upstox login page
2. You'll see the Upstox authorization page (not an error!)
3. **Enter your mobile number**
4. **Enter the OTP** sent to your phone
5. **Click "Authorize"**
6. Browser redirects back to localhost
7. You'll see: **"✅ Authorization Successful!"**
8. Token is automatically saved to `~/Algo/upstoxtoken.json`

**What you should see in browser:**
```
✅ Authorization Successful!

Access token has been saved to:
~/Algo/upstoxtoken.json

Token: eyJ0eXAiOiJKV1QiLCJ...

✅ You can close this tab now.
The trading system can now use this token.
```

---

## 🔍 **Common Issues and Solutions**

### **Issue 1: "Redirect URI mismatch"**

**Problem**: Your app's redirect URI doesn't match what you entered

**Solution**:
1. Go back to Upstox portal → My Apps → [Your App]
2. Check the **Redirect URI** field
3. Copy it EXACTLY (including trailing slash if present)
4. Use option 3 (custom) when running the script
5. Paste the exact URI

**Examples of correct formats:**
```
✅ http://localhost:5000/callback
✅ http://127.0.0.1:5000/callback
✅ https://yourdomain.com/callback
❌ http://localhost:5000/callback/ (extra slash)
❌ https://localhost:5000/callback (https vs http)
```

### **Issue 2: "Invalid Client ID"**

**Problem**: You copied the wrong value or included extra characters

**Solution**:
1. Go to Upstox portal → My Apps → [Your App]
2. Look for **App ID** or **Client ID**
3. Copy it carefully (no spaces, no quotes)
4. It should look like: `831e3836-d40e-411d-b659-63aaa41942b6`

### **Issue 3: Port 5000 already in use**

**Problem**: Another service is using port 5000

**Solution A** - Stop other service:
```bash
# Find process using port 5000
lsof -i :5000

# Kill it
kill $(lsof -t -i:5000)
```

**Solution B** - Use different port:
1. Edit `fetch_upstox_token.py`
2. Change `app.run(port=5000)` to `app.run(port=5001)`
3. Update Redirect URI in Upstox portal to: `http://localhost:5001/callback`
4. Run the script again

### **Issue 4: Browser doesn't open**

**Problem**: Script can't open browser automatically

**Solution**:
1. The script will print the authorization URL
2. Copy it manually
3. Paste into your browser
4. Example URL:
   ```
   https://api.upstox.com/v2/login/authorization/dialog?response_type=code&client_id=YOUR_CLIENT_ID&redirect_uri=http://localhost:5000/callback
   ```

### **Issue 5: Token file not created**

**Problem**: Authorization succeeded but no file saved

**Solution**:
```bash
# Check if directory exists
ls -la ~/Algo/

# If not, create it
mkdir -p ~/Algo

# Run token fetcher again
python3 fetch_upstox_token.py
```

---

## 📋 **Verification Checklist**

After getting your token, verify everything:

```bash
# 1. Check token file exists
ls -la ~/Algo/upstoxtoken.json

# 2. View token contents (should be valid JSON)
cat ~/Algo/upstoxtoken.json | python3 -m json.tool

# 3. Check token age (should be less than 24 hours)
python3 -c "
import json, time
with open('$HOME/Algo/upstoxtoken.json') as f:
    data = json.load(f)
    age = (time.time() - data['created_at']) / 3600
    print(f'Token age: {age:.1f} hours')
    print('Status: Valid' if age < 24 else 'Status: Expired')
"

# 4. Test token with Upstox API
curl -H "Authorization: Bearer $(python3 -c 'import json; print(json.load(open("'$HOME/Algo/upstoxtoken.json'"))["access_token"])')" \
  https://api.upstox.com/v2/user/profile
```

If all checks pass, you should see:
```json
{
  "status": "success",
  "data": {
    "email": "your-email@example.com",
    "user_name": "Your Name",
    ...
  }
}
```

---

## 🚀 **After Token is Fetched**

Once you have a valid token:

```bash
# 1. Verify token is valid
./check_status.sh

# 2. Launch the trading system
./launch_system.sh

# 3. Access dashboard
open http://localhost:3000
```

---

## 🔄 **Future Token Refreshes**

Upstox tokens expire after 24 hours. To fetch a new token:

**Quick Refresh** (uses saved credentials):
```bash
python3 fetch_upstox_token.py
# Will use saved credentials, just authorize in browser
```

**Manual Refresh** (if credentials changed):
```bash
# Delete saved credentials
rm ~/Algo/upstox_credentials.json

# Run fetcher (will ask for credentials again)
python3 fetch_upstox_token.py
```

---

## 📞 **Still Having Issues?**

### Debug Steps:

1. **Check Upstox API Status**
   ```
   https://status.upstox.com/
   ```

2. **View detailed error logs**
   ```bash
   tail -f /tmp/auth_output.log
   ```

3. **Test with curl**
   ```bash
   curl "https://api.upstox.com/v2/login/authorization/dialog?response_type=code&client_id=YOUR_CLIENT_ID&redirect_uri=http://localhost:5000/callback"
   ```

4. **Verify app is active in Upstox**
   - Go to https://api.upstox.com/
   - Check if your app status is "Active"
   - Ensure you're using the production API credentials (not sandbox)

---

## 📚 **Additional Resources**

- **Upstox API Docs**: https://upstox.com/developer/api-documentation/
- **Authorization Guide**: https://upstox.com/developer/api-documentation/authorization-token
- **Upstox Support**: https://support.upstox.com/

---

**Ready to try again?**

```bash
python3 fetch_upstox_token.py
```

This time you'll be asked to enter the correct credentials interactively! 🚀
