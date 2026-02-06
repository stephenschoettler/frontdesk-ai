"""
Google Calendar Authentication Service

Handles OAuth 2.0 and Service Account credential management for per-client calendar authentication.
All credentials are encrypted using pgcrypto before storage in the database.
"""

import os
import logging
import secrets
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import json

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from supabase import Client

logger = logging.getLogger(__name__)

# Set up file logging for debugging
log_file = os.path.join(os.path.dirname(__file__), "..", "calendar_oauth.log")
file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
logger.setLevel(logging.DEBUG)

# OAuth 2.0 scopes for Google Calendar
OAUTH_SCOPES = ["https://www.googleapis.com/auth/calendar"]

# Encryption key from environment (must be 32-byte hex string)
ENCRYPTION_KEY = os.environ.get("CALENDAR_CREDENTIALS_ENCRYPTION_KEY")

# OAuth client configuration
GOOGLE_OAUTH_CLIENT_ID = os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
GOOGLE_OAUTH_CLIENT_SECRET = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")
BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")


def _get_encryption_key() -> str:
    """Get and validate encryption key from environment."""
    if not ENCRYPTION_KEY:
        raise ValueError("CALENDAR_CREDENTIALS_ENCRYPTION_KEY not set in environment")
    return ENCRYPTION_KEY


async def encrypt_data(supabase: Client, data: str) -> str:
    """
    Encrypt sensitive data using PostgreSQL's pgcrypto.

    Args:
        supabase: Supabase client
        data: Plain text data to encrypt

    Returns:
        Encrypted data as text
    """
    try:
        key = _get_encryption_key()
        # Use pgcrypto's encrypt function via RPC
        result = supabase.rpc(
            "encrypt_secret",
            {"secret": data, "key": key}
        ).execute()
        return result.data
    except Exception as e:
        logger.error(f"Failed to encrypt data: {e}")
        raise


async def decrypt_data(supabase: Client, encrypted_data: str) -> str:
    """
    Decrypt sensitive data using PostgreSQL's pgcrypto.

    Args:
        supabase: Supabase client
        encrypted_data: Encrypted data

    Returns:
        Decrypted plain text data
    """
    try:
        key = _get_encryption_key()
        # Use pgcrypto's decrypt function via RPC
        result = supabase.rpc(
            "decrypt_secret",
            {"encrypted_data": encrypted_data, "key": key}
        ).execute()
        return result.data
    except Exception as e:
        logger.error(f"Failed to decrypt data: {e}")
        raise


def generate_oauth_url(
    client_id: str,
    user_id: str,
    supabase: Client
) -> tuple[str, str]:
    """
    Generate OAuth authorization URL for Google Calendar access.

    Args:
        client_id: Client UUID
        user_id: User UUID initiating the OAuth flow
        supabase: Supabase client

    Returns:
        Tuple of (authorization_url, state_token)
    """
    logger.debug(f"=== OAUTH FLOW START ===")
    logger.debug(f"Client ID: {client_id}")
    logger.debug(f"User ID: {user_id}")

    if not GOOGLE_OAUTH_CLIENT_ID or not GOOGLE_OAUTH_CLIENT_SECRET:
        logger.error(f"Missing OAuth credentials - CLIENT_ID: {bool(GOOGLE_OAUTH_CLIENT_ID)}, SECRET: {bool(GOOGLE_OAUTH_CLIENT_SECRET)}")
        raise ValueError("Google OAuth credentials not configured in environment")

    logger.debug(f"OAuth Client ID configured: {GOOGLE_OAUTH_CLIENT_ID[:20]}...")
    logger.debug(f"BASE_URL: {BASE_URL}")

    # Generate random state token for CSRF protection
    state = secrets.token_urlsafe(32)
    logger.debug(f"Generated state token: {state[:20]}...")

    # Store state token in database
    expires_at = datetime.utcnow() + timedelta(minutes=10)
    try:
        result = supabase.table("oauth_state_tokens").insert({
            "state": state,
            "client_id": client_id,
            "user_id": user_id,
            "expires_at": expires_at.isoformat()
        }).execute()
        logger.debug(f"State token stored in Supabase successfully")
    except Exception as e:
        logger.error(f"Failed to store state token in Supabase: {e}")
        raise

    # Create OAuth flow with generic callback (client_id stored in state token)
    redirect_uri = f"{BASE_URL}/api/calendar/oauth/callback"
    logger.debug(f"Redirect URI: {redirect_uri}")

    try:
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": GOOGLE_OAUTH_CLIENT_ID,
                    "client_secret": GOOGLE_OAUTH_CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [redirect_uri]
                }
            },
            scopes=OAUTH_SCOPES,
            redirect_uri=redirect_uri
        )
        logger.debug(f"OAuth Flow created successfully")
    except Exception as e:
        logger.error(f"Failed to create OAuth Flow: {e}")
        raise

    try:
        authorization_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            state=state,
            prompt="consent"  # Force consent to get refresh token
        )
        logger.info(f"Generated OAuth URL successfully for client {client_id}")
        logger.debug(f"Authorization URL: {authorization_url[:100]}...")
    except Exception as e:
        logger.error(f"Failed to generate authorization URL: {e}")
        raise

    return authorization_url, state


