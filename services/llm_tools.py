import logging
import os
from datetime import datetime, timedelta
import pytz
from typing import Optional

# Import our actual calendar functions
from services.google_calendar import (
    get_available_slots,
    book_appointment,
    reschedule_appointment,
    cancel_appointment,
    list_my_appointments,
)

# Import our new database function and the new client config function
from services.supabase_client import update_contact_name, get_client_config
from pipecat.services.llm_service import FunctionCallParams


logger = logging.getLogger(__name__)


async def handle_get_available_slots(params: FunctionCallParams, client_id: Optional[str] = None, **kwargs) -> None:
    """
    Check for available 1-hour appointment slots on a specific day.
    Returns human-readable times in the business timezone.
    """
    target_client_id = client_id or os.environ.get("CLIENT_ID")
    if not target_client_id:
        await params.result_callback([{"error": "Client ID is not configured."}])
        return

    client_config = await get_client_config(target_client_id)
    if not client_config:
        await params.result_callback(
            [{"error": "Failed to fetch client configuration."}]
        )
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

        start_time = tz.localize(
            datetime(req_date.year, req_date.month, req_date.day, start_hour, 0, 0)
        )
        end_time = tz.localize(
            datetime(req_date.year, req_date.month, req_date.day, end_hour, 0, 0)
        )

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

            # CLEANER TTS FORMATTING
            # If minute is 0, use "9 AM". If not, use "9:30 AM"
            if dt_local.minute == 0:
                human_time = dt_local.strftime("%-I %p")
            else:
                human_time = dt_local.strftime("%-I:%M %p")

            # Debug Log to catch "wonky" outputs
            logger.info(f"TTS Debug - Converted {dt_local} -> '{human_time}'")

            # Keep the ISO string for the machine, add human string for the voice
            human_slots.append(
                {"human_time": human_time, "iso_start": dt_local.isoformat()}
            )

        if not human_slots:
            await params.result_callback("No slots available for that time range.")
        else:
            # Return a simplified list that instructs the AI exactly what to say
            await params.result_callback(human_slots)

    except Exception as e:
        logger.error(f"Error in handle_get_available_slots: {e}")
        await params.result_callback([{"error": str(e)}])


async def handle_book_appointment(params: FunctionCallParams, client_id: Optional[str] = None, **kwargs) -> None:
    """
    Book an appointment. Handles 'lazy' arguments from AI (missing end_time, etc).
    """
    target_client_id = client_id or os.environ.get("CLIENT_ID")
    if not target_client_id:
        await params.result_callback(
            {"status": "error", "message": "Client ID missing."}
        )
        return

    client_config = await get_client_config(target_client_id)
    if not client_config:
        await params.result_callback({"status": "error", "message": "Config missing."})
        return

    calendar_id = client_config.get("calendar_id", "primary")

    try:
        args = params.arguments.get("kwargs", params.arguments)
        logger.info(f"Book args: {args}")  # Debug log

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

        # 1. Get phone from Args OR Environment (System Context)
        phone_number = args.get("phone") or os.environ.get("CALLER_PHONE")

        # 2. Force-append to description (Preserve AI's notes + System's data)
        if phone_number:
            if description:
                description += f"\nCaller Phone: {phone_number}"
            else:
                description = f"Caller Phone: {phone_number}"

        if not summary:
            if contact_name:
                summary = f"Booking for {contact_name}"
            elif phone_number:
                summary = f"Booking for {phone_number}"
            else:
                summary = "AI-Scheduled Appointment"

        logger.info(f"Booking event: {summary} at {start_dt}")

        event = await book_appointment(
            calendar_id=calendar_id,
            start_time=start_dt,
            end_time=end_dt,
            summary=summary,
            description=description,
        )

        if event:
            # Simplify output for success message too
            if start_dt.minute == 0:
                human_time = start_dt.strftime("%-I %p")
            else:
                human_time = start_dt.strftime("%-I:%M %p")

            logger.info(f"TTS Debug - Booking Success Time: '{human_time}'")

            result = {
                "status": "success",
                "summary": event.get("summary"),
                "time": human_time,
            }
        else:
            result = {"status": "error", "message": "Calendar API failed."}
        await params.result_callback(result)

    except Exception as e:
        logger.error(f"Error in handle_book_appointment: {e}")
        await params.result_callback({"status": "error", "message": str(e)})


async def handle_save_contact_name(params: FunctionCallParams, client_id: Optional[str] = None, **kwargs) -> None:
    """
    Saves contact name. Robust against missing keys.
    """
    args = params.arguments.get("kwargs", params.arguments)
    phone_number = args.get("phone_number") or os.environ.get("CALLER_PHONE")
    name = args.get("name") or args.get("contact_name")

    # 1. Prefer the injected client_id (Thread-safe)
    # 2. Fallback to env var (Legacy/Testing)
    target_client_id = client_id or os.environ.get("CLIENT_ID")

    if not phone_number or not name or not target_client_id:
        await params.result_callback(
            {"status": "error", "message": "Missing phone, name, or client configuration."}
        )
        return

    logger.info(f"TOOL CALL: save_contact_name(phone={phone_number}, name={name}, client={target_client_id})")

    # FIX: Pass client_id to update function
    success = await update_contact_name(phone_number=phone_number, name=name, client_id=target_client_id)

    if success:
        await params.result_callback(
            {"status": "success", "message": f"Name {name} saved."}
        )
    else:
        await params.result_callback({"status": "error", "message": "Database error."})


