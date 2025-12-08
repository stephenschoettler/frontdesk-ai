import os
import logging
from typing import Dict, Any, Optional

import httpx
from supabase import Client

from .supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

async def get_service_balances() -> Dict[str, Any]:
    """
    Fetches live balances from external providers.
    """
    balances: Dict[str, Any] = {}
    async with httpx.AsyncClient(timeout=10.0) as client:
        # Twilio Balance
        sid = os.getenv("TWILIO_ACCOUNT_SID")
        token = os.getenv("TWILIO_AUTH_TOKEN")
        if sid and token:
            try:
                resp = await client.get(
                    f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Balance.json",
                    auth=(sid, token),
                )
                resp.raise_for_status()
                balances["twilio"] = resp.json()
            except Exception as e:
                logger.warning(f"Twilio balance fetch failed: {e}")

        # OpenRouter Credits
        or_key = os.getenv("OPENROUTER_API_KEY")
        if or_key:
            try:
                resp = await client.get(
                    "https://openrouter.ai/api/v1/credits",
                    headers={"Authorization": f"Bearer {or_key}"},
                )
                resp.raise_for_status()
                balances["openrouter"] = resp.json()
            except Exception as e:
                logger.warning(f"OpenRouter balance fetch failed: {e}")

        # ElevenLabs Subscription
        el_key = os.getenv("XI_API_KEY") or os.getenv("ELEVENLABS_API_KEY")
        if el_key:
            try:
                resp = await client.get(
                    "https://api.elevenlabs.io/v1/user/subscription",
                    headers={"xi-api-key": el_key},
                )
                resp.raise_for_status()
                data = resp.json()
                # Map ElevenLabs API keys to our internal structure
                # Actual API returns: { "character_count": 123, "character_limit": 10000, ... }
                used = data.get("character_count", 0)
                limit = data.get("character_limit", 0)
                percent = 0
                if limit > 0:
                    percent = used / limit

                balances["elevenlabs"] = {
                    "used": used,
                    "limit": limit,
                    "percent": percent,
                }
            except Exception as e:
                logger.warning(f"ElevenLabs balance fetch failed: {e}")

        # Deepgram Balances
        dg_token = os.getenv("DEEPGRAM_API_KEY")
        project_id = os.getenv("DEEPGRAM_PROJECT_ID")
        if dg_token and project_id:
            try:
                resp = await client.get(
                    f"https://api.deepgram.com/v1/projects/{project_id}/balances",
                    headers={"Authorization": f"Token {dg_token}"},
                )
                resp.raise_for_status()
                balances["deepgram"] = resp.json()
            except Exception as e:
                logger.warning(f"Deepgram balance fetch failed: {e}")

    return balances

async def get_system_rates() -> Dict[str, float]:
    """
    Fetches system rates from DB as dict.
    """
    supabase: Optional[Client] = get_supabase_client()
    if not supabase:
        logger.warning("Supabase client unavailable")
        return {}

    try:
        resp = supabase.table("system_settings").select("key, value").execute()
        return {row["key"]: float(row["value"]) for row in resp.data or []}
    except Exception as e:
        logger.error(f"Failed to fetch system rates: {e}")
        return {}

async def update_system_rate(key: str, value: str) -> bool:
    """
    Updates/inserts a system rate in DB.
    """
    supabase: Optional[Client] = get_supabase_client()
    if not supabase:
        logger.warning("Supabase client unavailable")
        return False

    try:
        resp = supabase.table("system_settings").upsert(
            {"key": key, "value": str(value)}
        ).execute()
        logger.info(f"Updated system rate {key} = {value}")
        return bool(resp.data)
    except Exception as e:
        logger.error(f"Failed to update system rate {key}: {e}")
        return False