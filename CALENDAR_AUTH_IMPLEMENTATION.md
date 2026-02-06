# Google Calendar OAuth & Service Account Implementation

## Summary

Successfully implemented per-client Google Calendar authentication supporting both OAuth 2.0 and service account credentials. Clients can now choose their preferred authentication method, with the existing global service account remaining as a fallback.

## What Was Implemented

### 1. Database Changes ✅
- **New Table**: `calendar_credentials`
  - Stores encrypted OAuth tokens and service account JSON
  - Supports both credential types per client
  - Enforces one active credential per client
  - Tracks usage and metadata

- **New Table**: `oauth_state_tokens`
  - CSRF protection for OAuth flow
  - 10-minute expiration
  - One-time use enforcement

- **Encryption Functions**:
  - `encrypt_secret()` - AES encryption via pgcrypto
  - `decrypt_secret()` - Decryption with key from environment

- **RLS Policies**: Users can only manage credentials for their own clients

**Migration**: `supabase/migrations/20260205172816_add_calendar_credentials.sql`

### 2. Backend Services ✅

#### New Service: `services/calendar_auth.py`
Handles all calendar authentication operations:
- `generate_oauth_url()` - Initiates OAuth flow with state tokens
- `handle_oauth_callback()` - Exchanges code for tokens, stores encrypted
- `upload_service_account()` - Validates and stores service account JSON
- `get_calendar_credentials()` - Retrieves decrypted credentials for client
- `refresh_oauth_token()` - Auto-refreshes expired OAuth tokens
- `revoke_credentials()` - Deletes credentials and revokes with Google

#### Modified: `services/google_calendar.py`
Updated `get_calendar_service()` to support per-client credentials:
- **Priority**: Client OAuth → Client Service Account → Global Fallback
- Accepts `client_id` and `supabase` parameters
- Auto-refreshes expired OAuth tokens
- All calendar functions now accept `client_id` parameter:
  - `get_available_slots()`
  - `book_appointment()`
  - `reschedule_appointment()`
  - `cancel_appointment()`
  - `get_upcoming_appointments()`
  - `list_my_appointments()`

#### Modified: `services/llm_tools.py`
Updated all tool handlers to pass `client_id` and `supabase` to calendar functions:
- `handle_get_available_slots()`
- `handle_book_appointment()`
- `handle_reschedule_appointment()`
- `handle_cancel_appointment()`
- `handle_list_my_appointments()`

### 3. API Endpoints ✅

Added 5 new endpoints in `main.py`:

1. **GET `/api/clients/{client_id}/calendar/status`**
   - Returns credential status (type, created_at, last_used_at)
   - Shows whether global fallback is available
   - No sensitive data exposed

2. **POST `/api/clients/{client_id}/calendar/oauth/initiate`**
   - Generates OAuth authorization URL
   - Creates CSRF state token
   - Returns URL for frontend popup

3. **GET `/api/clients/{client_id}/calendar/oauth/callback`**
   - Handles OAuth redirect from Google
   - Exchanges code for tokens
   - Stores encrypted credentials
   - Returns HTML with postMessage for popup

4. **POST `/api/clients/{client_id}/calendar/service-account`**
   - Accepts service account JSON
   - Validates structure and fields
   - Encrypts and stores credentials
   - Returns service account email

5. **DELETE `/api/clients/{client_id}/calendar/credentials`**
   - Revokes OAuth token with Google (if applicable)
   - Deletes credentials from database
   - Returns success confirmation

All endpoints verify user owns the client via JWT token.

### 4. Frontend UI ✅

#### Client Edit Modal (`static/index.html`)
Added Calendar Authentication section after calendar_id field:
- **Status Display**: Shows current auth type (OAuth/Service Account/None)
- **Revoke Button**: Deletes credentials when clicked
- **OAuth Button**: Opens popup for Google authorization
- **File Upload**: Browse and upload service account JSON
- **Fallback Indicator**: Shows if global fallback is available
- Only visible in edit mode (not create mode)

#### Client Cards (`static/index.html`)
Added calendar auth status indicator below calendar_id:
- ✅ Green "OAuth" or "Service Account" badge if authenticated
- ⚠️ Yellow "Using Fallback" if using global account
- ❌ Red "Not Configured" if no credentials

#### State Management (`static/app.js`)
Added calendar auth functionality:
- **Refs**:
  - `calendarAuthStatus` - Current auth state
  - `initiatingOAuth` - Loading state for OAuth
  - `serviceAccountFile` - Selected file
  - `uploadingServiceAccount` - Upload loading state
  - `revokingCredentials` - Revoke loading state

- **Methods**:
  - `fetchCalendarAuthStatus()` - Loads status from API
  - `initiateOAuthFlow()` - Opens OAuth popup, handles postMessage
  - `handleServiceAccountFileSelect()` - Validates selected file
  - `uploadServiceAccount()` - Uploads and validates JSON
  - `revokeCalendarCredentials()` - Deletes credentials

- **Integration**:
  - `editClient()` now fetches auth status when modal opens
  - `loadClients()` fetches auth status for all clients in parallel

