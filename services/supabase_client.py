import os
import logging
from typing import Any, Optional, Dict
from supabase import create_client, Client
from postgrest.exceptions import APIError

logger = logging.getLogger(__name__)


def get_supabase_client() -> Optional[Client]:
    """Initializes and returns a Supabase client, or None if keys are missing."""
    supabase_url: str = os.environ.get("SUPABASE_URL")
    supabase_key: str = os.environ.get("SUPABASE_ANON_KEY")
    if not supabase_url or not supabase_key:
        logger.error("Supabase URL or Key is missing from environment variables.")
        return None
    try:
        return create_client(supabase_url, supabase_key)
    except Exception as e:
        logger.error(f"Failed to create Supabase client: {e}")
        return None


async def get_or_create_contact(phone_number: str) -> Optional[Dict[str, Any]]:
    """
    Tries to find a contact by phone number. If not found, creates a new one.
    Returns the contact's data.
    """
    supabase = get_supabase_client()
    if not supabase:
        return None

    try:
        # 1. Try to find the contact
        response = (
            supabase.table("contacts").select("*").eq("phone", phone_number).execute()
        )

        if response.data:
            logger.info(f"Found existing contact for {phone_number}")
            return response.data[0]
        else:
            # 2. If not found, create it
            logger.info(f"No contact found for {phone_number}. Creating new contact.")
            # The .select() cannot be chained after .insert() in this version.
            # Use returning="representation" to get the inserted row back.
            insert_response = (
                supabase.table("contacts")
                .insert({"phone": phone_number}, returning="representation")
                .execute()
            )

            if insert_response.data:
                return insert_response.data[0]
            else:
                # The error attribute may not exist on all responses, so we use getattr
                error_message = getattr(insert_response, "error", "Unknown error")
                logger.error(f"Failed to create new contact: {error_message}")
                return None

    except APIError as e:
        logger.error(f"Supabase API error in get_or_create_contact: {e.body}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in get_or_create_contact: {e}")
        return None


async def log_conversation(
    contact_id: str, client_id: str, transcript: Any, summary: Optional[str] = None
):
    """
    Logs the conversation details to the 'conversations' table.
    """
    supabase = get_supabase_client()
    if not supabase:
        logger.error("Failed to log conversation, Supabase client not available.")
        return

    data_to_insert = {
        "contact_id": contact_id,
        "client_id": client_id,
        "transcript": transcript,
        "summary": summary,
    }

    try:
        response = supabase.table("conversations").insert(data_to_insert).execute()
        logger.info(f"Conversation logged successfully for contact_id {contact_id}.")
        return response
    except APIError as e:
        logger.error(f"Supabase API error logging conversation: {e}")
    except Exception as e:
        logger.error(f"Unexpected error logging conversation: {e}")


async def update_contact_name(phone_number: str, name: str) -> bool:
    """
    Updates the name of a contact identified by their phone number.
    """
    supabase = get_supabase_client()
    if not supabase:
        return False

    try:
        resp = (
            supabase.table("contacts")
            .upsert(
                {"phone": phone_number, "name": name},
                on_conflict="phone",
                returning="representation",
            )
            .execute()
        )
        if resp.data:
            logger.info(f"DB upsert success → {phone_number}: {name}")
            return True
        else:
            logger.error(f"Upsert error: {getattr(resp, 'error', 'unknown')}")
            return False
    except Exception as e:
        logger.error(f"update_contact_name exception: {e}")
        return False
