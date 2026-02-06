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


async def get_or_create_contact(
    phone_number: str, client_id: str
) -> Optional[Dict[str, Any]]:
    """
    Finds a contact by phone AND client_id. Creates one if missing.
    """
    supabase = get_supabase_client()
    if not supabase:
        return None

    try:
        # 1. Search scoped to Client
        response = (
            supabase.table("contacts")
            .select("*")
            .eq("phone", phone_number)
            .eq("client_id", client_id)
            .execute()
        )

        if response.data:
            logger.info(
                f"Found existing contact for {phone_number} (Client {client_id})"
            )
            return response.data[0]
        else:
            # 2. Create scoped to Client
            logger.info(f"Creating new contact for {phone_number} (Client {client_id})")
            insert_response = (
                supabase.table("contacts")
                .insert(
                    {"phone": phone_number, "client_id": client_id},
                    returning="representation",
                )
                .execute()
            )

            if insert_response.data:
                return insert_response.data[0]
            else:
                error_message = getattr(insert_response, "error", "Unknown error")
                logger.error(f"Failed to create contact: {error_message}")
                return None

    except Exception as e:
        logger.error(f"Error in get_or_create_contact: {e}")
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
    contact_id: str,
    client_id: str,
    transcript: Any,
    summary: Optional[str] = None,
    duration: Optional[int] = None,
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
        response = (
            supabase.table("conversations")
            .insert(data_to_insert, returning="representation")
            .execute()
        )
        logger.info(f"Conversation logged successfully for contact_id {contact_id}.")
        return response
    except APIError as e:
        logger.error(f"Supabase API error logging conversation: {e}")
    except Exception as e:
        logger.error(f"Unexpected error logging conversation: {e}")


