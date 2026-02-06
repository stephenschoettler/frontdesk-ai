# Installation Guide

Detailed step-by-step installation guide for FrontDesk AI.

## Quick Links

- [Prerequisites](#prerequisites)
- [Service Setup](#service-setup)
- [Installation](#installation)
- [Configuration](#configuration)
- [First Run](#first-run)

---

## Prerequisites

### System Requirements

- **Operating System**: Linux, macOS, or Windows (WSL recommended)
- **Python**: 3.11 or higher
- **Node.js**: 18+ (for Supabase CLI)
- **Git**: For cloning the repository

### Required Accounts

Before installation, create accounts for:

1. ✅ **Twilio** - Phone number and voice services
2. ✅ **Supabase** - Database and authentication
3. ✅ **Deepgram** - Speech-to-text
4. ✅ **Cartesia** or **ElevenLabs** - Text-to-speech  
5. ✅ **OpenRouter** - LLM access
6. ✅ **Google Cloud** - Calendar integration
7. ✅ **Stripe** (optional) - Payment processing
8. ✅ **ngrok** - Development tunneling

---

## Service Setup

### 1. Twilio Setup

1. Create account at [twilio.com](https://www.twilio.com/)
2. **Upgrade account** - Add payment method (required to remove trial message)
3. **Buy phone number**:
   - Phone Numbers → Manage → Buy a number
   - Select number with **Voice** capability
   - Note: $1-2/month per number
4. **Get credentials**:
   - Dashboard → Account Info
   - Copy: Account SID, Auth Token

**Cost**: ~$1/month + $0.0085/min for calls

### 2. Supabase Setup

1. Create account at [supabase.com](https://supabase.com/)
2. **Create new project**:
   - Choose region close to you
   - Set strong database password
3. **Get credentials**:
   - Settings → API
   - Copy: Project URL, anon public key, service role key
4. **Run migrations** (after installation)

**Cost**: Free tier (500MB database, 50,000 monthly active users)

### 3. Deepgram Setup

1. Create account at [deepgram.com](https://deepgram.com/)
2. **Get API key**:
   - Console → API Keys → Create Key
3. **Get project ID**:
   - Console → Project Settings

**Cost**: $0.0043/min (Nova-2 model), $200 free credit

### 4. TTS Setup (Choose One or Both)

**Option A: Cartesia (Recommended - 5x Cheaper)**

1. Create account at [cartesia.ai](https://cartesia.ai/)
2. Get API key from dashboard

**Cost**: $0.05/min

**Option B: ElevenLabs (Premium Quality)**

1. Create account at [elevenlabs.io](https://elevenlabs.io/)
2. Get API key from profile

**Cost**: $0.24/min

### 5. OpenRouter Setup

1. Create account at [openrouter.ai](https://openrouter.ai/)
2. Add credits ($5-10 to start)
3. Get API key from Keys page

**Cost**: Varies by model ($0.06-$15 per 1M tokens)

### 6. Google Cloud Setup

See [GOOGLE_CALENDAR_SETUP.md](GOOGLE_CALENDAR_SETUP.md) for detailed instructions.

**Quick steps:**
1. Create Google Cloud project
2. Enable Calendar API
3. Set up OAuth credentials OR service account
4. Get client ID, client secret, generate encryption key

**Cost**: Free (1M requests/day)

### 7. Stripe Setup (Optional)

1. Create account at [stripe.com](https://stripe.com/)
2. Get API keys (use test mode initially)
3. Create products for subscriptions
4. Set up webhook endpoint

**Cost**: 2.9% + $0.30 per transaction

### 8. ngrok Setup

1. Create account at [ngrok.com](https://ngrok.com/)
2. Get auth token
3. Install ngrok:
   ```bash
   # macOS
   brew install ngrok
   
   # Linux
   curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | \
     sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null && \
     echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | \
     sudo tee /etc/apt/sources.list.d/ngrok.list && \
     sudo apt update && sudo apt install ngrok
   ```
4. Configure:
   ```bash
   ngrok config add-authtoken YOUR_TOKEN
   ```

**Cost**: Free tier sufficient for development

---

## Installation

### 1. Clone Repository

```bash
git clone https://github.com/stephenschoettler/frontdesk-ai.git
cd frontdesk-ai
```

### 2. Create Virtual Environment

```bash
# Create venv
python3.11 -m venv venv

# Activate (Linux/macOS)
source venv/bin/activate

# Activate (Windows)
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
# Core dependencies
pip install -r requirements.txt

# Development dependencies (optional)
pip install -r requirements-dev.txt
```

### 4. Install Supabase CLI

```bash
npm install -g supabase
```

---

## Configuration

### 1. Environment Variables

```bash
# Copy template
cp .env.example .env

# Edit with your values
nano .env  # or vim, code, etc.
```

**Required variables:**

```bash
# AI Services
DEEPGRAM_API_KEY="your_key"
DEEPGRAM_PROJECT_ID="your_project"
CARTESIA_API_KEY="your_key"
OPENROUTER_API_KEY="your_key"

# Database
SUPABASE_URL="https://yourproject.supabase.co"
SUPABASE_ANON_KEY="your_anon_key"
SUPABASE_SERVICE_ROLE_KEY="your_service_key"

# Telephony
TWILIO_ACCOUNT_SID="your_sid"
TWILIO_AUTH_TOKEN="your_token"

# Google Calendar OAuth
GOOGLE_OAUTH_CLIENT_ID="your-id.apps.googleusercontent.com"
GOOGLE_OAUTH_CLIENT_SECRET="your_secret"
CALENDAR_CREDENTIALS_ENCRYPTION_KEY="generate_with_openssl_rand_hex_32"
BASE_URL="http://localhost:8000"
```

**Generate encryption key:**
```bash
openssl rand -hex 32
```

### 2. Database Migrations

```bash
cd supabase

# Link to your project (one-time)
supabase link --project-ref your-project-id

# Run migrations
supabase db push

# Verify
supabase db diff
```

---

## First Run

### 1. Start Server

```bash
# Activate venv
source venv/bin/activate

# Start server
python main.py
```

**Expected output:**
```
INFO:     Started server process [12345]
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### 2. Start ngrok

```bash
# New terminal
ngrok http 8000
```

**Copy the https URL** (e.g., `https://abc123.ngrok-free.app`)

### 3. Configure Twilio

1. Go to Twilio Console → Phone Numbers
2. Click your phone number
3. Under "Voice Configuration":
   - Webhook: `https://abc123.ngrok-free.app/voice`
   - Method: POST
4. Save

### 4. Test Call

1. Call your Twilio number
2. Bot should greet you
3. Try: "What times are available tomorrow?"

### 5. Access Dashboard

1. Open: `http://localhost:8000`
2. Click "Sign in with Google"
3. Authorize
4. Create your first client

---

## Verification Checklist

After installation, verify:

- [ ] Server starts without errors
- [ ] Dashboard loads at localhost:8000
- [ ] Can sign in with Google
- [ ] Can create a client
- [ ] Can authorize calendar (OAuth)
- [ ] Test call connects
- [ ] Bot speaks first (initial greeting)
- [ ] Can check availability
- [ ] Can book appointment
- [ ] Appointment appears in Google Calendar
- [ ] Conversation logged in dashboard

---

## Troubleshooting

### Server won't start

**Check Python version:**
```bash
python --version  # Should be 3.11+
```

**Check dependencies:**
```bash
pip install -r requirements.txt --upgrade
```

**Check environment variables:**
```bash
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print('SUPABASE_URL:', bool(os.getenv('SUPABASE_URL')))"
```

### Database connection fails

1. Verify Supabase credentials in `.env`
2. Check project is not paused (Supabase dashboard)
3. Run migrations: `supabase db push`

### Twilio connection fails

1. Check ngrok is running and not expired
2. Verify webhook URL in Twilio console
3. Check Twilio credentials in `.env`

### Call connects but no audio

1. Check API keys (Deepgram, Cartesia)
2. View logs: `tail -f frontdesk_calls.log`
3. Verify client configuration in dashboard

### Calendar integration not working

See [GOOGLE_CALENDAR_SETUP.md](GOOGLE_CALENDAR_SETUP.md) for detailed troubleshooting.

---

## Next Steps

1. **Customize prompts** - Edit system prompt for your use case
2. **Add more clients** - Support multiple businesses
3. **Test thoroughly** - Make test calls, book appointments
4. **Deploy to production** - See [DEPLOYMENT.md](DEPLOYMENT.md)

---

## Updating

```bash
# Pull latest changes
git pull origin main

# Update dependencies
pip install -r requirements.txt --upgrade

# Run new migrations
cd supabase && supabase db push

# Restart server
python main.py
```

---

## Uninstall

```bash
# Deactivate venv
deactivate

# Remove project
cd ..
rm -rf frontdesk-ai

# Delete accounts (optional)
# - Twilio (release phone number first)
# - Supabase (delete project)
# - Other services as needed
```

---

**For production deployment, see [DEPLOYMENT.md](DEPLOYMENT.md)**

**For configuration details, see [CONFIGURATION.md](CONFIGURATION.md)**
