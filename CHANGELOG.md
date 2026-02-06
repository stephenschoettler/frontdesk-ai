# Changelog

All notable changes to FrontDesk AI will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Comprehensive documentation (README, FEATURES, ARCHITECTURE, CONTRIBUTING)
- Initial greeting system with automatic bot-first speaking
- Action narration in system prompts ("Let me check the calendar...")
- Complete conversation logging to database with timestamps
- MIT License

### Changed
- Updated README with all current features
- Enhanced .env.example with detailed documentation
- Improved initial greeting timing (1 second delay)

## [0.3.0] - 2026-02-06

### Added
- **Cartesia TTS Integration** - Added Cartesia as TTS provider (default, 5x cheaper than ElevenLabs)
- **Cartesia Voice Presets** - 19 voice options for Cartesia provider
- **TTS Provider Selection** - Per-client UI to choose between Cartesia and ElevenLabs
- **Dynamic Voice Dropdown** - Voice options automatically switch based on selected TTS provider
- **Cost Comparison** - UI shows cost difference ($0.05/min vs $0.24/min)

### Changed
- Defaulted tts_provider to 'cartesia' for new clients
- Updated client edit form with TTS provider selector
- Added pipecat-ai[cartesia] dependency

### Fixed
- Initial greeting now works correctly - bot speaks first without waiting for user

## [0.2.0] - 2026-02-05

### Added
- **Google Calendar OAuth 2.0** - Per-client calendar authorization
- **Service Account Upload** - BYOK (Bring Your Own Key) for advanced users
- **Calendar Credentials Encryption** - AES-256-GCM encryption for stored credentials
- **OAuth State Tokens** - CSRF protection for OAuth flows
- **Calendar Auth UI** - Status indicators, authorize buttons, revoke functionality
- **User Google OAuth** - "Sign in with Google" for user authentication
- **Automatic Token Refresh** - OAuth tokens refresh automatically when expired

### Database Changes
- Added `calendar_credentials` table
- Added `oauth_state_tokens` table
- Added encryption/decryption functions (pgcrypto)
- Added RLS policies for credential access

### New API Endpoints
- `POST /api/clients/{id}/calendar/oauth/initiate` - Start OAuth flow
- `GET /api/calendar/oauth/callback` - OAuth callback handler
- `GET /api/clients/{id}/calendar/status` - Get credential status
- `DELETE /api/clients/{id}/calendar/credentials` - Revoke credentials
- `POST /api/clients/{id}/calendar/service-account` - Upload service account
- `POST /auth/google/initiate` - User OAuth initiate
- `GET /auth/google/callback` - User OAuth callback

### Changed
- Modified `services/google_calendar.py` - Now accepts client_id parameter
- Updated all calendar functions to support per-client credentials
- Modified tool handlers to pass client_id through
- Calendar credential priority: Client OAuth → Client Service Account → Global Fallback

## [0.1.0] - 2026-01-15

### Added
- **Initial Release** - Core AI receptionist functionality
- **Multi-Client Support** - Full multi-tenant architecture
- **Real-time Voice** - Twilio + Pipecat + Deepgram + ElevenLabs
- **Calendar Integration** - Google Calendar via Service Account
- **Appointment Booking** - Check availability, book, reschedule, cancel
- **Contact Management** - Automatic caller identification and history
- **Conversation Logging** - Full transcripts with timestamps
- **Web Dashboard** - Vue.js 3 frontend for client management
- **Stripe Billing** - Subscription plans and usage-based billing
- **Active Call Monitoring** - Real-time dashboard of ongoing calls
- **Call Logs** - Historical call data and transcripts

### Core Features
- LLM tool system with 6 calendar/contact tools
- Customizable system prompts per client
- Per-client voice selection (ElevenLabs)
- Per-client LLM model selection (via OpenRouter)
- Balance tracking and per-second billing
- Row Level Security (RLS) for data isolation
- JWT authentication for users

### Database Schema
- `users` - User accounts
- `clients` - Client configurations
- `contacts` - Caller information
- `conversations` - Call transcripts and history
- Complete RLS policies

### API Endpoints
- Client CRUD operations
- Contact management
- Conversation retrieval
- Active call monitoring
- Twilio voice webhook
- Stripe webhook

## [0.0.1] - 2025-12-01

### Added
- Initial project setup
- Basic FastAPI server
- Supabase connection
- Twilio integration prototype
- Pipecat pipeline setup

---

## Version Numbering

- **Major** (X.0.0) - Breaking changes, major features
- **Minor** (0.X.0) - New features, backward compatible
- **Patch** (0.0.X) - Bug fixes, minor improvements

## Categories

- **Added** - New features
- **Changed** - Changes to existing functionality
- **Deprecated** - Soon-to-be removed features
- **Removed** - Removed features
- **Fixed** - Bug fixes
- **Security** - Security improvements

---

[Unreleased]: https://github.com/stephenschoettler/frontdesk-ai/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/stephenschoettler/frontdesk-ai/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/stephenschoettler/frontdesk-ai/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/stephenschoettler/frontdesk-ai/compare/v0.0.1...v0.1.0
[0.0.1]: https://github.com/stephenschoettler/frontdesk-ai/releases/tag/v0.0.1