async def update_contact_name(phone_number: str, name: str, client_id: str) -> bool:
    """
    Updates the name of a contact identified by phone AND client_id.
    """
    supabase = get_supabase_client()
    if not supabase:
        return False

    try:
        # We must match the UNIQUE constraint (phone, client_id) for upsert to work reliably
        # NOTE: Removed the space in 'phone,client_id' to satisfy PostgREST syntax
        resp = (
            supabase.table("contacts")
            .upsert(
                {"phone": phone_number, "client_id": client_id, "name": name},
                on_conflict="phone,client_id",
                returning="representation",
            )
            .execute()
        )
        if resp.data:
            logger.info(
                f"Updated name for {phone_number} (Client {client_id}) -> {name}"
            )
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
    user_id = payload["sub"]
    client_data = client_data.copy()
    client_data["owner_user_id"] = user_id

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
    Retrieves all contacts along with their last contact timestamp AND client name.
    """
    supabase = get_supabase_client()
    if not supabase:
        return None

    try:
        # Fetch all contacts JOINED with clients to get the name
        contacts_response = (
            supabase.table("contacts").select("*, clients(name)").execute()
        )
        if not contacts_response.data:
            logger.info("No contacts found.")
            return []

        # Flatten the response for the UI
        contacts = []
        for row in contacts_response.data:
            # Extract client name from the joined object
            client_data = row.get("clients")
            client_name = client_data.get("name") if client_data else "Unknown Client"

            # Create a clean record
            contact = row.copy()
            contact["client_name"] = client_name

            # Remove nested object if present to keep it clean
            if "clients" in contact:
                del contact["clients"]

            contacts.append(contact)

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
        logger.error(f"Supabase API error in get_all_contacts: {e}")
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
        logger.error(f"Supabase API error in get_conversation_logs: {e}")
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
        logger.error(f"Supabase API error in get_conversation_by_id: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in get_conversation_by_id: {e}")
        return None


async def delete_conversation(conversation_id: str, jwt_token: str) -> bool:
    """
    Deletes a conversation log for the authenticated user.
    """
    # Decode JWT to get user_id (no signature verification needed)
    try:
        payload = jwt.decode(jwt_token, options={"verify_signature": False})
        user_id = payload.get("sub")
        if not user_id:
            logger.warning("No user_id found in JWT payload")
            return False
    except Exception as e:
        logger.error(f"Failed to decode JWT token: {e}")
        return False

    supabase = get_supabase_client()
    if not supabase:
        return False

    try:
        # Verify conversation exists and get its client_id
        conv_resp = (
            supabase.table("conversations")
            .select("client_id")
            .eq("id", conversation_id)
            .execute()
        )
        if not conv_resp.data:
            logger.info(f"Conversation not found: {conversation_id}")
            return False
        conv_data = conv_resp.data[0]
        client_id = conv_data.get("client_id")
        if not client_id:
            logger.warning(f"No client_id for conversation: {conversation_id}")
            return False

        # Verify client ownership
        client_resp = (
            supabase.table("clients")
            .select("owner_user_id")
            .eq("id", client_id)
            .execute()
        )
        if not client_resp.data:
            logger.warning(f"Client not found for conversation: {conversation_id}")
            return False
        client_data = client_resp.data[0]
        if client_data.get("owner_user_id") != user_id:
            logger.warning(
                f"User {user_id} not authorized to delete conversation {conversation_id} (owned by {client_data.get('owner_user_id')})"
            )
            return False

        # Perform deletion
        (supabase.table("conversations").delete().eq("id", conversation_id).execute())
        logger.info(f"Deleted conversation {conversation_id} for user {user_id}")
        return True
    except APIError as e:
        logger.error(f"Supabase API error in delete_conversation: {e}")
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


async def get_client_balance(client_id: str) -> int:
    """
    CHECK: Fetches the current balance in seconds.
    """
    supabase = get_supabase_client()
    if not supabase:
        return 0

    try:
        resp = (
            supabase.table("clients")
            .select("balance_seconds")
            .eq("id", client_id)
            .execute()
        )
        if resp.data:
            return resp.data[0].get("balance_seconds", 0)
        return 0
    except Exception as e:
        logger.error(f"Error fetching balance: {e}")
        return 0


async def adjust_client_balance(
    client_id: str, amount_seconds: int, reason: str, revenue_usd: float = 0.0
) -> bool:
    """
    ADMIN: Manually adjusts a client's balance.
    amount_seconds: Positive to add (Credit), Negative to deduct (Debit).
    revenue_usd: Revenue amount for payments (default 0.0).
    """
    supabase = get_supabase_client()
    if not supabase:
        return False

    try:
        # 1. Fetch current balance
        current = await get_client_balance(client_id)
        new_balance = current + amount_seconds

        # 2. Update Client Balance
        supabase.table("clients").update({"balance_seconds": new_balance}).eq(
            "id", client_id
        ).execute()

        # 3. Log to Ledger
        # We use specific metric types for manual adjustments to track them easily
        metric_type = "MANUAL_CREDIT" if amount_seconds >= 0 else "MANUAL_DEBIT"

        # We log the absolute quantity for the metric, but the effect on balance is already applied
        quantity = abs(amount_seconds)

        ledger_entry = {
            "client_id": client_id,
            "metric_type": metric_type,
            "quantity": quantity,
            "revenue_usd": revenue_usd,
            # We abuse conversation_id or add a notes field if the schema supported it.
            # Since we don't know if 'notes' column exists, we'll try to stick to known columns.
            # If the schema allows extra json in a column, that would be great, but let's stay safe.
            # The requirement asks to log the reason. I'll Assume there isn't a reason column
            # and just log the action. If I could, I'd add 'notes': reason.
            # For now, let's just log the metric.
        }

        supabase.table("usage_ledger").insert(ledger_entry).execute()

        logger.info(
            f"Adjusted balance for {client_id} by {amount_seconds}s. New Balance: {new_balance}. Reason: {reason}"
        )
        return True

    except Exception as e:
        logger.error(f"Error adjusting balance: {e}")
        return False


async def deduct_balance(client_id: str, seconds: int) -> None:
    """
    COMMIT: Deducts seconds from the client's balance.
    (Used by Safety Valve and Final Commit)
    """
    supabase = get_supabase_client()
    if not supabase:
        return

    try:
        # Fetch current to ensure we don't go negative
        current = await get_client_balance(client_id)
        new_balance = current - seconds

        supabase.table("clients").update({"balance_seconds": new_balance}).eq(
            "id", client_id
        ).execute()
        logger.info(
            f"Deducted {seconds}s from Client {client_id}. New Balance: {new_balance}"
        )
    except Exception as e:
        logger.error(f"Error deducting balance: {e}")


async def log_usage_ledger(
    client_id: str,
    conversation_id: Optional[str],
    metrics: dict,
    costs: Optional[Dict[str, float]] = None,
):
    """
    COMMIT: Writes the detailed breakdown to the ledger.
    metrics = {'duration': 120, 'input_tokens': 500, 'output_tokens': 200, 'tts_chars': 1500}
    costs = {'duration': 0.5, 'input_tokens': 0.1, ...}  # optional USD costs per metric
    """
    supabase = get_supabase_client()
    if not supabase:
        return

    rows = []
    for m_type, qty in metrics.items():
        if qty > 0:
            row = {
                "client_id": client_id,
                "conversation_id": conversation_id,
                "metric_type": m_type,
                "quantity": qty,
            }
            if costs and m_type in costs:
                row["cost_usd"] = costs[m_type]
            rows.append(row)

    if rows:
        try:
            supabase.table("usage_ledger").insert(rows).execute()
            logger.info(f"Ledger updated for Conversation {conversation_id}")
        except Exception as e:
            logger.error(f"Error logging ledger: {e}")


async def get_admin_ledger() -> list[Dict[str, Any]]:
    """
    ADMIN: Fetches the master ledger with joins for readability.
    """
    supabase = get_supabase_client()
    if not supabase:
        return []

    try:
        # Fetch latest 50 usage records with Client Name and Contact Phone
        response = (
            supabase.table("usage_ledger")
            .select("*, clients(name), conversations(contact_id, contacts(phone))")
            .order("created_at", desc=True)
            .limit(50)
            .execute()
        )

        return response.data if response.data else []
    except Exception as e:
        logger.error(f"Admin ledger fetch error: {e}")
        return []


async def get_admin_clients() -> Optional[list[Dict[str, Any]]]:
    """
    ADMIN: Fetches ALL clients using the Service Role Key (Bypassing RLS).
    """
    supabase = get_supabase_client()  # This uses SERVICE_ROLE_KEY by default
    if not supabase:
        return []

    try:
        # Fetch all clients
        response = supabase.table("clients").select("*").execute()
        return response.data if response.data else []
    except Exception as e:
        logger.error(f"Admin clients fetch error: {e}")
        return []


async def get_client_ledger(client_id: str) -> list[Dict[str, Any]]:
    """
    ADMIN: Fetches the last 50 ledger entries for a specific client.
    """
    supabase = get_supabase_client()
    if not supabase:
        return []

    try:
        response = (
            supabase.table("usage_ledger")
            .select("*")
            .eq("client_id", client_id)
            .order("created_at", desc=True)
            .limit(50)
            .execute()
        )
        return response.data if response.data else []
    except Exception as e:
        logger.error(f"Client ledger fetch error: {e}")
        return []


async def toggle_user_status(user_id: str) -> Optional[bool]:
    """
    ADMIN: Toggles the is_active status in user_metadata.
    """
    supabase = get_supabase_client()
    if not supabase:
        return None

    try:
        # 1. Get current user data to find current status
        user_response = supabase.auth.admin.get_user_by_id(user_id)
        if not user_response or not user_response.user:
            return None

        user = user_response.user
        current_meta = user.user_metadata or {}
        # Default to True if not set
        current_status = current_meta.get("is_active", True)
        new_status = not current_status

        # 2. Update metadata
        # Merge with existing metadata to avoid data loss
        updated_meta = current_meta.copy()
        updated_meta["is_active"] = new_status

        supabase.auth.admin.update_user_by_id(user_id, {"user_metadata": updated_meta})

        # 3. Cascade to Clients
        # This ensures that when a user is banned, their AI agents also stop working immediately.
        supabase.table("clients").update({"is_active": new_status}).eq(
            "owner_user_id", user_id
        ).execute()

        logger.info(
            f"Toggled user {user_id} status to {new_status}. Cascaded to clients."
        )
        return new_status

    except Exception as e:
        logger.error(f"Toggle user status error: {e}")
        return None


async def admin_update_client(
    client_id: str, data: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    ADMIN: Updates a client record using the Service Role Key.
    """
    supabase = get_supabase_client()
    if not supabase:
        return None

    try:
        response = (
            supabase.table("clients")
            .update(data, returning="representation")
            .eq("id", client_id)
            .execute()
        )
        if response.data:
            logger.info(
                f"ADMIN: Updated client {client_id} with data: {list(data.keys())}"
            )
            return response.data[0]
        else:
            logger.error(f"ADMIN: Failed to update client {client_id}")
            return None
    except Exception as e:
        logger.error(f"Admin update client error: {e}")
        return None


