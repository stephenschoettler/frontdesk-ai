import os
import logging
import jwt
from typing import Any, Optional, Dict
from supabase import create_client as sb_create_client, Client
from supabase.lib.client_options import ClientOptions
from postgrest.exceptions import APIError

logger = logging.getLogger(__name__)


def get_supabase_client() -> Optional[Client]:
    """
    Initializes and returns a Supabase client.
    Prioritizes SUPABASE_SERVICE_ROLE_KEY (Admin) if available.
    Falls back to SUPABASE_ANON_KEY (Public) with limited permissions.
    """
    supabase_url: str = os.environ.get("SUPABASE_URL")

    # Try Service Role Key first (Bypasses RLS - for Backend use)
    supabase_key: str = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

    # Fallback to Anon Key (Subject to RLS - for Public use)
    if not supabase_key:
        supabase_key = os.environ.get("SUPABASE_ANON_KEY")

    if not supabase_url or not supabase_key:
        logger.error("Supabase URL or Key is missing from environment variables.")
        return None

    try:
        return sb_create_client(supabase_url, supabase_key)
    except Exception as e:
        logger.error(f"Failed to create Supabase client: {e}")
        return None


def get_authenticated_client(jwt_token: str) -> Optional[Client]:
    """
    Initializes and returns a Supabase client with an authenticated JWT.
    """
    supabase_url: str = os.environ.get("SUPABASE_URL")
    supabase_anon_key: str = os.environ.get("SUPABASE_ANON_KEY")

    if not supabase_url or not supabase_anon_key:
        logger.error("Supabase URL or Anon Key is missing from environment variables.")
        return None

    try:
        return sb_create_client(
            supabase_url,
            supabase_anon_key,
            options=ClientOptions(headers={"Authorization": f"Bearer {jwt_token}"}),
        )
    except Exception as e:
        logger.error(f"Failed to create authenticated Supabase client: {e}")
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
            insert_response = (
                supabase.table("contacts")
                .insert({"phone": phone_number}, returning="representation")
                .execute()
            )

            if insert_response.data:
                return insert_response.data[0]
            else:
                error_message = getattr(insert_response, "error", "Unknown error")
                logger.error(f"Failed to create new contact: {error_message}")
                return None

    except APIError as e:
        logger.error(f"Supabase API error in get_or_create_contact: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in get_or_create_contact: {e}")
        return None


async def get_client_config(client_id: str) -> Optional[Dict[str, Any]]:
    """
    Fetches the configuration for a client by their ID.
    """
    supabase = get_supabase_client()
    if not supabase:
        return None

    try:
        response = supabase.table("clients").select("*").eq("id", client_id).execute()

        if response.data:
            logger.info(f"Found client config for {client_id}")
            return response.data[0]
        else:
            logger.error(f"No client found for ID: {client_id}")
            return None

    except APIError as e:
        logger.error(f"Supabase API error in get_client_config: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in get_client_config: {e}")
        return None


