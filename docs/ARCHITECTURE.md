# FrontDesk AI - System Architecture

Complete system architecture documentation for FrontDesk AI.

## Table of Contents

- [Overview](#overview)
- [System Components](#system-components)
- [Data Flow](#data-flow)
- [Database Schema](#database-schema)
- [API Architecture](#api-architecture)
- [AI Pipeline](#ai-pipeline)
- [Security Architecture](#security-architecture)
- [Scalability](#scalability)

---

## Overview

FrontDesk AI is a multi-tenant SaaS platform built on a modern, production-ready architecture. The system handles real-time voice conversations, manages calendar appointments, and provides a comprehensive web dashboard for client management.

### High-Level Architecture

```
┌─────────────┐          ┌──────────────┐          ┌─────────────┐
│   Caller    │◄────────►│   Twilio     │◄────────►│   FastAPI   │
│  (Phone)    │   Voice  │   (WebRTC)   │   WSS    │   Backend   │
└─────────────┘          └──────────────┘          └──────┬──────┘
                                                           │
                         ┌─────────────────────────────────┤
                         │                                 │
                    ┌────▼─────┐                     ┌─────▼─────┐
                    │ Pipecat  │                     │  Supabase │
                    │ Pipeline │                     │ (Postgres)│
                    └────┬─────┘                     └───────────┘
                         │
       ┌─────────────────┼─────────────────┐
       │                 │                 │
  ┌────▼────┐       ┌────▼────┐      ┌────▼────┐
  │Deepgram │       │OpenRouter│      │Cartesia │
  │  (STT)  │       │  (LLM)   │      │  (TTS)  │
  └─────────┘       └──────────┘      └─────────┘
                         │
                    ┌────▼──────┐
                    │  Google   │
                    │ Calendar  │
                    └───────────┘
```

### Technology Stack

**Backend:**
- Python 3.11
- FastAPI (ASGI web framework)
- Uvicorn (ASGI server)
- Pipecat (Real-time AI pipeline orchestration)

**Frontend:**
- Vue.js 3 (Composition API)
- Bootstrap 5
- Vanilla JavaScript (no build step)

**Database:**
- PostgreSQL via Supabase
- Row Level Security (RLS)
- Real-time subscriptions

**Infrastructure:**
- Twilio (Voice/WebSocket)
- ngrok (Development tunneling)
- Stripe (Payment processing)

---

## System Components

### 1. Web Server (FastAPI)

**main.py** - Core application server

```python
# Key responsibilities:
- HTTP/WebSocket endpoint handling
- User authentication (JWT)
- Client routing (phone number → client mapping)
- Real-time call orchestration
- API endpoints for dashboard
- Webhook handling (Twilio, Stripe)
```

**Key Endpoints:**
- `POST /voice` - Twilio webhook for incoming calls
- `WS /ws/{client_id}/{caller_phone}` - WebSocket for audio streaming
- `GET /api/clients` - Client management
- `POST /api/clients/{id}/calendar/oauth/initiate` - Calendar OAuth
- `GET /api/active-calls` - Real-time call monitoring
- `POST /api/stripe/*` - Billing webhooks

### 2. Pipecat AI Pipeline

**Pipeline Architecture:**

```
┌──────────────┐
│   Twilio     │
│  Transport   │ (Bidirectional audio)
└──────┬───────┘
       │
┌──────▼───────┐
│   Deepgram   │ (Audio → Text)
│     STT      │
└──────┬───────┘
       │
┌──────▼───────┐
│   Context    │ (Conversation state)
│  Aggregator  │
└──────┬───────┘
       │
┌──────▼───────┐
│  OpenRouter  │ (Text → Response + Tool Calls)
│     LLM      │
└──────┬───────┘
       │
┌──────▼───────┐
│   Cartesia   │ (Text → Audio)
│     TTS      │
└──────┬───────┘
       │
┌──────▼───────┐
│   Twilio     │
│  Transport   │ (Audio output)
└──────────────┘
```

**Pipeline Features:**
- Bidirectional audio streaming
- Frame-based processing
- Context management
- Tool execution
- Error handling
- Metrics collection

### 3. Service Layer

**services/** directory structure:

```
services/
├── supabase_client.py      # Database operations
├── google_calendar.py      # Calendar integration
├── calendar_auth.py        # OAuth & credential management
├── user_auth.py            # User authentication
├── llm_tools.py            # LLM tool handlers
├── price_manager.py        # Cost tracking
└── twilio_client.py        # Twilio operations
```

**Key Services:**

**supabase_client.py:**
- Database connection management
- CRUD operations for clients, contacts, conversations
- Balance management
- User operations

**google_calendar.py:**
- Calendar API integration
- Appointment booking/rescheduling/cancellation
- Availability checking
- Multi-auth support (OAuth, Service Account, Global)

**llm_tools.py:**
- Tool function definitions
- Parameter validation
- Calendar tool wrappers
- Contact management tools

**calendar_auth.py:**
- OAuth flow management
- Credential encryption/decryption
- Token refresh
- Service account upload

### 4. Frontend (Vue.js)

**static/** directory:

```
static/
├── index.html         # SPA shell
├── app.js             # Vue app + state management
└── styles.css         # Custom styles
```

**Vue Components (in-template):**
- Auth modal (Google OAuth)
- Client list & management
- Client edit modal
- Contact list
- Call logs
- Active calls dashboard
- Settings panel

**State Management:**
- Reactive data with Vue 3 Composition API
- Real-time updates via polling
- Modal state management
- Form validation

---

## Data Flow

### Call Flow

```
1. Caller dials Twilio number
   ↓
2. Twilio POST /voice webhook
   ↓
3. Backend looks up client by phone number
   ↓
4. Return TwiML with WebSocket URL
   ↓
5. Twilio establishes WebSocket connection
   ↓
6. Backend checks client balance (reject if $0)
   ↓
7. Initialize Pipecat pipeline with client config
   ↓
8. Load caller contact & appointment history
   ↓
9. Inject context into LLM messages
   ↓
10. Send initial greeting (TTSSpeakFrame)
    ↓
11. Bidirectional conversation loop:
    - Audio in → STT → LLM → TTS → Audio out
    - Tool calls handled inline
    - Context updated continuously
    ↓
12. Call ends (user hangs up or timeout)
    ↓
13. Finalize conversation transcript
    ↓
14. Log conversation to database
    ↓
15. Deduct balance (per-second billing)
    ↓
16. Close WebSocket
```

### OAuth Flow

```
1. User clicks "Authorize Calendar" in dashboard
   ↓
2. Frontend → POST /api/clients/{id}/calendar/oauth/initiate
   ↓
3. Backend generates state token, stores in DB
   ↓
4. Return Google OAuth authorization URL
   ↓
5. Frontend opens popup with OAuth URL
   ↓
6. User authorizes in Google
   ↓
7. Google redirects to /api/calendar/oauth/callback?code=...&state=...
   ↓
8. Backend validates state token
   ↓
9. Exchange code for access/refresh tokens
   ↓
10. Encrypt tokens with AES
    ↓
11. Store in calendar_credentials table
    ↓
12. Return success HTML with postMessage
    ↓
13. Popup closes, dashboard refreshes status
```

### Appointment Booking Flow

```
1. Caller: "I'd like to book an appointment"
   ↓
2. LLM: "What day works best?"
   ↓
3. Caller: "Tomorrow morning"
   ↓
4. LLM decides to call get_available_slots tool
   - Parameters: date=tomorrow, time_range=morning
   ↓
5. Tool handler retrieves client calendar credentials
   ↓
6. Call Google Calendar API
   ↓
7. Return available slots to LLM
   ↓
8. LLM: "I have 9 AM, 10 AM, 11 AM available..."
   ↓
9. Caller: "9 AM"
   ↓
10. LLM calls book_appointment tool
    - Parameters: start_time=9AM, phone=caller
    ↓
11. Create event in Google Calendar
    ↓
12. Return success
    ↓
13. LLM: "Your appointment is booked for 9 AM"
```

---

## Database Schema

### Core Tables

**users**
```sql
id              uuid PRIMARY KEY
email           text UNIQUE NOT NULL
name            text
created_at      timestamptz
last_login      timestamptz
```

**clients**
```sql
id                  uuid PRIMARY KEY
owner_user_id       uuid REFERENCES users(id)
name                text NOT NULL
phone_number        text UNIQUE
calendar_id         text
system_prompt       text
initial_greeting    text
llm_model           text
stt_model           text
tts_provider        text (cartesia | elevenlabs)
tts_model           text
tts_voice_id        text
enabled_tools       text[]
balance_seconds     integer DEFAULT 0
is_active           boolean DEFAULT true
created_at          timestamptz
updated_at          timestamptz
```

**calendar_credentials**
```sql
id                      uuid PRIMARY KEY
client_id               uuid REFERENCES clients(id) ON DELETE CASCADE
credential_type         text CHECK (IN 'oauth', 'service_account')
oauth_access_token      text (encrypted)
oauth_refresh_token     text (encrypted)
oauth_token_expiry      timestamptz
oauth_scopes            text[]
service_account_json    text (encrypted)
service_account_email   text
created_at              timestamptz
updated_at              timestamptz
last_used_at            timestamptz
is_active               boolean DEFAULT true
UNIQUE (client_id, is_active) WHERE is_active = true
```

**contacts**
```sql
id              uuid PRIMARY KEY
client_id       uuid REFERENCES clients(id)
phone_number    text NOT NULL
name            text
created_at      timestamptz
updated_at      timestamptz
UNIQUE (client_id, phone_number)
```

**conversations**
```sql
id              uuid PRIMARY KEY
client_id       uuid REFERENCES clients(id)
contact_id      uuid REFERENCES contacts(id)
transcript      jsonb  -- Array of {role, content, timestamp}
summary         text
duration        integer (seconds)
created_at      timestamptz
```

**oauth_state_tokens**
```sql
state           text PRIMARY KEY
client_id       uuid REFERENCES clients(id) ON DELETE CASCADE
user_id         uuid REFERENCES users(id) ON DELETE CASCADE
created_at      timestamptz
expires_at      timestamptz DEFAULT now() + interval '10 minutes'
used            boolean DEFAULT false
```

### Row Level Security (RLS)

**Policies:**

```sql
-- Users can only see their own clients
CREATE POLICY "Users access own clients"
ON clients FOR ALL
USING (owner_user_id = auth.uid());

-- Users can only access contacts for their clients
CREATE POLICY "Users access contacts via clients"
ON contacts FOR ALL
USING (client_id IN (
  SELECT id FROM clients WHERE owner_user_id = auth.uid()
));

-- Users can only access conversations for their clients
CREATE POLICY "Users access conversations via clients"
ON conversations FOR ALL
USING (client_id IN (
  SELECT id FROM clients WHERE owner_user_id = auth.uid()
));

-- Users can only access credentials for their clients
CREATE POLICY "Users access credentials via clients"
ON calendar_credentials FOR ALL
USING (client_id IN (
  SELECT id FROM clients WHERE owner_user_id = auth.uid()
));
```

---

## API Architecture

### REST API Structure

**Base URL:** `http://localhost:8000` (dev) or `https://yourdomain.com` (prod)

### Authentication

**Method:** JWT Bearer Token

```http
Authorization: Bearer <jwt_token>
```

**User Login:**
```http
POST /auth/google/callback
{
  "code": "google_oauth_code",
  "state": "state_token"
}

Response:
{
  "access_token": "eyJ...",
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "name": "John Doe"
  }
}
```

### API Endpoints

**Client Management:**
```http
GET    /api/clients                    # List all clients
POST   /api/clients                    # Create new client
GET    /api/clients/{id}               # Get client details
PUT    /api/clients/{id}               # Update client
DELETE /api/clients/{id}               # Delete client
```

**Calendar OAuth:**
```http
POST   /api/clients/{id}/calendar/oauth/initiate    # Start OAuth flow
GET    /api/calendar/oauth/callback                 # OAuth callback
GET    /api/clients/{id}/calendar/status            # Get auth status
DELETE /api/clients/{id}/calendar/credentials       # Revoke credentials
POST   /api/clients/{id}/calendar/service-account   # Upload service account
```

**Contacts:**
```http
GET    /api/clients/{id}/contacts      # List contacts for client
POST   /api/contacts                   # Create contact
PUT    /api/contacts/{id}              # Update contact
DELETE /api/contacts/{id}              # Delete contact
```

**Conversations:**
```http
GET    /api/clients/{id}/conversations  # List conversations
GET    /api/conversations/{id}          # Get conversation transcript
DELETE /api/conversations/{id}          # Delete conversation
```

**Monitoring:**
```http
GET    /api/active-calls                # List active calls (real-time)
```

**Webhooks:**
```http
POST   /voice                          # Twilio voice webhook
POST   /api/stripe/webhook             # Stripe payment webhook
```

---

## AI Pipeline

### Pipecat Pipeline Configuration

**Pipeline Stages:**

1. **Transport Input** - Twilio WebSocket receives audio chunks
2. **STT** - Deepgram converts audio to text in real-time
3. **Context Aggregator** - Manages conversation state
4. **LLM** - Processes context and generates responses
5. **TTS** - Converts text responses to audio
6. **Transport Output** - Sends audio back to Twilio
7. **Assistant Aggregator** - Strips tool calls from spoken output

### LLM Tool System

**Tool Registration:**

```python
llm.register_direct_function(get_available_slots)
llm.register_direct_function(book_appointment)
llm.register_direct_function(reschedule_appointment)
llm.register_direct_function(cancel_appointment)
llm.register_direct_function(save_contact_name)
llm.register_direct_function(list_my_appointments)
```

**Tool Execution:**

1. LLM decides to call a tool
2. Pipecat intercepts function call
3. Tool handler executes (async)
4. Result returned to LLM
5. LLM incorporates result into response
6. Response sent to TTS

**Context Injection:**

```python
messages = [
    {"role": "system", "content": system_prompt},
    {"role": "system", "content": f"CALLER CONTEXT: {contact_info}"},
    {"role": "system", "content": f"Current date: {current_date}"},
    {"role": "assistant", "content": initial_greeting}  # Pre-populated
]
```

### Initial Greeting System

**Flow:**

1. Pipeline initialized
2. Initial greeting added to context as assistant message
3. Runner started
4. After 1 second delay, TTSSpeakFrame queued with greeting text
5. Greeting plays immediately without user input
6. Conversation continues normally

---

## Security Architecture

### Authentication & Authorization

**Layer 1: User Authentication**
- Google OAuth 2.0
- JWT session tokens
- Secure cookie storage

**Layer 2: API Authorization**
- Bearer token required on all API endpoints
- Token validation on every request
- User ID extracted from JWT

**Layer 3: Database RLS**
- PostgreSQL Row Level Security
- User can only access own data
- Enforced at database level

### Data Encryption

**At Rest:**
- OAuth tokens: AES-256-GCM via pgcrypto
- Service account JSON: AES-256-GCM
- Encryption key stored in environment variable

**In Transit:**
- HTTPS/TLS for all HTTP traffic
- WSS (WebSocket Secure) for audio
- Encrypted Twilio transport

### CSRF Protection

**OAuth State Tokens:**
- Random 32-byte token generated
- Stored in database with 10-minute expiration
- One-time use enforced
- Validated on callback

---

## Scalability

### Current Architecture

**Single-Server Deployment:**
- Handles ~50 concurrent calls
- Suitable for small-medium businesses
- Vertical scaling (more CPU/RAM)

### Scaling Strategy

**Horizontal Scaling:**

```
┌─────────────┐
│   Twilio    │
└──────┬──────┘
       │
┌──────▼──────────────────────┐
│     Load Balancer            │
│  (nginx/HAProxy/AWS ALB)     │
└────┬────────┬────────┬───────┘
     │        │        │
┌────▼───┐ ┌──▼────┐ ┌▼──────┐
│FastAPI │ │FastAPI│ │FastAPI│
│Instance│ │Instance│ │Instance│
└────┬───┘ └───┬───┘ └───┬───┘
     │         │         │
     └─────────┴─────────┘
               │
       ┌───────▼────────┐
       │   Supabase     │
       │  (Postgres)    │
       └────────────────┘
```

**Considerations:**
- WebSocket sticky sessions required
- Shared Supabase database
- Redis for session storage (future)
- Distributed call tracking

### Performance Optimization

**Current Optimizations:**
- Async I/O throughout
- Connection pooling (Supabase)
- Lazy loading of AI services
- Efficient frame processing (Pipecat)

**Future Optimizations:**
- Caching layer (Redis)
- CDN for static assets
- Database query optimization
- Connection multiplexing

---

## Development vs. Production

### Development Setup

```
┌─────────┐     ┌─────────┐     ┌──────────┐
│ Twilio  │────▶│  ngrok  │────▶│ FastAPI  │
│         │     │         │     │localhost │
└─────────┘     └─────────┘     └────┬─────┘
                                      │
                                ┌─────▼──────┐
                                │  Supabase  │
                                │   Cloud    │
                                └────────────┘
```

### Production Setup

```
┌─────────┐     ┌─────────┐     ┌──────────┐
│ Twilio  │────▶│   DNS   │────▶│   nginx  │
│         │     │         │     │reverse   │
└─────────┘     └─────────┘     │  proxy   │
                                └────┬─────┘
                                     │
                                ┌────▼─────┐
                                │ FastAPI  │
                                │ systemd  │
                                └────┬─────┘
                                     │
                                ┌────▼──────┐
                                │  Supabase │
                                │   Cloud   │
                                └───────────┘
```

**Production Requirements:**
- SSL/TLS certificates
- Process manager (systemd/supervisor)
- Reverse proxy (nginx)
- Firewall configuration
- Log aggregation
- Monitoring & alerts

---

## Monitoring & Observability

### Logging

**Current Logging:**
- File-based logs (`frontdesk.log`, `frontdesk_calls.log`)
- Structured logging with levels (INFO, DEBUG, ERROR)
- Call transcripts logged to database

**Future:**
- ELK stack (Elasticsearch, Logstash, Kibana)
- Centralized log aggregation
- Log retention policies

### Metrics

**Current:**
- Basic call metrics (duration, cost)
- Manual database queries

**Future:**
- Prometheus + Grafana
- Real-time dashboards
- Custom metrics (latency, success rate, etc.)

### Error Tracking

**Future:**
- Sentry integration
- Error aggregation
- Alert notifications

---

## Technology Decisions

### Why Pipecat?

- **Real-time optimized** - Built for low-latency voice
- **Framework agnostic** - Works with any LLM/STT/TTS
- **Production ready** - Battle-tested by Daily.co
- **Extensible** - Easy to add custom processors

### Why FastAPI?

- **Async by default** - Perfect for real-time apps
- **Type safety** - Pydantic validation
- **Auto documentation** - OpenAPI/Swagger
- **Performance** - One of the fastest Python frameworks

### Why Supabase?

- **Postgres excellence** - Full SQL power
- **Row Level Security** - Database-level auth
- **Real-time** - Built-in subscriptions
- **Developer experience** - Excellent tooling

### Why Vue.js?

- **Progressive** - Can use without build step
- **Reactive** - Composition API is elegant
- **Lightweight** - Small bundle size
- **Easy to learn** - Gentle learning curve

---

**For deployment instructions, see [DEPLOYMENT.md](DEPLOYMENT.md)**

**For API details, see [API_REFERENCE.md](API_REFERENCE.md)**

**For feature documentation, see [FEATURES.md](FEATURES.md)**
