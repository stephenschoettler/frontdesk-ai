import os
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional
import pytz
from google.oauth2 import service_account
from googleapiclient.discovery import build
import urllib.parse  # NEW IMPORT: Required to parse embed URLs

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar"]


def _clean_calendar_id(
    calendar_id: str,
) -> str:  # NEW FUNCTION: Handles user error of copying the full embed link
    """Extracts the actual calendar ID (email) from a full embed URL if needed."""
    if "calendar.google.com/calendar/embed" in calendar_id:
        try:
            parsed = urllib.parse.urlparse(calendar_id)
            query_params = urllib.parse.parse_qs(parsed.query)
            if "src" in query_params:
                # The ID is the first element of the 'src' list
                return query_params["src"][0]
        except Exception as e:
            logger.warning(f"Failed to parse calendar URL: {e}")
            # Fallback to original ID on failure
            return calendar_id
    return calendar_id


def get_calendar_service():
    """
    Initializes and returns a Google Calendar service object.
    """
    key_file_path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE_PATH")
    if not key_file_path:
        logger.critical(
            "GOOGLE_SERVICE_ACCOUNT_FILE_PATH environment variable not set."
        )
        return None

    try:
        creds = service_account.Credentials.from_service_account_file(
            key_file_path, scopes=SCOPES
        )
        service = build("calendar", "v3", credentials=creds)
        logger.info("Google Calendar service created successfully.")
        return service
    except Exception as e:
        logger.error(f"Failed to create Google Calendar service: {e}")
        return None


async def get_available_slots(
    calendar_id: str,
    start_time: datetime,
    end_time: datetime,
    # Removed time_range param
) -> list[dict]:
    """
    Fetches free/busy information and returns a list of available 1-hour slots.

    Args:
        calendar_id (str): The calendar ID to check.
        start_time (datetime): The start time for checking availability.
        end_time (datetime): The end time for checking availability.
    """
    # Clean the calendar_id first
    calendar_id = _clean_calendar_id(calendar_id)

    logger.info(
        f"Checking calendar [{calendar_id}] for slots between {start_time} and {end_time}"
    )

    service = get_calendar_service()
    if not service:
        logger.error("Google Calendar service is not available.")
        return []

    # Format times for the API
    start_rfc = start_time.isoformat()
    end_rfc = end_time.isoformat()

    freebusy_body = {
        "timeMin": start_rfc,
        "timeMax": end_rfc,
        "timeZone": "UTC",
        "items": [{"id": calendar_id}],
    }

    def _run_query():
        """This synchronous function will be run in a separate thread."""
        try:
            logger.info("Executing sync Google Calendar freeBusy query...")
            return service.freebusy().query(body=freebusy_body).execute()
        except Exception as e:
            logger.error(f"Error in Google Calendar API call: {e}")
            return None

    # Run the blocking IO call in an executor
    loop = asyncio.get_running_loop()
    freebusy_response = await loop.run_in_executor(None, _run_query)

    if not freebusy_response:
        return []

    busy_times = (
        freebusy_response.get("calendars", {}).get(calendar_id, {}).get("busy", [])
    )

    logger.debug(f"Busy intervals returned: {busy_times}")

    # --- Calculate Available Slots ---
    # (Removed the broken time_range filtering logic here) [cite_start][cite: 132]
    available_slots = []
    current_time = start_time

    while current_time < end_time:
        slot_end_time = current_time + timedelta(hours=1)
        is_busy = False

        # Check if this 1-hour slot overlaps with any busy time
        for busy in busy_times:
            # Google may return "Z" for UTC; normalize it
            busy_start = datetime.fromisoformat(busy["start"].replace("Z", "+00:00"))
            busy_end = datetime.fromisoformat(busy["end"].replace("Z", "+00:00"))

            # Convert to UTC for reliable comparison
            busy_start = busy_start.astimezone(pytz.utc)
            busy_end = busy_end.astimezone(pytz.utc)

            if (current_time < busy_end) and (slot_end_time > busy_start):
                is_busy = True
                break

        if not is_busy:
            available_slots.append(
                {"start": current_time.isoformat(), "end": slot_end_time.isoformat()}
            )

        # Move to the next slot
        current_time = slot_end_time

    logger.info(f"Found {len(available_slots)} available slots.")
    return available_slots


async def book_appointment(
    calendar_id: str,
    start_time: datetime,
    end_time: datetime,
    summary: str,
    description: Optional[str] = None,
) -> Optional[dict]:
    """
    Creates a new event on the Google Calendar.
    """
    # Clean the calendar_id first
    calendar_id = _clean_calendar_id(calendar_id)

    logger.info(f"Attempting to book appointment on [{calendar_id}]: {summary}")

    service = get_calendar_service()
    if not service:
        logger.error("Google Calendar service is not available.")
        return None

    event_body = {
        "summary": summary,
        "description": description,
        "start": {
            "dateTime": start_time.isoformat(),
            "timeZone": str(start_time.tzinfo) if start_time.tzinfo else "UTC",
        },
        "end": {
            "dateTime": end_time.isoformat(),
            "timeZone": str(end_time.tzinfo) if end_time.tzinfo else "UTC",
        },
        # We can add attendees here later if needed
        # 'attendees': [
        #     {'email': 'customer-email@example.com'},
        # ],
    }

    def _run_insert():
        """This synchronous function will be run in a separate thread."""
        try:
            logger.info("Executing sync Google Calendar events.insert query...")
            return (
                service.events()
                .insert(calendarId=calendar_id, body=event_body)
                .execute()
            )
        except Exception as e:
            logger.error(f"Error in Google Calendar API call (events.insert): {e}")
            return None

    # Run the blocking IO call in an executor
    loop = asyncio.get_running_loop()
    created_event = await loop.run_in_executor(None, _run_insert)

    if created_event:
        logger.info(f"Successfully created event, ID: {created_event.get('id')}")
        return created_event
    else:
        logger.error("Failed to create event.")
        return None