async def handle_reschedule_appointment(params: FunctionCallParams, client_id: Optional[str] = None, **kwargs) -> None:
    """
    Reschedule an existing appointment to a new time.
    """
    target_client_id = client_id or os.environ.get("CLIENT_ID")
    if not target_client_id:
        await params.result_callback(
            {"status": "error", "message": "Client ID missing."}
        )
        return

    client_config = await get_client_config(target_client_id)
    if not client_config:
        await params.result_callback({"status": "error", "message": "Config missing."})
        return

    calendar_id = client_config.get("calendar_id", "primary")

    try:
        args = params.arguments.get("kwargs", params.arguments)
        logger.info(f"Reschedule args: {args}")

        booking_id = args.get("booking_id")
        if not booking_id:
            raise ValueError("booking_id is required.")

        # --- FIX: ROBUST PARAMETER HANDLING (Catching 'new_start_time') ---
        new_time_str = (
            args.get("new_time") or args.get("start_time") or args.get("new_start_time")
        )

        if not new_time_str:
            # Log what we actually got to help debug if it fails again
            logger.error(f"Missing time argument. Received keys: {list(args.keys())}")
            raise ValueError(
                "Could not determine new start time. Required: new_time, start_time, or new_start_time."
            )

        new_start = datetime.fromisoformat(new_time_str)

        # Check for end time (also checking new_end_time just in case)
        new_end_str = args.get("new_end_time") or args.get("end_time")
        if new_end_str:
            new_end = datetime.fromisoformat(new_end_str)
        else:
            # Default to 1 hour if not specified
            new_end = new_start + timedelta(hours=1)

        event = await reschedule_appointment(
            calendar_id=calendar_id,
            event_id=booking_id,
            new_start_time=new_start,
            new_end_time=new_end,
        )

        if event:
            if new_start.minute == 0:
                human_time = new_start.strftime("%-I %p")
            else:
                human_time = new_start.strftime("%-I:%M %p")

            result = {
                "status": "success",
                "message": f"Rescheduled appointment to {human_time}",
            }
        else:
            result = {"status": "error", "message": "Failed to reschedule appointment."}
        await params.result_callback(result)

    except Exception as e:
        logger.error(f"Error in handle_reschedule_appointment: {e}")
        await params.result_callback({"status": "error", "message": str(e)})


async def handle_cancel_appointment(params: FunctionCallParams, client_id: Optional[str] = None, **kwargs) -> None:
    """
    Cancel an existing appointment.
    """
    target_client_id = client_id or os.environ.get("CLIENT_ID")
    if not target_client_id:
        await params.result_callback(
            {"status": "error", "message": "Client ID missing."}
        )
        return

    client_config = await get_client_config(target_client_id)
    if not client_config:
        await params.result_callback({"status": "error", "message": "Config missing."})
        return

    calendar_id = client_config.get("calendar_id", "primary")

    try:
        args = params.arguments.get("kwargs", params.arguments)
        logger.info(f"Cancel args: {args}")

        booking_id = args.get("booking_id")
        if not booking_id:
            raise ValueError("booking_id is required.")

        success = await cancel_appointment(
            calendar_id=calendar_id,
            event_id=booking_id,
        )

        if success:
            result = {
                "status": "success",
                "message": "Appointment cancelled successfully.",
            }
        else:
            result = {"status": "error", "message": "Failed to cancel appointment."}
        await params.result_callback(result)

    except Exception as e:
        logger.error(f"Error in handle_cancel_appointment: {e}")
        await params.result_callback({"status": "error", "message": str(e)})


async def handle_list_my_appointments(params: FunctionCallParams, client_id: Optional[str] = None, **kwargs) -> None:
    """
    List the caller's upcoming appointments with booking_ids.
    """
    target_client_id = client_id or os.environ.get("CLIENT_ID")
    if not target_client_id:
        await params.result_callback([{"error": "No CLIENT_ID."}])
        return
    client_config = await get_client_config(target_client_id)
    if not client_config:
        await params.result_callback([{"error": "No client config."}])
        return
    calendar_id = client_config.get("calendar_id", "primary")
    phone = os.environ.get("CALLER_PHONE")
    if not phone:
        await params.result_callback([{"error": "No caller phone."}])
        return
    appointments = await list_my_appointments(calendar_id, phone)
    if not appointments:
        await params.result_callback("No upcoming appointments found.")
    else:
        await params.result_callback(appointments)
