import logging
import os
from datetime import datetime
import pytz

# Import our actual calendar functions
from services.google_calendar import get_available_slots, book_appointment

# Import our new database function
from services.supabase_client import update_contact_name
from pipecat.services.llm_service import FunctionCallParams


logger = logging.getLogger(__name__)


async def handle_get_available_slots(params: FunctionCallParams, **kwargs) -> None:
    """
    Check for available 30-minute appointment slots on a specific day.

    Args:
        date (str): The date to check for availability, in 'YYYY-MM-DD' format.
    """
    args = params.arguments.get("kwargs", params.arguments)
    raw_day = args["date"]
    # Force default — ignore any user-provided timezone
    timezone = "America/Los_Angeles"
    logger.info(f"Handling get_available_slots for day: {raw_day} in {timezone}")

    try:
        # TODO: Get this from the 'client' record in the future
        calendar_id = os.environ.get("DEFAULT_CALENDAR_ID", "primary")

        # --- Timezone & Date Logic ---
        tz = pytz.timezone(timezone)

        # Get the requested date
        req_date = datetime.strptime(raw_day, "%Y-%m-%d").date()

        # Work-day window: 9 AM – 5 PM in the caller's local timezone
        start_time = tz.localize(
            datetime(req_date.year, req_date.month, req_date.day, 9, 0, 0)
        )
        end_time = tz.localize(
            datetime(req_date.year, req_date.month, req_date.day, 17, 0, 0)
        )

        # Convert to UTC for the API
        start_time_utc = start_time.astimezone(pytz.utc)
        end_time_utc = end_time.astimezone(pytz.utc)

        logger.info(
            f"Querying Google Calendar free/busy from {start_time_utc} to {end_time_utc} UTC"
        )

        result = await get_available_slots(calendar_id, start_time_utc, end_time_utc)
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
    start_time = params.arguments["start_time"]
    end_time = params.arguments["end_time"]
    summary = params.arguments["summary"]
    description = params.arguments["description"]
    logger.info(f"Handling book_appointment for: {summary}")

    try:
        # TODO: Get this from the 'client' record
        calendar_id = os.environ.get("DEFAULT_CALENDAR_ID", "primary")

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
    phone_number = params.arguments["phone_number"]
    name = params.arguments["name"]
    logger.info(f"TOOL CALL: save_contact_name(phone={phone_number}, name={name})")

    success = await update_contact_name(phone_number=phone_number, name=name)

    if success:
        logger.info(f"Name persisted in DB: {name}")
        result = {"status": "success", "message": f"Name {name} saved."}
    else:
        logger.error("Failed to save name")
        result = {"status": "error", "message": "Failed to save name."}
    await params.result_callback(result)