async def reschedule_appointment(
    calendar_id: str,
    event_id: str,
    new_start_time: datetime,
    new_end_time: Optional[datetime] = None,
) -> Optional[dict]:
    """
    Updates an existing event's start and end times on the Google Calendar.
    """
    calendar_id = _clean_calendar_id(calendar_id)

    logger.info(
        f"Attempting to reschedule event [{event_id}] on [{calendar_id}] to {new_start_time}"
    )

    service = get_calendar_service()
    if not service:
        logger.error("Google Calendar service is not available.")
        return None

    if new_end_time is None:
        new_end_time = new_start_time + timedelta(hours=1)

    try:
        # Fetch current event to preserve other fields
        def _run_get():
            return (
                service.events().get(calendarId=calendar_id, eventId=event_id).execute()
            )

        loop = asyncio.get_running_loop()
        current_event = await loop.run_in_executor(None, _run_get)

        if not current_event:
            logger.error(f"Event {event_id} not found.")
            return None

        # Update start and end
        current_event["start"] = {
            "dateTime": new_start_time.isoformat(),
            "timeZone": str(new_start_time.tzinfo) if new_start_time.tzinfo else "UTC",
        }
        current_event["end"] = {
            "dateTime": new_end_time.isoformat(),
            "timeZone": str(new_end_time.tzinfo) if new_end_time.tzinfo else "UTC",
        }

        def _run_update():
            return (
                service.events()
                .update(calendarId=calendar_id, eventId=event_id, body=current_event)
                .execute()
            )

        updated_event = await loop.run_in_executor(None, _run_update)

        if updated_event:
            logger.info(f"Successfully rescheduled event {event_id}")
            return updated_event
        else:
            logger.error("Failed to update event.")
            return None
    except Exception as e:
        logger.error(f"Error rescheduling appointment: {e}")
        return None


async def cancel_appointment(calendar_id: str, event_id: str) -> bool:
    """
    Cancels (deletes) an event from the Google Calendar.
    """
    calendar_id = _clean_calendar_id(calendar_id)
    logger.info(f"Attempting to cancel event [{event_id}] on [{calendar_id}]")

    service = get_calendar_service()
    if not service:
        logger.error("Google Calendar service is not available.")
        return False

    try:
        def _run_delete():
            service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
            return True

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _run_delete)
        logger.info(f"Successfully cancelled event {event_id}")
        return True
    except Exception as e:
        logger.error(f"Error cancelling appointment: {e}")
        return False


async def get_upcoming_appointments(calendar_id: str, phone_number: str) -> str:
    """
    Searches for future events containing the phone number in the description/summary.
    Returns a context string for the LLM.
    """
    calendar_id = _clean_calendar_id(calendar_id)
    service = get_calendar_service()
    if not service:
        return ""

    now = datetime.utcnow().isoformat() + "Z"

    def _run_search():
        # 'q' searches summary, description, and attendees
        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=now,
            maxResults=3,
            singleEvents=True,
            orderBy='startTime',
            q=phone_number
        ).execute()
        return events_result.get('items', [])

    loop = asyncio.get_running_loop()
    events = await loop.run_in_executor(None, _run_search)

    if not events:
        return ""

    context_lines = []
    for event in events:
        start = event['start'].get('dateTime', event['start'].get('date'))
        # Simple formatting for the AI to read
        # e.g. "Dental Cleaning on 2023-11-28T14:00:00 (ID: 12345)"
        context_lines.append(f"- {event.get('summary', 'Appointment')} at {start} (ID: {event['id']})")

    return "\n".join(context_lines)


async def list_my_appointments(calendar_id: str, phone_number: str) -> list[dict]:
    """
    Tool: Returns structured list of upcoming appointments matching caller phone.
    """
    calendar_id = _clean_calendar_id(calendar_id)
    service = get_calendar_service()
    if not service:
        logger.warning("Calendar service unavailable.")
        return []

    tz = pytz.timezone("America/Los_Angeles")

    now_utc = datetime.utcnow().isoformat() + "Z"

    def _run_list():
        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=now_utc,
            maxResults=10,
            singleEvents=True,
            orderBy="startTime",
            q=phone_number
        ).execute()
        return events_result.get("items", [])

    loop = asyncio.get_running_loop()
    events = await loop.run_in_executor(None, _run_list)

    appointments = []
    for event in events:
        start_iso = event["start"].get("dateTime", event["start"].get("date"))
        dt_utc = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
        dt_local = dt_utc.astimezone(tz)
        human_time = dt_local.strftime("%-I %p %B %d") if dt_local.minute == 0 else dt_local.strftime("%-I:%M %p %B %d")
        appointments.append({
            "booking_id": event["id"],
            "summary": event.get("summary", "Appointment"),
            "start_time": human_time,
            "iso_start": dt_local.isoformat()
        })
    logger.info(f"Listed {len(appointments)} appointments for {phone_number}")
    return appointments