import os
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional
import pytz
from google.oauth2 import service_account
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar"]


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
    calendar_id: str, start_time: datetime, end_time: datetime
) -> list[dict]:
    """
    Fetches free/busy information and returns a list of available 30-minute slots.
    """
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
        "timeZone": start_time.tzinfo.tzname(start_time),
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
    available_slots = []
    current_time = start_time

    while current_time < end_time:
        slot_end_time = current_time + timedelta(minutes=30)
        is_busy = False

        # Check if this 30-min slot overlaps with any busy time
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
