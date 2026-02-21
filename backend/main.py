import os
import hmac
import hashlib
import json
import secrets
from typing import Optional, List, Union
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, Depends, Request, Security
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware 
from starlette.responses import RedirectResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
import firebase_admin
from firebase_admin import credentials, auth
from authlib.integrations.starlette_client import OAuth, OAuthError
from cryptography.fernet import Fernet

from core import (
    init_db, User, SessionLocal, get_db,
    MeetingRequest, MeetingResponse, ChatRequest, ErrorResponse,
    create_calendar_event
)
from agent import MeetingAgent

# ─── 1. INITIALIZATION ──────────────────────────────────────────────────

init_db()

# Firebase Setup
cred = credentials.Certificate("credentials.json")
try:
    firebase_admin.get_app()
except ValueError:
    firebase_admin.initialize_app(cred)

app = FastAPI(title="Scedura API", version="1.0.0")

# Middleware
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY", "super-secret-key"))
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# OAuth Setup
oauth = OAuth()
oauth.register(
    name='google',
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile https://www.googleapis.com/auth/calendar.events'}
)

security = HTTPBearer()

# ─── 2. DEPENDENCIES ────────────────────────────────────────────────────

def verify_token(creds: HTTPAuthorizationCredentials = Security(security), db=Depends(get_db)):
    token = creds.credentials
    try:
        decoded_token = auth.verify_id_token(token)
        uid = decoded_token["uid"]
        email = decoded_token.get("email")
        user = db.query(User).filter(User.firebase_uid == uid).first()
        if not user:
            user = User(firebase_uid=uid, email=email)
            db.add(user)
            db.commit()
            db.refresh(user)
        return user
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid auth: {str(e)}")

def get_cipher():
    key = os.getenv("FERNET_KEY")
    return Fernet(key.encode()) if key else None

# ─── 3. ROUTES ──────────────────────────────────────────────────────────

@app.get("/health")
def health(): return {"status": "ok"}

@app.get("/config")
async def get_config():
    return {
        "firebase": {
            "apiKey": os.getenv("FIREBASE_API_KEY"),
            "authDomain": os.getenv("FIREBASE_AUTH_DOMAIN"),
            "projectId": os.getenv("FIREBASE_PROJECT_ID"),
            "storageBucket": os.getenv("FIREBASE_STORAGE_BUCKET"),
            "messagingSenderId": os.getenv("FIREBASE_MESSAGING_SENDER_ID"),
            "appId": os.getenv("FIREBASE_APP_ID"),
        },
        "vapi": {"publicKey": os.getenv("VAPI_PUBLIC_KEY")}
    }


@app.post("/chat")
async def chat_endpoint(payload: ChatRequest, user: User = Depends(verify_token)):
    agent = MeetingAgent(user)
    response, redirect_url = await agent.chat(payload.message, history=payload.history)
    return {"response": response, "redirect_url": redirect_url}

# ─── 4. AUTH ROUTES ─────────────────────────────────────────────────────

@app.get("/auth/google/login")
async def google_login(request: Request, uid: str):
    redirect_uri = request.url_for('google_callback')
    state = secrets.token_urlsafe(16)
    request.session[f"oauth_state_{state}"] = uid
    return await oauth.google.authorize_redirect(request, redirect_uri, state=state, access_type="offline", prompt="consent")

@app.get("/auth/google/callback")
async def google_callback(request: Request, db=Depends(get_db)):
    try:
        token = await oauth.google.authorize_access_token(request)
    except OAuthError as error:
        raise HTTPException(status_code=400, detail=str(error))
    
    state = request.query_params.get("state")
    uid = request.session.pop(f"oauth_state_{state}", None)
    if not uid: raise HTTPException(status_code=400, detail="Session expired")

    user = db.query(User).filter(User.firebase_uid == uid).first()
    if not user: raise HTTPException(status_code=404, detail="User not found")

    refresh_token = token.get("refresh_token")
    if refresh_token:
        cipher = get_cipher()
        user.google_refresh_token = cipher.encrypt(refresh_token.encode()).decode() if cipher else refresh_token
        user.is_calendar_connected = True
        db.commit()

    frontend_url = request.headers.get("referer") or os.getenv("FRONTEND_URL", "http://localhost:3000")
    return RedirectResponse(url=frontend_url)

@app.get("/auth/me")
async def get_me(user: User = Depends(verify_token)):
    return {"uid": user.firebase_uid, "email": user.email, "is_calendar_connected": user.is_calendar_connected}

# ─── 5. VAPI WEBHOOK ────────────────────────────────────────────────────

@app.post("/vapi/webhook")
async def vapi_webhook(request: Request):
    vapi_secret = os.getenv("VAPI_SERVER_SECRET")
    body = await request.body()
    if vapi_secret:
        if not hmac.compare_digest(request.headers.get("x-vapi-signature", ""), hmac.new(vapi_secret.encode(), body, hashlib.sha256).hexdigest()):
            raise HTTPException(status_code=401)
    
    payload = json.loads(body)
    msg = payload.get("message", {})
    mtype = msg.get("type")

    if mtype in ["tool-call", "assistant-request"]:
        user = await _get_vapi_user(payload)
        if not user: return {"error": "User not found"}
        agent = MeetingAgent(user)

        if mtype == "tool-call":
            results = []
            for tc in msg.get("toolCalls", []):
                res = await agent._execute_tool(tc["function"]["name"], tc["function"]["arguments"])
                results.append({"toolCallId": tc["id"], "result": res})
            return {"results": results}

        if mtype == "assistant-request":
            history = [{"role": m.get("role"), "text": m.get("message") or m.get("content")} for m in payload.get("messages", [])]
            text, _ = await agent.chat(history[-1]["text"], history=history[:-1])
            return {"message": {"role": "assistant", "content": text}}
    
    return {"status": "success"}

async def _get_vapi_user(payload: dict) -> Optional[User]:
    email = payload.get("call", {}).get("metadata", {}).get("user_email")
    db = SessionLocal()
    user = db.query(User).filter(User.email == email).first() if email else db.query(User).first()
    db.close()
    return user