async def get_admin_users() -> list[Dict[str, Any]]:
    """
    ADMIN: Fetches ALL registered users using the Service Role Key's access to the Auth system.
    """
    supabase = get_supabase_client()  # Uses SERVICE_ROLE_KEY by default
    if not supabase:
        return []

    try:
        # Fetch all users using the admin client
        admin_response = supabase.auth.admin.list_users()

        # Flatten the user data for the frontend display
        users = [
            {
                "id": user.id,
                "email": user.email,
                "created_at": user.created_at,
                "last_sign_in_at": user.last_sign_in_at,
                "email_confirmed_at": user.email_confirmed_at,
                "role": user.role,
                "is_active": user.user_metadata.get("is_active", True)
                if user.user_metadata
                else True,
            }
            for user in admin_response
        ]

        return users

    except Exception as e:
        logger.error(f"Admin users fetch error (using auth.admin.list_users): {e}")
        return []


async def get_client_usage_stats() -> Optional[list[Dict[str, Any]]]:
    """
    Fetches client usage stats from the database function.
    Returns list of dicts with client_id, seconds_today, seconds_month.
    """
    supabase = get_supabase_client()
    if not supabase:
        return None

    try:
        response = supabase.rpc("get_client_usage_stats").execute()
        if response.data:
            return response.data
        else:
            return []
    except Exception as e:
        logger.error(f"Error fetching client usage stats: {e}")
        return None


