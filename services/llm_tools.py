import logging
import os
from datetime import datetime, timedelta
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
    Returns human-readable times in the business timezone.
    """
    client_id = os.environ.get("CLIENT_ID")
    if not client_id:
        await params.result_callback([{"error": "Client ID is not configured."}])
        return

    client_config = await get_client_config(client_id)
    if not client_config:
        await params.result_callback([{"error": "Failed to fetch client configuration."}])
        return

    calendar_id = client_config.get("calendar_id", "primary")
    timezone = client_config.get("business_timezone", "America/Los_Angeles")
    start_hour_default = client_config.get("business_start_hour", 9)
    end_hour_default = client_config.get("business_end_hour", 17)

    args = params.arguments.get("kwargs", params.arguments)
    raw_day = args["date"]
    time_range = args.get("time_range")
    
    logger.info(f"Handling get_available_slots for day: {raw_day} in {timezone}")

    try:
        tz = pytz.timezone(timezone)
        req_date = datetime.strptime(raw_day, "%Y-%m-%d").date()

        # Determine working hours
        start_hour = start_hour_default
        end_hour = end_hour_default
        if time_range == "morning":
            end_hour = 12
        elif time_range == "afternoon":
            start_hour = 12

        start_time = tz.localize(datetime(req_date.year, req_date.month, req_date.day, start_hour, 0, 0))
        end_time = tz.localize(datetime(req_date.year, req_date.month, req_date.day, end_hour, 0, 0))

        start_time_utc = start_time.astimezone(pytz.utc)
        end_time_utc = end_time.astimezone(pytz.utc)

        # Get slots from Google (returns UTC ISO strings)
        raw_slots = await get_available_slots(calendar_id, start_time_utc, end_time_utc)
        
        # --- FORMAT SLOTS FOR HUMAN READABILITY ---
        human_slots = []
        for slot in raw_slots:
            # Parse the UTC time from Google
            dt_utc = datetime.fromisoformat(slot["start"])
            # Convert to Business Timezone
            dt_local = dt_utc.astimezone(tz)
            # Format nicely (e.g., "9:00 AM")
            human_time = dt_local.strftime("%-I:%M %p")
            # Keep the ISO string for the machine, add human string for the voice
            human_slots.append({
                "human_time": human_time, 
                "iso_start": dt_local.isoformat()
            })

        if not human_slots:
             await params.result_callback("No slots available for that time range.")
        else:
             # Return a simplified list that instructs the AI exactly what to say
             await params.result_callback(human_slots)

    except Exception as e:
        logger.error(f"Error in handle_get_available_slots: {e}")
        await params.result_callback([{"error": str(e)}])


async def handle_book_appointment(params: FunctionCallParams, **kwargs) -> None:
    """
    Book an appointment. Handles 'lazy' arguments from AI (missing end_time, etc).
    """
    client_id = os.environ.get("CLIENT_ID")
    if not client_id:
        await params.result_callback({"status": "error", "message": "Client ID missing."})
        return

    client_config = await get_client_config(client_id)
    if not client_config:
        await params.result_callback({"status": "error", "message": "Config missing."})
        return

    calendar_id = client_config.get("calendar_id", "primary")

    try:
        args = params.arguments.get("kwargs", params.arguments)
        logger.info(f"Book args: {args}") # Debug log
        
        # --- ROBUST ARGUMENT PARSING ---
        start_time_str = args.get("start_time")
        
        # Handle "time" vs "start_time" ambiguity
        if not start_time_str:
            time_arg = args.get("time")
            date_arg = args.get("date")
            
            if time_arg:
                # FIX: If AI sends full ISO string (contains 'T'), use it directly
                if "T" in time_arg:
                    start_time_str = time_arg
                # Otherwise, combine date + simple time
                elif date_arg:
                    if len(time_arg) == 5:
                        time_arg += ":00"  # Fix "17:00" to "17:00:00"
                    start_time_str = f"{date_arg}T{time_arg}"
                    # Fallback to PST if no offset provided
                    if "+" not in start_time_str and "-" not in start_time_str[-6:]:
                         start_time_str += "-08:00"

        if not start_time_str:
            raise ValueError("Could not determine start_time from arguments.")

        # Calculate end time if missing (default 1 hour)
        end_time_str = args.get("end_time")
        if not end_time_str:
            start_dt = datetime.fromisoformat(start_time_str)
            end_dt = start_dt + timedelta(hours=1)
            end_time_str = end_dt.isoformat()
        else:
            start_dt = datetime.fromisoformat(start_time_str)
            end_dt = datetime.fromisoformat(end_time_str)

        # Handle names
        summary = args.get("summary")
        description = args.get("description", "")
        contact_name = args.get("name") or args.get("caller_name")

        if not summary:
            summary = f"Booking for {contact_name}" if contact_name else "AI Appointment"

        logger.info(f"Booking event: {summary} at {start_dt}")

        event = await book_appointment(
            calendar_id=calendar_id,
            start_time=start_dt,
            end_time=end_dt,
            summary=summary,
            description=description,
        )

        if event:
            result = {
                "status": "success", 
                "summary": event.get("summary"), 
                "time": start_dt.strftime("%-I:%M %p")
            }
        else:
            result = {"status": "error", "message": "Calendar API failed."}
        await params.result_callback(result)

    except Exception as e:
        logger.error(f"Error in handle_book_appointment: {e}")
        await params.result_callback({"status": "error", "message": str(e)})


async def handle_save_contact_name(params: FunctionCallParams, **kwargs) -> None:
    """
    Saves contact name. Robust against missing keys.
    """
    args = params.arguments.get("kwargs", params.arguments)
    phone_number = args.get("phone_number")
    name = args.get("name") or args.get("contact_name")

    if not phone_number or not name:
        await params.result_callback({"status": "error", "message": "Missing phone or name."})
        return

    logger.info(f"TOOL CALL: save_contact_name(phone={phone_number}, name={name})")
    success = await update_contact_name(phone_number=phone_number, name=name)
    
    if success:
        await params.result_callback({"status": "success", "message": f"Name {name} saved."})
    else:
        await params.result_callback({"status": "error", "message": "Database error."})

