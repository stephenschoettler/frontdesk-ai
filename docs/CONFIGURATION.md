# Configuration Guide

Complete guide to configuring FrontDesk AI.

## Environment Variables

### Required Variables

```bash
# AI Service Keys
DEEPGRAM_API_KEY=          # Speech-to-text API key
DEEPGRAM_PROJECT_ID=       # Deepgram project ID
CARTESIA_API_KEY=          # TTS API key (recommended)
OPENROUTER_API_KEY=        # LLM API key

# Database
SUPABASE_URL=              # Supabase project URL
SUPABASE_ANON_KEY=         # Public anon key
SUPABASE_SERVICE_ROLE_KEY= # Service role key (admin)

# Telephony
TWILIO_ACCOUNT_SID=        # Twilio account SID
TWILIO_AUTH_TOKEN=         # Twilio auth token

# Calendar OAuth
GOOGLE_OAUTH_CLIENT_ID=    # Google OAuth client ID
GOOGLE_OAUTH_CLIENT_SECRET=# Google OAuth secret
CALENDAR_CREDENTIALS_ENCRYPTION_KEY= # 32-byte hex key
BASE_URL=                  # Your domain (http://localhost:8000)
```

### Optional Variables

```bash
# Optional TTS
ELEVENLABS_API_KEY=        # ElevenLabs TTS (premium option)

# Legacy Calendar (fallback)
GOOGLE_SERVICE_ACCOUNT_FILE_PATH= # Path to service account JSON

# Stripe Billing
STRIPE_PUBLISHABLE_KEY=    # Stripe public key
STRIPE_SECRET_KEY=         # Stripe secret key
STRIPE_WEBHOOK_SECRET=     # Webhook signing secret
STRIPE_PRICE_STARTER=      # Starter plan price ID
STRIPE_PRICE_GROWTH=       # Growth plan price ID
STRIPE_PRICE_POWER=        # Power plan price ID
```

## Client Configuration

Clients are configured via the web dashboard. Each client can customize:

### Identity
- **Name**: Business name
- **Phone Number**: Twilio number for this client
- **Calendar ID**: Google Calendar ID
- **Active Status**: Enable/disable calls

### AI Settings
- **LLM Model**: Choose from OpenRouter models
- **STT Model**: Deepgram model selection
- **TTS Provider**: Cartesia or ElevenLabs
- **TTS Voice**: Voice preset selection

### Behavior
- **System Prompt**: AI personality and instructions
- **Initial Greeting**: First message to callers
- **Enabled Tools**: Which features are available

### Billing
- **Balance**: Call minutes remaining
- **Subscription**: Plan level (if using Stripe)

## System Prompts

System prompts define your AI's behavior. See [PROMPTING.md](PROMPTING.md) for guidance.

**Template structure:**
```
[System Identity]
- Who the AI is
- Tone and personality

[Caller Context]
- How to handle caller information
- Using existing bookings

[Protocols]
- Step-by-step workflows
- Tool usage instructions

[Closing]
- How to end calls
- Goodbye signal
```

## Voice Selection

### Cartesia Voices (19 options)
- Professional, friendly, authoritative personalities
- $0.05/min
- Good quality over phone

### ElevenLabs Voices
- Premium studio quality  
- $0.24/min
- Best for brand consistency

**Select in dashboard per client**

## LLM Models

Available via OpenRouter:

**Recommended:**
- `openai/gpt-4o-mini` - Fast, cheap, good quality
- `meta-llama/llama-3.1-70b-instruct` - Open source, affordable
- `anthropic/claude-3.5-sonnet` - Best reasoning
- `openai/gpt-4o` - Most capable

**Cost range:** $0.06 - $15 per 1M tokens

## Calendar Integration

Three authentication methods (see [GOOGLE_CALENDAR_SETUP.md](GOOGLE_CALENDAR_SETUP.md)):

1. **OAuth 2.0** - One-click per-client auth
2. **Service Account Upload** - BYOK approach  
3. **Global Fallback** - Shared credentials

## Security Settings

### Encryption
- Calendar credentials encrypted with AES-256
- Encryption key must be 32-byte hex
- **Never change key** after storing credentials

### Access Control
- Row Level Security in database
- JWT authentication for API
- OAuth for user login

### Best Practices
- Use strong encryption key
- Enable HTTPS in production
- Rotate API keys quarterly
- Review access logs regularly

## Performance Tuning

### Call Quality
- Use Deepgram Nova-2 for best accuracy
- Choose appropriate LLM (faster for simple tasks)
- Enable VAD for natural conversation flow

### Cost Optimization  
- Use Cartesia TTS (5x cheaper)
- Choose cheaper LLM for simple tasks
- Set reasonable balance limits

### Scalability
- Vertical: More CPU/RAM for concurrent calls
- Horizontal: Load balancer + multiple instances

## Logging

Logs are written to:
- `frontdesk.log` - General application logs
- `frontdesk_calls.log` - Detailed call logs
- Database: Full conversation transcripts

**View logs:**
```bash
tail -f frontdesk_calls.log
tail -f frontdesk_calls.log | grep GREETING
```

For more details, see [ARCHITECTURE.md](ARCHITECTURE.md)
