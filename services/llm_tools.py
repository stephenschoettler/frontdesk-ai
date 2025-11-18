import logging
import os
from datetime import datetime
import pytz

# Import our actual calendar functions
from services.google_calendar import get_available_slots, book_appointment

# Import our new database function and the new client config function
from services.supabase_client import update_contact_name, get_client_config
from pipecat.services.llm_service import FunctionCallParams


logger = logging.getLogger(__name__)




async def handle_get_available_slots(params: FunctionCallParams, **kwargs) -> None:
    """
    Check for available 1-hour appointment slots on a specific day.

    Args:
        date (str): The date to check for availability, in 'YYYY-MM-DD' format.
        time_range (str, optional): "morning" or "afternoon" to filter slots to 9 AM - 12 PM or 12 PM - 5 PM.
    """
    client_id = os.environ.get("CLIENT_ID")
    if not client_id:
        await params.result_callback([{"error": "Client ID is not configured."}])
        return

    # --- FETCH CLIENT CONFIG TO GET DYNAMIC SETTINGS ---
    client_config = await get_client_config(client_id)
    if not client_config:
        await params.result_callback([{"error": "Failed to fetch client configuration."}])
        return

    # --- USE CONFIG VALUES with Fallbacks (Defaults from setup.sql) ---
    calendar_id = client_config.get("calendar_id", "primary")
    timezone = client_config.get("business_timezone", "America/Los_Angeles")
    start_hour_default = client_config.get("business_start_hour", 9)
    end_hour_default = client_config.get("business_end_hour", 17)

    args = params.arguments.get("kwargs", params.arguments)
    raw_day = args["date"]
    time_range = args.get("time_range")
    
    logger.info(f"Handling get_available_slots for day: {raw_day} in {timezone}")

    try:
        # --- Timezone & Date Logic ---
        tz = pytz.timezone(timezone)

        # Get the requested date
        req_date = datetime.strptime(raw_day, "%Y-%m-%d").date()

        # Determine working hours based on time_range
        start_hour = start_hour_default
        end_hour = end_hour_default

        if time_range == "morning":
            end_hour = 12
        elif time_range == "afternoon":
            start_hour = 12

        # Create localized datetimes first
        start_time = tz.localize(
            datetime(req_date.year, req_date.month, req_date.day, start_hour, 0, 0)
        )
        end_time = tz.localize(
            datetime(req_date.year, req_date.month, req_date.day, end_hour, 0, 0)
        )

        # Convert to UTC for the API
        start_time_utc = start_time.astimezone(pytz.utc)
        end_time_utc = end_time.astimezone(pytz.utc)

        logger.info(
            f"Querying Google Calendar free/busy from {start_time_utc} to {end_time_utc} UTC"
        )

        result = await get_available_slots(
            calendar_id, start_time_utc, end_time_utc
        )
        await params.result_callback(result)

    except Exception as e:
        logger.error(f"Error in handle_get_available_slots: {e}")
        await params.result_callback([{"error": str(e)}])


async def handle_book_appointment(params: FunctionCallParams, **kwargs) -> None:
    """
    Book an appointment on the calendar.

    Args:
        start_time (str): The start time of the appointment in ISO 8601 format (e.g., '2025-11-20T14:30:00-08:00').
        end_time (str): The end time of the appointment in ISO 8601 format.
        summary (str): A summary or title for the appointment (e.g., 'Booking for John Doe').
        description (str): A description for the appointment, including the caller's phone number.
    """
    client_id = os.environ.get("CLIENT_ID")
    if not client_id:
        await params.result_callback({"status": "error", "message": "Client ID is not configured."})
        return

    # --- FETCH CLIENT CONFIG TO GET CALENDAR ID ---
    client_config = await get_client_config(client_id)
    if not client_config:
        await params.result_callback({"status": "error", "message": "Failed to fetch client configuration."})
        return

    calendar_id = client_config.get("calendar_id", "primary") # Use config or fallback

    try:
        args = params.arguments.get("kwargs", params.arguments)

        # FIX: We now use the correct keys from the LLM arguments.
        start_time = args["start_time"]
        end_time = args["end_time"]
        description = args["description"]

        # FIX: Robustly get the summary, or build it from provided contact info.
        # This prevents the KeyError: 'summary' seen in the log.
        summary = args.get("summary")
        contact_name = args.get("name")
        phone_number = args.get("phone")

        if not summary:
            if contact_name:
                summary = f"Booking for {contact_name}"
            elif phone_number:
                summary = f"Booking for {phone_number}"
            else:
                summary = "AI-Scheduled Appointment"
        logger.info(f"Handling book_appointment for: {summary}")
        
        start_time_dt = datetime.fromisoformat(start_time)
        end_time_dt = datetime.fromisoformat(end_time)

        event = await book_appointment(
            calendar_id=calendar_id,
            start_time=start_time_dt,
            end_time=end_time_dt,
            summary=summary,
            description=description,
        )

        if event:
            result = {
                "status": "success",
                "event_id": event.get("id"),
                "summary": event.get("summary"),
            }
        else:
            result = {"status": "error", "message": "Failed to create event."}
        await params.result_callback(result)

    except Exception as e:
        logger.error(f"Error in handle_book_appointment: {e}")
        await params.result_callback({"status": "error", "message": str(e)})


async def handle_save_contact_name(params: FunctionCallParams, **kwargs) -> None:
    """
    Saves or updates a caller's name in the database using their phone number.

    Args:
        phone_number (str): The phone number of the contact to update (e.g., '+15551234567').
        name (str): The full name of the contact to save.
    """
    args = params.arguments.get("kwargs", params.arguments)
    phone_number = args["phone_number"]
    name = args["name"]
    logger.info(f"TOOL CALL: save_contact_name(phone={phone_number}, name={name})")

    success = await update_contact_name(phone_number=phone_number, name=name)

    if success:
        logger.info(f"Name persisted in DB: {name}")
        result = {"status": "success", "message": f"Name {name} saved."}
    else:
        logger.error("Failed to save name")
        result = {"status": "error", "message": "Failed to save name."}
    await params.result_callback(result)