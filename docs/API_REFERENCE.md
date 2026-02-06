# API Reference

Complete REST API documentation for FrontDesk AI.

## Base URL

- **Development**: `http://localhost:8000`
- **Production**: `https://yourdomain.com`

## Authentication

All API endpoints (except webhooks) require JWT authentication.

### Headers

```http
Authorization: Bearer <jwt_token>
Content-Type: application/json
```

### Getting an Access Token

Use Google OAuth to authenticate users:

```http
POST /auth/google/callback
Content-Type: application/json

{
  "code": "google_oauth_authorization_code",
  "state": "state_token"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "name": "John Doe"
  }
}
```

---

## Endpoints

### Authentication

#### Initiate User OAuth

```http
POST /auth/google/initiate
```

Generates Google OAuth URL for user authentication.

**Response:**
```json
{
  "authorization_url": "https://accounts.google.com/o/oauth2/auth?..."
}
```

#### Google OAuth Callback

```http
GET /auth/google/callback?code=...&state=...
```

Handles Google OAuth redirect. Returns JWT token.

---

### Clients

#### List Clients

```http
GET /api/clients
```

Returns all clients owned by the authenticated user.

**Response:**
```json
[
  {
    "id": "uuid",
    "name": "Acme Corp",
    "phone_number": "+15551234567",
    "calendar_id": "primary",
    "system_prompt": "You are a receptionist...",
    "initial_greeting": "Hi, I'm Front Desk...",
    "llm_model": "openai/gpt-4o-mini",
    "stt_model": "nova-2-phonecall",
    "tts_provider": "cartesia",
    "tts_voice_id": "voice-id-here",
    "enabled_tools": ["get_available_slots", "book_appointment"],
    "balance_seconds": 3600,
    "is_active": true,
    "created_at": "2026-01-15T10:00:00Z",
    "updated_at": "2026-02-06T10:00:00Z"
  }
]
```

#### Get Client

```http
GET /api/clients/{client_id}
```

Get specific client details.

**Response:** Same as list item above

#### Create Client

```http
POST /api/clients
Content-Type: application/json

{
  "name": "New Client",
  "phone_number": "+15559876543",
  "calendar_id": "email@gmail.com",
  "system_prompt": "Custom prompt...",
  "initial_greeting": "Welcome to...",
  "llm_model": "openai/gpt-4o",
  "stt_model": "nova-2-phonecall",
  "tts_provider": "cartesia",
  "tts_voice_id": "voice-id",
  "enabled_tools": ["get_available_slots", "book_appointment"],
  "balance_seconds": 0,
  "is_active": true
}
```

**Response:**
```json
{
  "id": "newly-created-uuid",
  "name": "New Client",
  ...
}
```

#### Update Client

```http
PUT /api/clients/{client_id}
Content-Type: application/json

{
  "name": "Updated Name",
  "tts_provider": "elevenlabs",
  ...
}
```

**Response:** Updated client object

#### Delete Client

```http
DELETE /api/clients/{client_id}
```

**Response:**
```json
{
  "message": "Client deleted successfully"
}
```

---

### Calendar OAuth

#### Get Calendar Auth Status

```http
GET /api/clients/{client_id}/calendar/status
```

Returns the calendar authentication status for a client.

**Response:**
```json
{
  "has_credentials": true,
  "credential_type": "oauth",
  "created_at": "2026-02-05T10:00:00Z",
  "last_used_at": "2026-02-06T09:30:00Z",
  "fallback_available": true
}
```

#### Initiate OAuth Flow

```http
POST /api/clients/{client_id}/calendar/oauth/initiate
```

Generates Google OAuth authorization URL for calendar access.

**Response:**
```json
{
  "authorization_url": "https://accounts.google.com/o/oauth2/auth?...",
  "state": "csrf_state_token"
}
```

#### OAuth Callback

```http
GET /api/calendar/oauth/callback?code=...&state=...
```

Handles Google Calendar OAuth redirect. Stores encrypted credentials.

**Response:** HTML page with postMessage to close popup

#### Upload Service Account

```http
POST /api/clients/{client_id}/calendar/service-account
Content-Type: application/json

{
  "service_account_json": "{\"type\":\"service_account\",...}"
}
```

**Response:**
```json
{
  "message": "Service account uploaded successfully",
  "service_account_email": "frontdesk@project.iam.gserviceaccount.com"
}
```

#### Revoke Credentials

```http
DELETE /api/clients/{client_id}/calendar/credentials
```

Revokes and deletes calendar credentials.

**Response:**
```json
{
  "message": "Calendar credentials revoked successfully"
}
```

---

### Contacts

#### List Contacts

```http
GET /api/clients/{client_id}/contacts
```

Returns all contacts for a specific client.

**Response:**
```json
[
  {
    "id": "uuid",
    "client_id": "client-uuid",
    "phone_number": "+15551234567",
    "name": "John Doe",
    "created_at": "2026-01-20T10:00:00Z",
    "updated_at": "2026-02-06T10:00:00Z"
  }
]
```

#### Create Contact

```http
POST /api/contacts
Content-Type: application/json

{
  "client_id": "client-uuid",
  "phone_number": "+15559876543",
  "name": "Jane Smith"
}
```

**Response:** Created contact object

#### Update Contact

```http
PUT /api/contacts/{contact_id}
Content-Type: application/json

{
  "name": "Jane Doe"
}
```

**Response:** Updated contact object

#### Delete Contact

```http
DELETE /api/contacts/{contact_id}
```

**Response:**
```json
{
  "message": "Contact deleted successfully"
}
```

---

### Conversations

#### List Conversations

```http
GET /api/clients/{client_id}/conversations
```

