import os
from fastapi import APIRouter, Request, Depends, HTTPException
from starlette.responses import RedirectResponse
from authlib.integrations.starlette_client import OAuth, OAuthError
from sqlalchemy.orm import Session
from database import get_db, User
from auth import verify_token

router = APIRouter()

oauth = OAuth()
oauth.register(
    name='google',
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile https://www.googleapis.com/auth/calendar.events'
    }
)

# In-memory store for pending states to link OAuth to Firebase User
# Key: state, Value: firebase_uid
# In production, use Redis or signed cookies
PENDING_STATES = {} 

@router.get("/auth/google/login")
async def google_login(request: Request, uid: str):
    """
    Initiates Google OAuth flow. 
    'uid' is the Firebase UID, passed so we know who is connecting the calendar.
    """
    redirect_uri = request.url_for('google_auth_callback')
    
    # Generate a unique state
    import secrets
    state = secrets.token_urlsafe(16)
    PENDING_STATES[state] = uid
    
    return await oauth.google.authorize_redirect(request, redirect_uri, state=state, access_type="offline", prompt="consent")


@router.get("/auth/google/callback")
async def google_auth_callback(request: Request, db: Session = Depends(get_db)):
    try:
        token = await oauth.google.authorize_access_token(request)
    except OAuthError as error:
        raise HTTPException(status_code=400, detail=str(error))
    
    state = request.query_params.get("state")
    firebase_uid = PENDING_STATES.pop(state, None)
    
    if not firebase_uid:
        raise HTTPException(status_code=400, detail="State mismatch or session expired.")

    user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
    if not user:
         raise HTTPException(status_code=404, detail="User not found.")

    # Save Refresh Token (Critical for offline access)
    refresh_token = token.get("refresh_token")
    if refresh_token:
        user.google_refresh_token = refresh_token
        user.is_calendar_connected = True
        db.commit()
    elif not user.is_calendar_connected:
        # If we didn't get a refresh token and they weren't connected, 
        # we might need to force 'prompt=consent' again.
        # But for now, we assume 'access_type=offline' worked.
        pass

    # Redirect back to frontend (using the Referer or a known frontend host)
    # For now, we redirect to the origin of the request to favor Ngrok/Localhost flexibility
    frontend_url = request.headers.get("referer") or os.getenv("FRONTEND_URL", "http://localhost:3000")
    return RedirectResponse(url=frontend_url)


@router.get("/auth/me")
async def get_my_status(user: User = Depends(verify_token)):
    return {
        "uid": user.firebase_uid,
        "email": user.email,
        "is_calendar_connected": user.is_calendar_connected
    }
