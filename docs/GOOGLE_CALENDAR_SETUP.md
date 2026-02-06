# Google Calendar Integration Setup Guide

Complete guide for setting up Google Calendar integration in FrontDesk AI. This allows your AI receptionist to check availability, book appointments, reschedule, and cancel appointments on Google Calendar.

## Table of Contents

- [Overview](#overview)
- [Authentication Methods](#authentication-methods)
- [Method 1: OAuth 2.0 (Recommended)](#method-1-oauth-20-recommended)
- [Method 2: Service Account Upload (BYOK)](#method-2-service-account-upload-byok)
- [Method 3: Global Service Account (Fallback)](#method-3-global-service-account-fallback)
- [Testing Your Integration](#testing-your-integration)
- [Troubleshooting](#troubleshooting)
- [Security Best Practices](#security-best-practices)

---

## Overview

FrontDesk AI integrates with Google Calendar to provide appointment scheduling capabilities. The system supports three authentication methods, allowing you to choose the best option for your needs.

### Why Calendar Integration?

- ✅ **Check Availability** - Real-time calendar slot checking
- ✅ **Book Appointments** - Create calendar events from phone calls
- ✅ **Reschedule** - Move existing appointments
- ✅ **Cancel** - Remove appointments with confirmation
- ✅ **View Appointments** - List upcoming bookings for callers

---

## Authentication Methods

FrontDesk AI supports three ways to connect Google Calendar:

| Method | Best For | Setup Time | Security | Per-Client |
|--------|----------|------------|----------|------------|
| **OAuth 2.0** | Most users | 2 minutes | ⭐⭐⭐⭐⭐ | ✅ Yes |
| **Service Account Upload** | Advanced users | 5 minutes | ⭐⭐⭐⭐ | ✅ Yes |
| **Global Service Account** | Testing/single-tenant | 10 minutes | ⭐⭐⭐ | ❌ No |

### Credential Priority

If you configure multiple methods, FrontDesk AI uses this priority:

```
1. Client OAuth credentials (if authorized)
   ↓
2. Client Service Account (if uploaded)
   ↓
3. Global Service Account (environment variable fallback)
```

---

## Method 1: OAuth 2.0 (Recommended)

**Best for:** Most users who want quick, secure calendar access.

**Advantages:**
- ✅ One-click authorization
- ✅ No JSON files to manage
- ✅ Revocable at any time
- ✅ Automatic token refresh
- ✅ User-friendly

**Disadvantages:**
- ⚠️ Requires Google Cloud OAuth setup (one-time)
- ⚠️ Users must authorize each client separately

### Prerequisites

- Google Cloud Project
- OAuth 2.0 credentials configured

### Step 1: Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click project dropdown → **New Project**
3. Name: "FrontDesk AI" (or your preferred name)
4. Click **Create**
5. Select the new project from the dropdown

### Step 2: Enable Google Calendar API

1. Navigate to **APIs & Services → Library**
2. Search for "Google Calendar API"
3. Click **Enable**

### Step 3: Configure OAuth Consent Screen

1. Go to **APIs & Services → OAuth consent screen**
2. Select **External** (unless you have a Google Workspace)
3. Click **Create**

**App Information:**
- **App name:** FrontDesk AI
- **User support email:** Your email
- **Developer contact:** Your email

4. Click **Save and Continue**

**Scopes:**
5. Click **Add or Remove Scopes**
6. Search for "Google Calendar API"
7. Select:
   - `.../auth/calendar` (See, edit, share, and permanently delete calendars)
   - `.../auth/calendar.events` (View and edit events)
8. Click **Update** → **Save and Continue**

**Test Users:**
9. Click **Add Users**
10. Add your email address
11. Click **Save and Continue**
12. Click **Back to Dashboard**

### Step 4: Create OAuth Credentials

1. Navigate to **APIs & Services → Credentials**
2. Click **Create Credentials → OAuth client ID**
3. Application type: **Web application**
4. Name: "FrontDesk AI Web"

**Authorized redirect URIs:**
5. Click **Add URI**
6. Add: `http://localhost:8000/api/calendar/oauth/callback` (for development)
7. Add: `https://yourdomain.com/api/calendar/oauth/callback` (for production)
8. Click **Create**

9. **Copy the Client ID and Client Secret** (you'll need these)

### Step 5: Configure FrontDesk AI

Add to your `.env` file:

```bash
GOOGLE_OAUTH_CLIENT_ID="your-client-id.apps.googleusercontent.com"
GOOGLE_OAUTH_CLIENT_SECRET="your-client-secret"
CALENDAR_CREDENTIALS_ENCRYPTION_KEY="generate-with-openssl-rand-hex-32"
BASE_URL="http://localhost:8000"  # or your production URL
```

**Generate encryption key:**
```bash
openssl rand -hex 32
```

### Step 6: Authorize Calendar Access

1. Log in to FrontDesk AI dashboard
2. Navigate to your client
3. Click **Edit**
4. In the **Calendar Authentication** section:
   - Click **Authorize Google Calendar**
5. A popup opens with Google authorization
6. Select your Google account
7. Click **Allow**
8. Popup closes automatically
9. Status shows **OAuth Authenticated** ✅

### Step 7: Set Calendar ID

1. Go to [Google Calendar](https://calendar.google.com/)
2. Find your calendar → Three dots → **Settings and sharing**
3. Scroll to **Integrate calendar**
4. Copy the **Calendar ID**
5. Paste into the "Calendar ID" field in FrontDesk AI
6. Click **Save**

**Done!** Your client can now access the calendar.

---

## Method 2: Service Account Upload (BYOK)

**Best for:** Advanced users who want full control over credentials.

**Advantages:**
- ✅ No OAuth flow required
- ✅ Full control over credentials
- ✅ Works in restricted environments
- ✅ Can use existing service accounts

**Disadvantages:**
- ⚠️ Must create and download JSON key
- ⚠️ Must manually share calendar
- ⚠️ More complex setup

### Step 1: Create Service Account

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select or create a project
3. Navigate to **APIs & Services → Credentials**
4. Click **Create Credentials → Service Account**

**Service Account Details:**
- **Name:** `frontdesk-calendar-{client-name}`
- **Description:** "Calendar access for {client-name}"

5. Click **Create and Continue**
6. Skip optional steps → **Done**

### Step 2: Download Service Account Key

1. In Credentials page, find your service account
2. Click on the service account email
3. Go to **Keys** tab
4. Click **Add Key → Create new key**
5. Select **JSON**
6. Click **Create**
7. JSON file downloads automatically
8. **Keep this file secure!**

### Step 3: Share Calendar with Service Account

1. Open the downloaded JSON file
2. Copy the `client_email` value (e.g., `frontdesk-calendar@project.iam.gserviceaccount.com`)
3. Go to [Google Calendar](https://calendar.google.com/)
4. Find your calendar → Three dots → **Settings and sharing**
5. Scroll to **Share with specific people or groups**
6. Click **Add people and groups**
7. Paste the service account email
8. Set permissions to **Make changes to events**
9. Click **Send**

### Step 4: Upload to FrontDesk AI

1. Log in to FrontDesk AI dashboard
2. Navigate to your client → **Edit**
3. In **Calendar Authentication** section:
   - Click **Choose File** under "Upload Service Account"
   - Select your JSON key file
   - Click **Upload**
4. Status shows **Service Account Uploaded** ✅
5. Service account email is displayed
6. Set your Calendar ID
7. Click **Save**

**Done!** Your client can now use the uploaded service account.

---

## Method 3: Global Service Account (Fallback)

**Best for:** Testing, single-tenant deployments, or when per-client auth isn't needed.

**Advantages:**
- ✅ One-time setup
- ✅ All clients can use same credentials
- ✅ Simple for testing

**Disadvantages:**
- ⚠️ Not per-client
- ⚠️ Less secure for multi-tenant
- ⚠️ All clients share same calendar access

### Step 1: Create Service Account

Follow the same steps as Method 2, Steps 1-2.

### Step 2: Share Calendars

For each calendar you want to use:
1. Follow Method 2, Step 3
2. Share the calendar with the service account email

### Step 3: Configure Environment Variable

1. Place the JSON key file in a secure location:
   ```bash
   /home/w0lf/dev/frontdesk/calendar-credentials.json
   ```

2. Add to `.env`:
   ```bash
   GOOGLE_SERVICE_ACCOUNT_FILE_PATH="/home/w0lf/dev/frontdesk/calendar-credentials.json"
   ```

3. Set file permissions (Linux/Mac):
   ```bash
   chmod 600 /home/w0lf/dev/frontdesk/calendar-credentials.json
   ```

4. Restart FrontDesk AI server

### Step 4: Configure Clients

For each client:
1. Edit client in dashboard
2. Set the **Calendar ID** (the calendar you shared in Step 2)
3. Leave calendar authentication empty (uses global fallback)
4. Click **Save**

**Done!** Clients will use the global service account.

---

## Testing Your Integration

### Test Calendar Access

1. Make a test call to your FrontDesk AI number
2. Try these commands:
   - "What times are available tomorrow?"
   - "Book an appointment for tomorrow at 2 PM"
   - "What appointments do I have?"

3. Check your Google Calendar to verify:
   - Availability check worked
   - Appointment was created
   - Details are correct

### Check Logs

View detailed logs:
```bash
tail -f frontdesk_calls.log | grep -i calendar
```

Look for:
- `[TOOL DEBUG] Calling tool: get_available_slots`
- `Successfully retrieved slots from Google Calendar`
- `Event created with ID: xyz...`

---

## Troubleshooting

### OAuth Issues

**Error: "Redirect URI mismatch"**
- Solution: Ensure the redirect URI in Google Cloud Console exactly matches your BASE_URL + `/api/calendar/oauth/callback`
- Development: `http://localhost:8000/api/calendar/oauth/callback`
- Production: `https://yourdomain.com/api/calendar/oauth/callback`

**Error: "Access blocked: App not verified"**
- Solution: Add your email to **Test Users** in OAuth consent screen
- Or: Submit app for Google verification (for public apps)

**OAuth popup blocked**
- Solution: Allow popups for your domain
- Try again after allowing

**Token refresh failed**
- Solution: Re-authorize the calendar (revoke and authorize again)
- Check that encryption key hasn't changed

### Service Account Issues

**Error: "Calendar not found" or "Permission denied"**
- Solution: Verify you shared the calendar with the service account email
- Check permissions are "Make changes to events"
- Confirm Calendar ID is correct

**Error: "Service account not found"**
- Solution: Verify JSON file uploaded successfully
- Check that JSON format is valid
- Try re-uploading

### General Issues

**Error: "Calendar service not available"**
- Check Google Calendar API is enabled in Google Cloud Console
- Verify credentials are configured (OAuth or Service Account)
- Check application logs for specific errors

**No available slots returned**
- Verify calendar has free time in the requested range
- Check calendar working hours settings
- Ensure events are not marked as "available" or "free"

**Events not appearing in calendar**
- Confirm using correct Calendar ID
- Check service account/OAuth has write permissions
- Verify no firewall blocking Google API access

**Credential encryption errors**
- Verify `CALENDAR_CREDENTIALS_ENCRYPTION_KEY` is set
- Ensure key is a 32-byte hex string (64 characters)
- Key must remain constant (don't change after storing credentials)

---

## Security Best Practices

### For All Methods

1. **Enable Google Calendar API only**
   - Don't enable unnecessary APIs
   - Regularly review enabled APIs

2. **Use least privilege**
   - OAuth: Only grant calendar access
   - Service accounts: Only share necessary calendars

3. **Monitor activity**
   - Review calendar audit logs regularly
   - Check for unexpected events or changes

4. **Rotate credentials**
   - OAuth: Tokens auto-refresh, revoke if compromised
   - Service accounts: Rotate keys annually

### OAuth-Specific

1. **Keep encryption key secure**
   - Never commit `CALENDAR_CREDENTIALS_ENCRYPTION_KEY` to git
   - Use environment variables or secrets manager
   - Back up the key securely (losing it means re-authorizing all clients)

2. **HTTPS in production**
   - Always use HTTPS for OAuth redirects
   - Configure proper SSL/TLS certificates

3. **Validate redirect URIs**
   - Only authorize necessary domains
   - Use specific paths, not wildcards

### Service Account-Specific

1. **Secure JSON files**
   ```bash
   chmod 600 service-account.json  # Read/write for owner only
   ```

2. **Never commit to version control**
   - Add `*.json` to `.gitignore`
   - Use environment variables for paths

3. **Restrict sharing**
   - Only share calendars that need AI access
   - Use "Make changes to events", not "Manage sharing"

4. **Delete unused keys**
   - In Google Cloud Console, delete old/unused service account keys
   - Keep only active keys

---

## Cost Considerations

### Google Calendar API Quotas

- **Free tier**: 1,000,000 requests/day
- **Rate limit**: 500 queries per 100 seconds per user

### Typical Usage

- **Per call average**: 2-5 API requests
  - 1 request: Check availability
  - 1 request: Book appointment
  - Optional: List existing appointments

- **1000 calls/day**: ~2,000-5,000 API requests
- **Well within free tier limits**

### OAuth vs Service Account

Both methods use the same API and have the same quotas. Choose based on:
- **Ease of use**: OAuth
- **Control**: Service Account
- **Testing**: Global Service Account

---

## Additional Resources

- [Google Calendar API Documentation](https://developers.google.com/calendar/api/guides/overview)
- [OAuth 2.0 Guide](https://developers.google.com/identity/protocols/oauth2)
- [Service Account Authentication](https://cloud.google.com/iam/docs/service-accounts)
- [Google Cloud Console](https://console.cloud.google.com/)

---

## Need Help?

If you encounter issues not covered in this guide:

1. **Check logs**: `tail -f frontdesk_calls.log`
2. **Review this guide**: Re-read the troubleshooting section
3. **Search issues**: [GitHub Issues](https://github.com/stephenschoettler/frontdesk-ai/issues)
4. **Ask for help**: [GitHub Discussions](https://github.com/stephenschoettler/frontdesk-ai/discussions)
5. **Open an issue**: Provide logs, steps to reproduce, environment details

---

**Ready to book your first appointment? Make a test call and say: "I'd like to schedule an appointment"** 📅
