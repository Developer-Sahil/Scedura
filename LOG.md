# Project Change Log

## Initial State - 2026-02-20

As of today, the project repository has been audited. Below is the list of existing files and their current state. No previous git history was found to track historical changes.

### Backend (`/backend`)
- **`main.py`**: FastAPI application entry point. Handles HTTP requests for meeting creation and chat.
- **`agent.py`**: Contains `MeetingAgent` class integrating with Google Gemini and defining tools (`book_meeting`, `cancel_meeting`).
- **`calendar_service.py`**: Google Calendar API integration logic (Auth, Create Event, Find Event, Delete Event).
- **`schemas.py`**: Pydantic models for request/response validation (`MeetingRequest`, `MeetingResponse`, etc.).
- **`verify_memory.py`**: Script to verify agent memory (currently active).
- **`.env`**: Configuration file (Environment variables).
- **`credentials.json`**: Google Service Account credentials.
- **`requirements.txt`**: Python dependencies.

### Frontend (`/frontend`)
- **`index.html`**: Main user interface with manual form and chat/voice panel.
- **`script.js`**: Frontend logic handling form submission, voice recognition (`webkitSpeechRecognition`), and API calls.
- **`style.css`**: Stylesheet for the application.

## Changes
- **2026-02-20**:
    - Created `LOG.md` (this file).
    - Created `AUDIT.md` (Audit Report).
    - **Authentication & User Management**:
        - Implemented Firebase Authentication (Frontend & Backend).
        - Created `auth.py` for verifying Firebase ID tokens.
        - Created `database.py` with `User` model (SQLite) to store user data and refresh tokens.
    - **Google Calendar Integration**:
        - Implemented Google OAuth flow in `auth_routes.py` to allow users to connect their own calendars.
        - Refactored `calendar_service.py` to use user-specific credentials instead of a service account.
        - Updated `main.py` to protect endpoints (`/create-meeting`, `/chat`) with `verify_token` dependency.
    - **Agent Enhancements**:
        - Refactored `MeetingAgent` in `agent.py` to be user-aware, passing the authenticated user context to tools.
    - **Frontend Updates**:
        - Added Login Overlay with "Sign in with Google".
        - Added User Profile section and "Connect Calendar" button.
        - Updated `script.js` to handle authentication state and include auth tokens in API requests.
    - **Configuration**:
        - Added `SECRET_KEY` to `.env` for session management (AuthLib).
        - Removed `GOOGLE_CALENDAR_ID` from `.env` and `calendar_service.py` (now uses authenticated user's primary calendar).
        - Updated `README.md` and `AUDIT.md` to reflect these changes.
    - **Bug Fixes**:
        - Fixed CSS Grid layout issue causing "Jarvis Assistant" panel to disappear.
        - Fixed scrolling issue by removing `overflow: hidden` from body/container.
        - Fixed OAuth Callback Redirect: Now redirects to Frontend (port 3000) instead of Backend.
        - **Redirection & AI Improvements**:
            - Implemented automatic redirection to Google Calendar after successful booking in both Manual Form (2s delay) and AI Assistant (4s delay).
            - Updated AI model to `gemini-1.5-flash` in `agent.py` for improved stability and response quality.
            - Added fallback text logic in `MeetingAgent` to prevent empty chat bubbles when the LLM returns no content.
            - Enhanced backend logging with detailed tracebacks and debug print statements for `/chat` and tool executions.
            - Fixed `const dateInput` redeclaration error and code duplication in `script.js`.
            - Cleaned up duplicate exception handlers in `main.py`.
        - **SDK Migration**:
            - Refactored `MeetingAgent` in `agent.py` to use the official `google-genai` SDK (version 1.0+), bypassing LangChain's wrapper for better model compatibility and error handling.
            - Standardized `calendar_service.py` by making `find_event` and `delete_event` asynchronous.
            - Updated `requirements.txt` to include `google-genai`.
        - **UI & Branding**:
            - Rebranded the assistant from **Jarvis** to **Scedura** across frontend and backend.
            - Fixed layout issue where the manual scheduler panel stretched vertically with the AI chat.
        - **Vapi Integration & Voice Enhancements**:
            - Integrated Vapi Web SDK for voice-based interactions.
            - Resolved `ReferenceError: Vapi is not defined` by switching to an ESM-based loading strategy via `esm.sh` in `index.html`.
            - Fixed `TypeError: v.isCallActive is not a function` by updating to the correct SDK property `v.started`.
            - Implemented deferred initialization in `script.js` to handle asynchronous SDK loading.
            - Configured Vapi to route through the backend webhook (`/vapi/webhook`) using the `custom-llm` provider for unified logic.
            - Added granular error logging to diagnose `401 Unauthorized` and connectivity issues.
            - Updated Vapi public key to `pGYsZruQzo8cpdFVZyJc`.
        - **Conversation Memory**:
            - Implemented `chatHistory` in `script.js` to track user and bot messages.
            - Updated `schemas.py` and `main.py` to support passing conversation history to the backend.
            - Refactored `MeetingAgent` to utilize historical context for more coherent multi-turn conversations.
        - **UI & Branding**:
            - Completed rebranding from **Jarvis** to **Scedura** across all frontend assets and backend system instructions.
            - Fixed CSS layout issue where the manual scheduler panel stretched vertically.
            - Improved mic button responsiveness and added voice-specific status updates.
        - **Model Stability**:
            - Switched to `gemini-2.0-flash` model IDs to resolve `404 Not Found` errors with older model strings.
        - **P1 Security Enhancements**:
            - Implemented **Encryption at Rest** for Google Refresh Tokens using Fernet (cryptography).
            - Secured Vapi Webhooks with **HMAC-SHA256 signature verification**.
            - Refactored OAuth state management to use **signed session cookies** instead of in-memory stores.
            - Moved all frontend secrets (Firebase/Vapi) to a backend `/config` endpoint to prevent key exposure in source code.
        - **Infrastructure & Ngrok Support**:
            - Added `ProxyHeadersMiddleware` to `main.py` to correctly handle HTTPS headers from Ngrok tunnels.
            - Implemented dynamic OAuth redirects in `auth_routes.py` to support variable frontend origins (Locahost/Ngrok).
            - Updated `API_BASE` in `script.js` to use a public Ngrok URL for Vapi compatibility.
        - **Project Cleanup**:
            - Removed redundant test scripts: `test_vapi.py`, `models.txt`, and `verify_memory.py`.
            - Deleted deprecated service account directory `backend/secrets/`.
            - Standardized project structure and localized dependencies.
        - **Bug Fixes**:
            - Fixed `NameError` in `main.py` by using Python 3.12 `| None` syntax for type hints.
            - Cleaned up duplicate middleware and import declarations in `main.py`.

- **2026-02-21**:
    - **Project Simplification & Consolidation**:
        - Consolidated backend modules into `core.py` (DB, Schemas, Calendar Service).
        - Merged authentication and routing into a unified `main.py`.
        - Streamlined `agent.py` to reduce boilerplate.
        - Removed 5 legacy Python files to clean up the backend structure.
        - Simplified `requirements.txt` by removing unused LangChain packages.
    - **Voice Agent Optimization**:
        - Lean Data Model: Removed `name` requirement; meetings now only track Date, Time, and Purpose.
        - AI-First UI: Removed manual scheduling panel and centered the Scedura assistant in `index.html` and `style.v3.css`.
        - Purpose-Based Search: Implementation of calendar searches by event title (Purpose).
        - Cleaned up `script.js` by removing redundant manual form handling.
    - **Bug Fixes**:
        - Updated `script.js` to use `localhost:8000` for `API_BASE` to resolve "Failed to fetch" errors during local development.