### 5. Environment Variables ✅

Updated `.env.example` with new required variables:

```bash
# Google OAuth 2.0 credentials (create in Google Cloud Console)
GOOGLE_OAUTH_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=your-client-secret

# Encryption key for credentials (generate with: openssl rand -hex 32)
CALENDAR_CREDENTIALS_ENCRYPTION_KEY=your-32-byte-hex-key

# Base URL for OAuth callbacks
BASE_URL=http://localhost:8000

# Global service account (now optional fallback)
GOOGLE_SERVICE_ACCOUNT_FILE_PATH=path/to/service-account.json
```

## Security Features

1. **Encryption**: All credentials encrypted at rest using AES via pgcrypto
2. **CSRF Protection**: State tokens prevent OAuth hijacking
3. **RLS Policies**: Users can only access their own client credentials
4. **Token Refresh**: Expired OAuth tokens automatically refreshed
5. **Secure Key Storage**: Encryption key from environment (never hardcoded)
6. **Minimal Scopes**: Only requests calendar access (no other Google services)
7. **Validation**: Service account JSON structure validated before storage

## How It Works

### OAuth Flow
1. User clicks "Connect with Google OAuth" in client edit modal
2. Backend generates auth URL with state token, stores in database
3. Frontend opens popup with Google authorization page
4. User authorizes, Google redirects to callback endpoint
5. Backend validates state token, exchanges code for tokens
6. Tokens encrypted and stored in database
7. Popup closes, frontend refreshes status

### Service Account Upload
1. User selects service account JSON file
2. Frontend reads file content
3. Backend validates JSON structure (type, project_id, private_key, etc.)
4. JSON encrypted and stored in database
5. Service account email displayed for confirmation

### Calendar API Calls
1. Tool handler receives calendar request with `client_id`
2. `get_calendar_service()` checks for client credentials:
   - Try OAuth credentials (refresh if expired)
   - Try service account credentials
   - Fallback to global service account
3. Calendar operation performed with appropriate credentials
4. Last used timestamp updated in database

## Testing Checklist

- [ ] OAuth flow works end-to-end
- [ ] Service account upload validates and stores correctly
- [ ] Calendar operations use client-specific credentials
- [ ] Expired OAuth tokens auto-refresh
- [ ] Global fallback works when no client credentials
- [ ] Revoke deletes credentials and updates UI
- [ ] RLS prevents cross-client access
- [ ] Credentials are encrypted in database
- [ ] Status indicators show correct state
- [ ] CSRF protection prevents token replay

## Migration Applied

✅ Database migration `20260205172816_add_calendar_credentials.sql` has been successfully applied.

Tables created:
- `calendar_credentials`
- `oauth_state_tokens`

Functions created:
- `encrypt_secret()`
- `decrypt_secret()`
- `cleanup_expired_oauth_state_tokens()`

## Next Steps

1. **Configure OAuth App in Google Cloud Console**:
   - Create OAuth 2.0 Client ID
   - Add authorized redirect URI: `{BASE_URL}/api/clients/{client_id}/calendar/oauth/callback`
   - Copy client ID and secret to `.env`

2. **Generate Encryption Key**:
   ```bash
   openssl rand -hex 32
   ```
   Add to `.env` as `CALENDAR_CREDENTIALS_ENCRYPTION_KEY`

3. **Update Documentation**:
   - Add OAuth setup instructions to `docs/GOOGLE_CALENDAR_SETUP.md`
   - Include screenshots of the new UI
   - Explain when to use OAuth vs service account

4. **Test End-to-End**:
   - Test OAuth flow with real Google account
   - Test service account upload
   - Verify calendar operations work with both auth types
   - Test credential revocation
   - Verify fallback behavior

## Files Modified

### New Files
- `supabase/migrations/20260205172816_add_calendar_credentials.sql`
- `services/calendar_auth.py`
- `CALENDAR_AUTH_IMPLEMENTATION.md` (this file)

### Modified Files
- `services/google_calendar.py`
- `services/llm_tools.py`
- `main.py`
- `static/index.html`
- `static/app.js`
- `.env.example`

## Architecture Diagram

```
User Request (with client_id)
        ↓
   Tool Handler (llm_tools.py)
        ↓
   get_calendar_service(client_id)
        ↓
   ┌─────────────────────────────┐
   │ Check Client Credentials    │
   ├─────────────────────────────┤
   │ 1. OAuth? → Build service   │
   │    ├─ Expired? → Refresh    │
   │    └─ Valid → Use tokens    │
   │                              │
   │ 2. Service Account?         │
   │    └─ Use SA credentials    │
   │                              │
   │ 3. Fallback                 │
   │    └─ Use global SA         │
   └─────────────────────────────┘
        ↓
   Google Calendar API
        ↓
   Calendar Operation Result
```

## Summary

This implementation provides flexible, secure, per-client calendar authentication while maintaining backward compatibility with the existing global service account. Users can choose the authentication method that best fits their needs, and the system gracefully handles token expiration and failover scenarios.
