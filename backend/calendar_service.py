import os
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from schemas import MeetingRequest, MeetingResponse
from database import User

# Core Config
TIMEZONE = "Asia/Kolkata"
IST = ZoneInfo(TIMEZONE)
MEETING_DURATION_MINUTES = 30
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"

def _get_user_calendar_service(user: User):
    """
    Builds a Google Calendar service object for the specific user
    using their stored refresh token.
    """
    if not user.google_refresh_token:
        raise ValueError("User has not connected their Google Calendar.")

    # Construct Credentials object from stored tokens
    creds = Credentials(
        token=None,  # Access token will be refreshed automatically
        refresh_token=user.google_refresh_token,
        token_uri=GOOGLE_TOKEN_URI,
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
    )

    return build("calendar", "v3", credentials=creds)


def _parse_datetime_ist(date_str: str, time_str: str) -> datetime:
    """
    Parse separate date and time strings into a timezone-aware datetime in IST.
    """
    time_str = time_str.strip()

    # Determine 12h vs 24h
    if re.search(r"[APap][Mm]", time_str):
        fmt = "%I:%M %p" if " " in time_str else "%I:%M%p"
        naive_time = datetime.strptime(time_str.upper(), fmt.upper())
    else:
        naive_time = datetime.strptime(time_str, "%H:%M")

    naive_date = datetime.strptime(date_str, "%Y-%m-%d")

    naive_dt = naive_date.replace(
        hour=naive_time.hour,
        minute=naive_time.minute,
        second=0,
        microsecond=0,
    )

    # Attach IST timezone
    return naive_dt.replace(tzinfo=IST)


async def create_calendar_event(user: User, payload: MeetingRequest) -> MeetingResponse:
    """Create a Google Calendar event for the authenticated user."""
    start_dt = _parse_datetime_ist(payload.date, payload.time)
    end_dt = start_dt + timedelta(minutes=MEETING_DURATION_MINUTES)

    # Reject dates in the past
    now_ist = datetime.now(IST)
    if start_dt < now_ist:
        raise ValueError(
            f"Cannot schedule a meeting in the past. "
            f"Requested: {start_dt.strftime('%Y-%m-%d %H:%M IST')}, "
            f"Current time: {now_ist.strftime('%Y-%m-%d %H:%M IST')}"
        )

    # Use 'primary' because we are authenticated as the user
    calendar_id = "primary"

    event_body = {
        "summary": payload.title,
        "description": f"Meeting scheduled via Meeting Scheduler for {payload.name}.",
        "start": {
            "dateTime": start_dt.isoformat(),
            "timeZone": TIMEZONE,
        },
        "end": {
            "dateTime": end_dt.isoformat(),
            "timeZone": TIMEZONE,
        },
        # Auto-add Google Meet
        "conferenceData": {
            "createRequest": {
                "requestId": f"meet-{int(start_dt.timestamp())}",
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        },
    }

    print(f"DEBUG: create_calendar_event called for user {user.email}")
    service = _get_user_calendar_service(user)
    print("DEBUG: Google Calendar Service created")

    try:
        created_event = (
            service.events()
            .insert(
                calendarId=calendar_id,
                body=event_body,
                conferenceDataVersion=1,
            )
            .execute()
        )
        print(f"DEBUG: Event created successfully: {created_event.get('id')}")
    except Exception as e:
        print(f"DEBUG: Failed to insert event: {e}")
        raise e

    meet_link = None
    conference = created_event.get("conferenceData")
    if conference:
        for ep in conference.get("entryPoints", []):
            if ep.get("entryPointType") == "video":
                meet_link = ep.get("uri")
                break

    return MeetingResponse(
        success=True,
        event_id=created_event["id"],
        title=created_event["summary"],
        start_ist=start_dt.isoformat(),
        end_ist=end_dt.isoformat(),
        calendar_link=created_event.get("htmlLink", ""),
        meet_link=meet_link,
    )


async def find_event(user: User, name: str, date: str) -> str:
    """Find an upcoming event by name and date for the user."""
    service = _get_user_calendar_service(user)
    calendar_id = "primary"
    
    # Parse date to IST start/end of day
    dt = datetime.strptime(date, "%Y-%m-%d")
    start_of_day = dt.replace(hour=0, minute=0, second=0, microsecond=0).replace(tzinfo=IST)
    end_of_day = start_of_day + timedelta(days=1)
    
    events_result = (
        service.events()
        .list(
            calendarId=calendar_id,
            timeMin=start_of_day.isoformat(),
            timeMax=end_of_day.isoformat(),
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    events = events_result.get("items", [])

    for event in events:
        summary = event.get("summary", "")
        # Check if name is in summary (case-insensitive)
        if name.lower() in summary.lower():
            return event["id"]
            
    return None


async def delete_event(user: User, event_id: str):
    """Delete an event by ID."""
    service = _get_user_calendar_service(user)
    service.events().delete(calendarId="primary", eventId=event_id).execute()