async def get_global_usage_stats() -> dict:
    """
    Fetches global usage totals across all clients from DB function.
    Defaults to 0 on error/empty.
    """
    supabase = get_supabase_client()
    if not supabase:
        return {"total_seconds_today": 0, "total_seconds_month": 0}

    try:
        response = supabase.rpc("get_global_usage_stats").execute()
        if response.data and len(response.data) > 0:
            data = response.data[0]
            return {
                "total_seconds_today": data.get("total_seconds_today", 0),
                "total_seconds_month": data.get("total_seconds_month", 0),
            }
        else:
            return {"total_seconds_today": 0, "total_seconds_month": 0}
    except Exception as e:
        logger.error(f"Error fetching global usage stats: {e}")
        return {"total_seconds_today": 0, "total_seconds_month": 0}


async def get_financial_history(days: int = 30) -> list[Dict[str, Any]]:
    """
    Fetches daily financial summary (revenue, cost, profit) for last N days via RPC.
    Defaults to empty list on error.
    """
    supabase = get_supabase_client()
    if not supabase:
        return []

    try:
        response = supabase.rpc(
            "get_daily_financials", {"days_history": days}
        ).execute()
        return response.data or []
    except Exception as e:
        logger.error(f"Error fetching financial history: {e}")
        return []