Returns conversation history for a client.

**Query Parameters:**
- `limit` (optional): Number of results (default: 50)
- `offset` (optional): Pagination offset

**Response:**
```json
[
  {
    "id": "uuid",
    "client_id": "client-uuid",
    "contact_id": "contact-uuid",
    "duration": 120,
    "created_at": "2026-02-06T10:00:00Z",
    "transcript": [
      {
        "role": "assistant",
        "content": "Hi, I'm Front Desk...",
        "timestamp": "2026-02-06T10:00:10Z"
      },
      {
        "role": "user",
        "content": "I'd like to book an appointment",
        "timestamp": "2026-02-06T10:00:15Z"
      }
    ]
  }
]
```

#### Get Conversation

```http
GET /api/conversations/{conversation_id}
```

Get detailed conversation transcript.

**Response:** Same as list item above

#### Delete Conversation

```http
DELETE /api/conversations/{conversation_id}
```

**Response:**
```json
{
  "message": "Conversation deleted successfully"
}
```

---

### Monitoring

#### Get Active Calls

```http
GET /api/active-calls
```

Returns currently active calls across all clients.

**Response:**
```json
[
  {
    "call_id": "call-uuid",
    "client_id": "client-uuid",
    "client_name": "Acme Corp",
    "caller_phone": "+15551234567",
    "start_time": "2026-02-06T10:00:00Z",
    "owner_user_id": "user-uuid"
  }
]
```

---

### Webhooks

These endpoints are called by external services and don't require authentication.

#### Twilio Voice Webhook

```http
POST /voice
Content-Type: application/x-www-form-urlencoded

From=+15551234567
To=+15559876543
CallSid=CA123...
```

Returns TwiML to establish WebSocket connection.

**Response:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Connect>
    <Stream url="wss://yourdomain.com/ws/client-uuid/+15551234567" />
  </Connect>
</Response>
```

#### Stripe Webhook

```http
POST /api/stripe/webhook
Content-Type: application/json
Stripe-Signature: signature_here

{
  "type": "checkout.session.completed",
  "data": { ... }
}
```

Handles Stripe payment events (subscriptions, top-ups, etc.)

---

## WebSocket

### Call Audio Stream

```
WS /ws/{client_id}/{caller_phone}
```

Bidirectional audio stream for Twilio calls.

**Connection:**
- Protocol: WebSocket (WSS in production)
- Format: Twilio Media Stream JSON

**Flow:**
1. Client connects
2. Server validates balance
3. Pipecat pipeline initialized
4. Bidirectional audio frames exchanged
5. Conversation logged on disconnect

---

## Error Responses

All errors follow this format:

```json
{
  "detail": "Error message here"
}
```

### HTTP Status Codes

- `200` - Success
- `201` - Created
- `400` - Bad Request (validation error)
- `401` - Unauthorized (missing/invalid token)
- `403` - Forbidden (insufficient permissions)
- `404` - Not Found
- `500` - Internal Server Error

### Example Error

```http
HTTP/1.1 401 Unauthorized
Content-Type: application/json

{
  "detail": "Invalid authentication credentials"
}
```

---

## Rate Limiting

Currently no rate limiting is enforced, but recommended limits:

- **API requests**: 100 per minute per user
- **WebSocket connections**: 10 concurrent per client

---

## Pagination

List endpoints support pagination:

```http
GET /api/clients?limit=20&offset=40
```

**Parameters:**
- `limit`: Results per page (max 100)
- `offset`: Starting position

---

## CORS

CORS is enabled for all origins in development. In production, configure allowed origins in your deployment.

---

## Examples

### Full Authentication Flow

```bash
# 1. Get OAuth URL
curl -X POST http://localhost:8000/auth/google/initiate

# 2. User authorizes in browser (redirect to callback)

# 3. Get JWT token
curl -X POST http://localhost:8000/auth/google/callback \
  -H "Content-Type: application/json" \
  -d '{"code":"auth_code","state":"state_token"}'

# Response includes access_token
```

### Create and Configure Client

```bash
# 1. Create client
curl -X POST http://localhost:8000/api/clients \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Business",
    "phone_number": "+15551234567",
    "calendar_id": "primary",
    "tts_provider": "cartesia"
  }'

# 2. Initiate calendar OAuth
curl -X POST http://localhost:8000/api/clients/CLIENT_ID/calendar/oauth/initiate \
  -H "Authorization: Bearer YOUR_TOKEN"

# 3. User authorizes in browser

# 4. Check status
curl http://localhost:8000/api/clients/CLIENT_ID/calendar/status \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Monitor Active Calls

```bash
# Get active calls
curl http://localhost:8000/api/active-calls \
  -H "Authorization: Bearer YOUR_TOKEN"

# Response shows all ongoing conversations
```

---

## SDK / Client Libraries

Currently no official SDKs. Use standard HTTP clients:

**Python:**
```python
import requests

headers = {"Authorization": f"Bearer {token}"}
response = requests.get("http://localhost:8000/api/clients", headers=headers)
clients = response.json()
```

**JavaScript:**
```javascript
const response = await fetch('http://localhost:8000/api/clients', {
  headers: { 'Authorization': `Bearer ${token}` }
});
const clients = await response.json();
```

**cURL:**
```bash
curl http://localhost:8000/api/clients \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## Changelog

- **v0.3.0** - Added TTS provider selection, Cartesia support
- **v0.2.0** - Added calendar OAuth endpoints
- **v0.1.0** - Initial API release

---

For implementation details, see [ARCHITECTURE.md](ARCHITECTURE.md)

For setup instructions, see [INSTALLATION.md](INSTALLATION.md)