async def log_conversation(
    contact_id: str, client_id: str, transcript: Any, summary: Optional[str] = None, duration: Optional[int] = None
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

    if duration is not None:
        data_to_insert["duration"] = duration

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


async def get_all_clients(jwt_token: str) -> Optional[list[Dict[str, Any]]]:
    """
    Fetches all client configurations for the authenticated user.
    """
    supabase = get_authenticated_client(jwt_token)
    if not supabase:
        return None

    try:
        response = supabase.table("clients").select("*").execute()
        if response.data:
            logger.info(f"Fetched {len(response.data)} clients")
            return response.data
        else:
            logger.info("No clients found")
            return []
    except APIError as e:
        logger.error(f"Supabase API error in get_all_clients: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in get_all_clients: {e}")
        return None


async def create_client_record(
    client_data: Dict[str, Any], jwt_token: str
) -> Optional[Dict[str, Any]]:
    """
    Creates a new client configuration for the authenticated user.
    """
    supabase = get_supabase_client()  # service role bypasses RLS
    if not supabase:
        return None

    payload = jwt.decode(jwt_token, options={"verify_signature": False})
    user_id = payload['sub']
    client_data = client_data.copy()
    client_data['owner_user_id'] = user_id

    try:
        response = (
            supabase.table("clients")
            .insert(client_data, returning="representation")
            .execute()
        )
        if response.data:
            logger.info(f"Created new client: {response.data[0]['id']}")
            return response.data[0]
        else:
            logger.error("Failed to create client")
            return None
    except APIError as e:
        logger.error(f"Supabase API error in create_client: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in create_client: {e}")
        return None


async def update_client(
    client_id: str, client_data: Dict[str, Any], jwt_token: str
) -> Optional[Dict[str, Any]]:
    """
    Updates an existing client configuration for the authenticated user.
    """
    supabase = get_supabase_client()  # service role bypasses RLS
    if not supabase:
        return None

    try:
        response = (
            supabase.table("clients")
            .update(client_data, returning="representation")
            .eq("id", client_id)
            .execute()
        )
        if response.data:
            logger.info(f"Updated client: {client_id}")
            return response.data[0]
        else:
            logger.error(f"Failed to update client: {client_id}")
            return None
    except APIError as e:
        logger.error(f"Supabase API error in update_client: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in update_client: {e}")
        return None


async def delete_client(client_id: str, jwt_token: str) -> bool:
    """
    Deletes a client configuration for the authenticated user.
    """
    supabase = get_supabase_client()  # service role bypasses RLS
    if not supabase:
        return False

    try:
        response = supabase.table("clients").delete().eq("id", client_id).execute()
        if response.data:
            logger.info(f"Deleted client: {client_id}")
            return True
        else:
            logger.error(f"Failed to delete client: {client_id}")
            return False
    except APIError as e:
        logger.error(f"Supabase API error in delete_client: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error in delete_client: {e}")
        return False


async def get_all_contacts() -> Optional[list[Dict[str, Any]]]:
    """
    Retrieves all contacts along with their last contact timestamp.
    """
    supabase = get_supabase_client()
    if not supabase:
        return None

    try:
        # Fetch all contacts
        contacts_response = supabase.table("contacts").select("*").execute()
        if not contacts_response.data:
            logger.info("No contacts found.")
            return []

        contacts = contacts_response.data
        contact_ids = [contact["id"] for contact in contacts]

        conversations_response = (
            supabase.table("conversations")
            .select("contact_id, created_at")
            .in_("contact_id", contact_ids)
            .order("created_at", desc=True)
            .execute()
        )

        last_contact_map = {}
        for conv in conversations_response.data:
            contact_id = conv["contact_id"]
            if contact_id not in last_contact_map:
                last_contact_map[contact_id] = conv["created_at"]

        # Add last_contact to each contact
        for contact in contacts:
            contact["last_contact"] = last_contact_map.get(contact["id"])

        logger.info(f"Fetched {len(contacts)} contacts with last contact info.")
        return contacts
    except APIError as e:
        logger.error(f"Supabase API error in get_all_contacts: {e.body}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in get_all_contacts: {e}")
        return None


async def get_conversation_logs() -> Optional[list[Dict[str, Any]]]:
    """
    Retrieves all conversation logs, ordered by creation time.
    """
    supabase = get_supabase_client()
    if not supabase:
        return None

    try:
        response = (
            supabase.table("conversations")
            .select("*, clients(name), contacts(phone)")
            .order("created_at", desc=True)
            .execute()
        )
        if response.data:
            flat_data = []
            for row in response.data:
                client_name = "N/A"
                clients_data = row.get("clients")
                if clients_data:
                    client_name = clients_data.get("name", "N/A")

                phone = "N/A"
                contacts_data = row.get("contacts")
                if contacts_data:
                    phone = contacts_data.get("phone", "N/A")

                flat_row = {
                    "id": row.get("id"),
                    "timestamp": row.get("created_at"),
                    "client_id": row.get("client_id"),
                    "client_name": client_name,
                    "contact_id": row.get("contact_id"),
                    "phone": phone,
                    "transcript": row.get("transcript"),
                    "summary": row.get("summary"),
                    "duration": row.get("duration", 0),
                    "status": row.get("status", "completed"),
                }
                flat_data.append(flat_row)
            logger.info(f"Fetched and flattened {len(flat_data)} conversation logs.")
            return flat_data
        else:
            logger.info("No conversation logs found.")
            return []
    except APIError as e:
        logger.error(f"Supabase API error in get_conversation_logs: {e.body}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in get_conversation_logs: {e}")
        return None


async def get_conversation_by_id(conversation_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves a single conversation log by its ID.
    """
    supabase = get_supabase_client()
    if not supabase:
        return None

    try:
        response = (
            supabase.table("conversations")
            .select("*")
            .eq("id", conversation_id)
            .execute()
        )
        if response.data:
            logger.info(f"Fetched conversation {conversation_id}.")
            return response.data[0]
        else:
            logger.info(f"No conversation found with ID: {conversation_id}.")
            return None
    except APIError as e:
        logger.error(f"Supabase API error in get_conversation_by_id: {e.body}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in get_conversation_by_id: {e}")
        return None


async def delete_conversation(conversation_id: str, jwt_token: str) -> bool:
    """
    Deletes a conversation log for the authenticated user.
    """
    supabase = get_authenticated_client(jwt_token)
    if not supabase:
        return False

    try:
        response = supabase.table("conversations").delete().eq("id", conversation_id).execute()
        if response.data:
            logger.info(f"Deleted conversation: {conversation_id}")
            return True
        else:
            logger.error(f"Failed to delete conversation: {conversation_id}")
            return False
    except APIError as e:
        logger.error(f"Supabase API error in delete_conversation: {e.body}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error in delete_conversation: {e}")
        return False


async def get_client_by_phone(phone_number: str) -> Optional[Dict[str, Any]]:
    """
    Finds a client record where the 'cell' column matches the provided phone number.
    """
    supabase = get_supabase_client()
    if not supabase:
        return None

    try:
        response = (
            supabase.table("clients").select("*").eq("cell", phone_number).execute()
        )

        if response.data:
            logger.info(
                f"Routing call to client: {response.data[0]['name']} ({response.data[0]['id']})"
            )
            return response.data[0]
        else:
            logger.warning(f"No client found for incoming number: {phone_number}")
            return None

    except Exception as e:
        logger.error(f"Error looking up client by phone: {e}")
        return None