async def handle_oauth_callback(
    code: str,
    state: str,
    client_id: str,
    supabase: Client
) -> Dict[str, Any]:
    """
    Handle OAuth callback, exchange code for tokens, and store credentials.

    Args:
        code: Authorization code from Google
        state: State token for CSRF validation
        client_id: Client UUID
        supabase: Supabase client

    Returns:
        Dict with success status and credential info
    """
    logger.debug(f"=== OAUTH CALLBACK START ===")
    logger.debug(f"Code received: {code[:20]}...")
    logger.debug(f"State: {state[:20]}...")
    logger.debug(f"Client ID: {client_id}")

    # Validate state token
    logger.debug(f"Validating state token...")
    state_record = supabase.table("oauth_state_tokens").select("*").eq("state", state).execute()
    logger.debug(f"State record found: {bool(state_record.data)}")

    if not state_record.data:
        logger.error("Invalid state token - not found in database")
        raise ValueError("Invalid state token")

    state_data = state_record.data[0]
    logger.debug(f"State data: client_id={state_data['client_id']}, used={state_data['used']}")

    # Check if already used
    if state_data["used"]:
        logger.error("State token already used")
        raise ValueError("State token already used")

    # Check if expired
    expires_at = datetime.fromisoformat(state_data["expires_at"].replace("Z", "+00:00"))
    if datetime.utcnow().replace(tzinfo=expires_at.tzinfo) > expires_at:
        logger.error(f"State token expired: {expires_at}")
        raise ValueError("State token expired")

    # Validate client_id matches
    if state_data["client_id"] != client_id:
        logger.error(f"Client ID mismatch: expected {client_id}, got {state_data['client_id']}")
        raise ValueError("Client ID mismatch")

    # Mark state token as used
    logger.debug("Marking state token as used...")
    supabase.table("oauth_state_tokens").update({"used": True}).eq("state", state).execute()

    # Exchange code for tokens
    redirect_uri = f"{BASE_URL}/api/calendar/oauth/callback"
    logger.debug(f"Exchange code for tokens with redirect_uri: {redirect_uri}")

    try:
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": GOOGLE_OAUTH_CLIENT_ID,
                    "client_secret": GOOGLE_OAUTH_CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [redirect_uri]
                }
            },
            scopes=OAUTH_SCOPES,
            redirect_uri=redirect_uri
        )
        logger.debug("OAuth flow created for token exchange")

        logger.debug("Fetching token from Google...")
        flow.fetch_token(code=code)
        credentials = flow.credentials
        logger.debug(f"Token received - has refresh_token: {bool(credentials.refresh_token)}")

    except Exception as e:
        logger.error(f"Failed to exchange code for token: {e}", exc_info=True)
        raise

    # Encrypt tokens before storage
    logger.debug("Encrypting tokens...")
    try:
        encrypted_access_token = await encrypt_data(supabase, credentials.token)
        encrypted_refresh_token = await encrypt_data(supabase, credentials.refresh_token) if credentials.refresh_token else None
        logger.debug("Tokens encrypted successfully")
    except Exception as e:
        logger.error(f"Failed to encrypt tokens: {e}", exc_info=True)
        raise

    # Deactivate any existing credentials for this client
    logger.debug("Deactivating old credentials...")
    try:
        supabase.table("calendar_credentials").update(
            {"is_active": False}
        ).eq("client_id", client_id).eq("is_active", True).execute()
        logger.debug("Old credentials deactivated")
    except Exception as e:
        logger.warning(f"Failed to deactivate old credentials (may not exist): {e}")

    # Store new credentials
    logger.debug("Storing new credentials...")
    credential_data = {
        "client_id": client_id,
        "credential_type": "oauth",
        "oauth_access_token": encrypted_access_token,
        "oauth_refresh_token": encrypted_refresh_token,
        "oauth_token_expiry": credentials.expiry.isoformat() if credentials.expiry else None,
        "oauth_scopes": credentials.scopes,
        "created_by_user_id": state_data["user_id"],
        "is_active": True
    }

    try:
        result = supabase.table("calendar_credentials").insert(credential_data).execute()
        logger.info(f"Successfully stored OAuth credentials for client {client_id}")
        logger.debug(f"Credential ID: {result.data[0]['id']}")

        return {
            "success": True,
            "credential_id": result.data[0]["id"],
            "credential_type": "oauth"
        }
    except Exception as e:
        logger.error(f"Failed to store credentials in database: {e}", exc_info=True)
        raise


