import os
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware 
from fastapi.responses import JSONResponse
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from schemas import MeetingRequest, MeetingResponse, ErrorResponse, ChatRequest
from calendar_service import create_calendar_event
from database import init_db, User, SessionLocal
from auth import verify_token
from auth_routes import router as auth_router
from agent import MeetingAgent

# Initialize DB
init_db()

app = FastAPI(
    title="Meeting Scheduler",
    description="Webhook-compatible meeting scheduling API with Google Calendar integration",
    version="1.0.0",
)

# Required for AuthLib OAuth to manage state
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY", "super-secret-key"))
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production to your frontend domain
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

app.include_router(auth_router)

@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post(
    "/create-meeting",
    response_model=MeetingResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def create_meeting(
    payload: MeetingRequest, 
    user: User = Depends(verify_token)
):
    """
    Create a 30-minute Google Calendar meeting.
    Requires Firebase Auth Token.
    """
    try:
        # Pass user to service
        event = await create_calendar_event(user, payload)
        return event
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Calendar API error: {repr(e)}")


@app.post("/chat")
async def chat(
    payload: ChatRequest,
    user: User = Depends(verify_token)
):
    try:
        print(f"DEBUG: Chat request: {payload.message} from user {user.email}")
        # Instantiate agent per-request with the authenticated user
        agent = MeetingAgent(user)
        response, redirect_url = await agent.chat(payload.message, history=payload.history)
        print(f"DEBUG: Agent response: '{response}', Redirect: {redirect_url}")
        return {"response": response, "redirect_url": redirect_url}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Agent error: {repr(e)}")


# ── Vapi Webhook Logic ──────────────────────────────────────────────────

@app.post("/vapi/webhook")
async def vapi_webhook(request: Request):
    """
    Handles tool-call, assistant-request, and other webhook events from Vapi.
    """
    payload = await request.json()
    message = payload.get("message", {})
    msg_type = message.get("type")

    print(f"DEBUG: Vapi Webhook received: {msg_type}")

    # 1. Handle Tool Calls
    if msg_type == "tool-call":
        tool_calls = message.get("toolCalls", [])
        results = []
        
        user = await _get_user_from_vapi_metadata(payload)
        if not user:
            return {"results": [{"toolCallId": tc["id"], "result": "Error: User not found"} for tc in tool_calls]}

        agent = MeetingAgent(user)
        for tc in tool_calls:
            func = tc.get("function", {})
            name = func.get("name")
            args = func.get("arguments")
            print(f"DEBUG: Vapi executing tool: {name}")
            result = await agent._execute_tool(name, args)
            results.append({"toolCallId": tc["id"], "result": result})
        return {"results": results}

    # 2. Handle Assistant Request (The "Brain")
    # This is called if Vapi is configured with this server as the model provider
    if msg_type == "assistant-request":
        user = await _get_user_from_vapi_metadata(payload)
        if not user:
            return {"error": "User not found"}
        
        # Vapi sends the full message history in the payload
        vapi_messages = payload.get("messages", [])
        # The last message is the user utterance
        user_input = ""
        history = []
        
        # Convert Vapi messages to our agent format
        for m in vapi_messages:
            role = m.get("role")
            content = m.get("message") or m.get("content")
            if role == "user":
                user_input = content
            history.append({"role": role, "text": content})
            
        print(f"DEBUG: Vapi Assistant Request with {len(history)} messages. User: {user_input}")
        
        agent = MeetingAgent(user)
        # We use the agent.chat method which now handles history
        response_text, _ = await agent.chat(user_input, history=history[:-1]) # history minus current utterance
        
        return {
            "message": {
                "role": "assistant",
                "content": response_text
            }
        }

    return {"status": "success"}

async def _get_user_from_vapi_metadata(payload: dict) -> User | None:
    call = payload.get("call", {})
    metadata = call.get("metadata", {}) or {}
    user_email = metadata.get("user_email")
    
    db = SessionLocal()
    user = None
    if user_email:
        user = db.query(User).filter(User.email == user_email).first()
    else:
        user = db.query(User).first()
    db.close()
    return user
