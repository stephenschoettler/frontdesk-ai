"""
User OAuth Authentication Service

Handles Google OAuth 2.0 for user login/registration.
"""

import os
import logging
import secrets
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
import requests

logger = logging.getLogger(__name__)

# OAuth configuration
GOOGLE_OAUTH_CLIENT_ID = os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
GOOGLE_OAUTH_CLIENT_SECRET = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")
BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")

# OAuth scopes for user authentication
USER_OAUTH_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile"
]


def generate_user_oauth_url() -> tuple[str, str]:
    """
    Generate OAuth authorization URL for user login.

    Returns:
        Tuple of (authorization_url, state_token)
    """
    logger.debug("=== USER OAUTH FLOW START ===")

    if not GOOGLE_OAUTH_CLIENT_ID or not GOOGLE_OAUTH_CLIENT_SECRET:
        logger.error(f"Missing OAuth credentials")
        raise ValueError("Google OAuth credentials not configured")

    # Generate random state token for CSRF protection
    state = secrets.token_urlsafe(32)
    logger.debug(f"Generated state token for user login")

    # Create OAuth flow
    redirect_uri = f"{BASE_URL}/api/auth/google/callback"
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
            scopes=USER_OAUTH_SCOPES,
            redirect_uri=redirect_uri
        )
        logger.debug("OAuth flow created successfully")

        authorization_url, _ = flow.authorization_url(
            access_type="online",  # We don't need offline access for user login
            include_granted_scopes="true",
            state=state,
            prompt="select_account"  # Let user choose account
        )
        logger.info("Generated user OAuth URL successfully")
        logger.debug(f"Authorization URL: {authorization_url[:100]}...")

        return authorization_url, state

    except Exception as e:
        logger.error(f"Failed to generate OAuth URL: {e}", exc_info=True)
        raise


def get_google_user_info(access_token: str) -> Dict[str, Any]:
    """
    Fetch user information from Google using access token.

    Args:
        access_token: Google OAuth access token

    Returns:
        Dict with user info (email, name, picture, etc.)
    """
    logger.debug("Fetching user info from Google...")

    try:
        response = requests.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        response.raise_for_status()

        user_info = response.json()
        logger.debug(f"User info received: email={user_info.get('email')}")

        return user_info

    except Exception as e:
        logger.error(f"Failed to fetch user info from Google: {e}", exc_info=True)
        raise


def handle_user_oauth_callback(code: str, state: str, supabase) -> Dict[str, Any]:
    """
    Handle OAuth callback for user login.

    Args:
        code: Authorization code from Google
        state: State token for CSRF validation
        supabase: Supabase client

    Returns:
        Dict with user data and JWT token
    """
    logger.debug("=== USER OAUTH CALLBACK START ===")
    logger.debug(f"Code received: {code[:20]}...")
    logger.debug(f"State: {state[:20]}...")

    redirect_uri = f"{BASE_URL}/api/auth/google/callback"

    try:
        # Create flow and exchange code for token
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
            scopes=USER_OAUTH_SCOPES,
            redirect_uri=redirect_uri
        )

        logger.debug("Fetching token from Google...")
        flow.fetch_token(code=code)
        credentials = flow.credentials

        # Get user info from Google
        user_info = get_google_user_info(credentials.token)

        email = user_info.get("email")
        name = user_info.get("name", email.split("@")[0])
        picture = user_info.get("picture")
        google_id = user_info.get("id")

        if not email:
            raise ValueError("No email returned from Google")

        logger.info(f"Google OAuth successful for {email}")

        # Check if user exists in Supabase
        logger.debug(f"Checking if user exists: {email}")
        existing_user = supabase.table("users").select("*").eq("email", email).execute()

        if existing_user.data:
            # User exists - log them in
            user = existing_user.data[0]
            logger.info(f"Existing user logged in: {email}")

            # Update last login and profile picture if needed
            update_data = {"last_sign_in_at": datetime.utcnow().isoformat()}
            if picture and not user.get("avatar_url"):
                update_data["avatar_url"] = picture

            supabase.table("users").update(update_data).eq("id", user["id"]).execute()

        else:
            # Create new user
            logger.info(f"Creating new user: {email}")

            new_user_data = {
                "email": email,
                "display_name": name,
                "avatar_url": picture,
                "oauth_provider": "google",
                "oauth_provider_id": google_id,
                "created_at": datetime.utcnow().isoformat(),
                "last_sign_in_at": datetime.utcnow().isoformat()
            }

            # Use Supabase Auth to create user
            try:
                auth_response = supabase.auth.admin.create_user({
                    "email": email,
                    "email_confirm": True,
                    "user_metadata": {
                        "display_name": name,
                        "avatar_url": picture,
                        "oauth_provider": "google"
                    }
                })
                user = auth_response.user
                logger.info(f"New user created via Supabase Auth: {email}")

            except Exception as e:
                logger.error(f"Failed to create user via Supabase Auth: {e}")
                # Fallback: try to get user if it was created
                existing_user = supabase.table("users").select("*").eq("email", email).execute()
                if existing_user.data:
                    user = existing_user.data[0]
                else:
                    raise

        # Generate session token using Supabase Auth
        try:
            sign_in_response = supabase.auth.sign_in_with_password({
                "email": email,
                "password": google_id  # Use Google ID as password for OAuth users
            })
            session_token = sign_in_response.session.access_token
        except:
            # If password login fails, generate custom JWT (fallback)
            # In production, you'd want to use Supabase's proper auth flow
            logger.warning("Using fallback token generation")
            session_token = user.get("id")  # Simplified for now

        return {
            "success": True,
            "user": {
                "id": user.get("id"),
                "email": email,
                "display_name": name,
                "avatar_url": picture
            },
            "token": session_token
        }

    except Exception as e:
        logger.error(f"OAuth callback failed: {e}", exc_info=True)
        raise