async def upload_service_account(
    client_id: str,
    user_id: str,
    service_account_json: str,
    supabase: Client
) -> Dict[str, Any]:
    """
    Upload and store service account credentials for a client.

    Args:
        client_id: Client UUID
        user_id: User UUID uploading the credential
        service_account_json: Service account JSON key file content
        supabase: Supabase client

    Returns:
        Dict with success status and service account email
    """
    # Validate JSON structure
    try:
        sa_data = json.loads(service_account_json)
        required_fields = ["type", "project_id", "private_key_id", "private_key", "client_email"]

        for field in required_fields:
            if field not in sa_data:
                raise ValueError(f"Missing required field: {field}")

        if sa_data["type"] != "service_account":
            raise ValueError("Invalid service account type")

        service_account_email = sa_data["client_email"]

    except json.JSONDecodeError:
        raise ValueError("Invalid JSON format")
    except Exception as e:
        raise ValueError(f"Invalid service account JSON: {e}")

    # Encrypt service account JSON
    encrypted_json = await encrypt_data(supabase, service_account_json)

    # Deactivate any existing credentials for this client
    supabase.table("calendar_credentials").update(
        {"is_active": False}
    ).eq("client_id", client_id).eq("is_active", True).execute()

    # Store new credentials
    credential_data = {
        "client_id": client_id,
        "credential_type": "service_account",
        "service_account_json": encrypted_json,
        "service_account_email": service_account_email,
        "created_by_user_id": user_id,
        "is_active": True
    }

    result = supabase.table("calendar_credentials").insert(credential_data).execute()

    logger.info(f"Successfully stored service account credentials for client {client_id}")

    return {
        "success": True,
        "credential_id": result.data[0]["id"],
        "credential_type": "service_account",
        "service_account_email": service_account_email
    }