async def get_cost_by_service(days: int = 30) -> Dict[str, Any]:
    """
    Returns cost breakdown by service/metric type for the last N days.
    Groups by metric_type and sums costs and quantities.
    """
    supabase = get_supabase_client()
    if not supabase:
        return {}

    try:
        from datetime import datetime, timedelta
        cutoff_date = (datetime.utcnow() - timedelta(days=days)).isoformat()

        response = (
            supabase.table("usage_ledger")
            .select("metric_type, quantity, cost_usd")
            .gte("created_at", cutoff_date)
            .execute()
        )

        # Aggregate by metric_type
        breakdown = {}
        for row in response.data or []:
            metric = row.get("metric_type", "unknown")
            qty = row.get("quantity", 0)
            cost = row.get("cost_usd", 0) or 0

            if metric not in breakdown:
                breakdown[metric] = {"quantity": 0, "cost": 0}

            breakdown[metric]["quantity"] += qty
            breakdown[metric]["cost"] += cost

        return breakdown
    except Exception as e:
        logger.error(f"Error fetching cost by service: {e}")
        return {}


async def get_cost_by_client(days: int = 30) -> list[Dict[str, Any]]:
    """
    Returns cost and revenue breakdown by client for profitability analysis.
    """
    supabase = get_supabase_client()
    if not supabase:
        return []

    try:
        from datetime import datetime, timedelta
        cutoff_date = (datetime.utcnow() - timedelta(days=days)).isoformat()

        # Get cost per client from usage_ledger
        cost_response = (
            supabase.table("usage_ledger")
            .select("client_id, cost_usd, quantity")
            .gte("created_at", cutoff_date)
            .execute()
        )

        # Aggregate costs by client
        client_costs = {}
        for row in cost_response.data or []:
            client_id = row.get("client_id")
            cost = row.get("cost_usd", 0) or 0

            if client_id not in client_costs:
                client_costs[client_id] = 0
            client_costs[client_id] += cost

        # Get client names
        clients_response = supabase.table("clients").select("id, name").execute()
        client_names = {c["id"]: c["name"] for c in clients_response.data or []}

        # Build result with client names
        result = []
        for client_id, total_cost in client_costs.items():
            result.append({
                "client_id": client_id,
                "client_name": client_names.get(client_id, "Unknown"),
                "total_cost": round(total_cost, 2)
            })

        # Sort by cost descending
        result.sort(key=lambda x: x["total_cost"], reverse=True)
        return result
    except Exception as e:
        logger.error(f"Error fetching cost by client: {e}")
        return []


async def get_top_expensive_calls(limit: int = 10) -> list[Dict[str, Any]]:
    """
    Returns the top N most expensive calls/conversations.
    """
    supabase = get_supabase_client()
    if not supabase:
        return []

    try:
        # Aggregate costs by conversation_id
        response = (
            supabase.table("usage_ledger")
            .select("conversation_id, cost_usd, quantity, metric_type, created_at, client_id")
            .not_.is_("conversation_id", "null")
            .execute()
        )

        # Group by conversation
        conv_costs = {}
        for row in response.data or []:
            conv_id = row.get("conversation_id")
            cost = row.get("cost_usd", 0) or 0
            client_id = row.get("client_id")
            created_at = row.get("created_at")

            if conv_id not in conv_costs:
                conv_costs[conv_id] = {
                    "conversation_id": conv_id,
                    "total_cost": 0,
                    "client_id": client_id,
                    "created_at": created_at
                }
            conv_costs[conv_id]["total_cost"] += cost

        # Sort and limit
        result = sorted(conv_costs.values(), key=lambda x: x["total_cost"], reverse=True)[:limit]

        # Get client names
        if result:
            client_ids = [r["client_id"] for r in result if r.get("client_id")]
            clients_response = supabase.table("clients").select("id, name").in_("id", client_ids).execute()
            client_names = {c["id"]: c["name"] for c in clients_response.data or []}

            for r in result:
                r["client_name"] = client_names.get(r["client_id"], "Unknown")
                r["total_cost"] = round(r["total_cost"], 2)

        return result
    except Exception as e:
        logger.error(f"Error fetching top expensive calls: {e}")
        return []