async def get_calendar_credentials(
    client_id: str,
    supabase: Client
) -> Optional[Dict[str, Any]]:
    """
    Retrieve active calendar credentials for a client.

    Args:
        client_id: Client UUID
        supabase: Supabase client

    Returns:
        Dict with decrypted credential data, or None if no credentials exist
    """
    # Query active credentials
    result = supabase.table("calendar_credentials").select("*").eq(
        "client_id", client_id
    ).eq("is_active", True).execute()

    if not result.data:
        return None

    cred = result.data[0]

    # Update last_used_at
    supabase.table("calendar_credentials").update(
        {"last_used_at": datetime.utcnow().isoformat()}
    ).eq("id", cred["id"]).execute()

    # Decrypt based on credential type
    if cred["credential_type"] == "oauth":
        access_token = await decrypt_data(supabase, cred["oauth_access_token"])
        refresh_token = await decrypt_data(supabase, cred["oauth_refresh_token"]) if cred["oauth_refresh_token"] else None

        return {
            "id": cred["id"],
            "credential_type": "oauth",
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_expiry": cred["oauth_token_expiry"],
            "scopes": cred["oauth_scopes"]
        }

    elif cred["credential_type"] == "service_account":
        sa_json = await decrypt_data(supabase, cred["service_account_json"])

        return {
            "id": cred["id"],
            "credential_type": "service_account",
            "service_account_json": sa_json,
            "service_account_email": cred["service_account_email"]
        }

    return None


async def refresh_oauth_token(
    credential_id: str,
    supabase: Client
) -> Credentials:
    """
    Refresh an expired OAuth token.

    Args:
        credential_id: Calendar credential UUID
        supabase: Supabase client

    Returns:
        Updated Credentials object
    """
    # Get credential record
    result = supabase.table("calendar_credentials").select("*").eq("id", credential_id).execute()

    if not result.data:
        raise ValueError("Credential not found")

    cred = result.data[0]

    if cred["credential_type"] != "oauth":
        raise ValueError("Not an OAuth credential")

    # Decrypt tokens
    access_token = await decrypt_data(supabase, cred["oauth_access_token"])
    refresh_token = await decrypt_data(supabase, cred["oauth_refresh_token"]) if cred["oauth_refresh_token"] else None

    # Create Credentials object
    credentials = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=GOOGLE_OAUTH_CLIENT_ID,
        client_secret=GOOGLE_OAUTH_CLIENT_SECRET,
        scopes=cred["oauth_scopes"]
    )

    # Refresh the token
    credentials.refresh(Request())

    # Encrypt new tokens
    encrypted_access_token = await encrypt_data(supabase, credentials.token)
    encrypted_refresh_token = await encrypt_data(supabase, credentials.refresh_token) if credentials.refresh_token else None

    # Update database
    supabase.table("calendar_credentials").update({
        "oauth_access_token": encrypted_access_token,
        "oauth_refresh_token": encrypted_refresh_token,
        "oauth_token_expiry": credentials.expiry.isoformat() if credentials.expiry else None,
        "updated_at": datetime.utcnow().isoformat()
    }).eq("id", credential_id).execute()

    logger.info(f"Successfully refreshed OAuth token for credential {credential_id}")

    return credentials


async def revoke_credentials(
    client_id: str,
    user_id: str,
    supabase: Client
) -> bool:
    """
    Revoke and delete calendar credentials for a client.

    Args:
        client_id: Client UUID
        user_id: User UUID requesting revocation
        supabase: Supabase client

    Returns:
        True if successfully revoked
    """
    # Get active credentials
    result = supabase.table("calendar_credentials").select("*").eq(
        "client_id", client_id
    ).eq("is_active", True).execute()

    if not result.data:
        logger.info(f"No active credentials found for client {client_id}")
        return True

    cred = result.data[0]

    # If OAuth, try to revoke the token with Google
    if cred["credential_type"] == "oauth" and cred["oauth_refresh_token"]:
        try:
            refresh_token = await decrypt_data(supabase, cred["oauth_refresh_token"])
            credentials = Credentials(
                token=None,
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=GOOGLE_OAUTH_CLIENT_ID,
                client_secret=GOOGLE_OAUTH_CLIENT_SECRET
            )
            credentials.revoke(Request())
            logger.info(f"Revoked OAuth token with Google for client {client_id}")
        except Exception as e:
            logger.warning(f"Failed to revoke OAuth token with Google: {e}")

    # Delete from database
    supabase.table("calendar_credentials").delete().eq("id", cred["id"]).execute()

    logger.info(f"Deleted calendar credentials for client {client_id}")
    return True
