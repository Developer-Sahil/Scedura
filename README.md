# Scedura: Voice Schedular Agent

A professional meeting scheduling application with a FastAPI backend, vanilla JS frontend, and **Multi-User Google Calendar integration**. Users can log in with Google, connect their individual calendars, and schedule meetings via a manual form or a low-latency **Vapi-powered voice assistant**.

---

## Features

- **Google Sign-In**: Secure authentication via Firebase.
- **Personal Calendar Integration**: Users connect their own Google Calendar; the app manages events via OAuth 2.0.
- **AI Voice Assistant**: **Scedura** uses Gemini 2.0 and Vapi for natural voice-based scheduling.
- **Manual Scheduling**: Traditional form for quick slot booking.
- **Real-time Feedback**: Toast notifications and dynamic UI updates (with auto-redirect to Google Calendar).

---

## Project Structure

```
meeting-scheduler/
├── backend/
│   ├── main.py              # FastAPI app (includes Ngrok Proxy support)
│   ├── auth.py              # Firebase Token Verification
│   ├── auth_routes.py       # Google OAuth Flow (Dynamic Redirects)
│   ├── database.py          # SQLite DB (Persistent User Sessions)
│   ├── agent.py             # Scedura AI Agent (Context-aware)
│   ├── calendar_service.py  # Google Calendar API Integration
│   ├── schemas.py           # Pydantic models
│   └── requirements.txt
└── frontend/
    ├── index.html           # UI with Vapi & ESM loading
    ├── script.js            # Frontend Logic & Vapi Orchestration
    └── style.v3.css         # Modernized CSS
```

---

## Setup Guide

### 1. Google Cloud Project Setup

1. Go to [console.cloud.google.com](https://console.cloud.google.com).
2. Create a project.
3. **Enable APIs**:
   - Google Calendar API
4. **OAuth Consent Screen**:
   - User Type: External (or Internal if G-Suite).
   - Scopes: `.../auth/calendar.events` (and `openid`, `email`, `profile`).
   - Add Test Users (if External/Testing).
5. **Create Credentials**:
   - type: **OAuth 2.0 Client ID** (Web Application).
   - **Authorized Redirect URIs**: `http://localhost:8000/auth/google/callback`
   - Download JSON or copy `Client ID` and `Client Secret`.

### 2. Firebase Project Setup

1. Go to [console.firebase.google.com](https://console.firebase.google.com).
2. Create a project.
3. **Authentication**: Enable **Google** provider.
4. **Web App**: Register a web app to get your `firebaseConfig` object.
5. Update `frontend/script.js` with your Firebase Config.

### 3. Backend Setup

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# Mac/Linux: source .venv/bin/activate

pip install -r requirements.txt
```

Create a `.env` file in `backend/`:

```ini
GOOGLE_API_KEY=your_gemini_api_key
GOOGLE_CLIENT_ID=your_oauth_client_id
GOOGLE_CLIENT_SECRET=your_oauth_client_secret
SECRET_KEY=your_random_secret_string
```

Run the server:

```bash
uvicorn main:app --reload
```
API Docs: http://localhost:8000/docs

### 4. Ngrok & Vapi Setup (Voice)

Since Vapi is a cloud service, it requires a public URL to speak to your local backend.

1.  **Auth**: Ensure your **Vapi Public Key** is updated in `frontend/script.js`.
2.  **Ngrok**: Start a public tunnel:
    ```bash
    ngrok http 8000
    ```
3.  **Update Frontend**: Copy the `https://...` link from Ngrok and paste it into `API_BASE` at the top of `script.js`.
4.  **Google Console**: Ensure your Ngrok callback URL (`https://.../auth/google/callback`) is whitelisted in Google Authorized Redirect URIs.

### 5. Running the App

1. Start backend: `uvicorn main:app --reload` (Port 8000).
2. Start frontend: `python -m http.server 3000` (Port 3000).
3. Open `http://localhost:3000` (or your Ngrok link).

---

## API & Auth Flow

1. **Frontend Login**: User signs in with Google (Firebase).
2. **Token Exchange**: Frontend sends Firebase ID Token to Backend in `Authorization` header.
3. **Backend Verification**: `verify_token` dependency decodes token, upserts User in SQLite `users` table.
4. **Calendar Connection**: 
   - User clicks "Connect Calendar".
   - Redirects to `/auth/google/login`.
   - Google OAuth consent screen appears.
   - Callback to `/auth/google/callback` stores `refresh_token` in DB for that user.
5. **Booking**: 
   - Agent/Service fetches user's `refresh_token`.
   - Re-authenticates with Google.
   - Inserts event into user's **primary** calendar.

---

## Troubleshooting

- **"Please connect your Google Calendar"**: You are logged in, but haven't linked the OAuth scope. Click the link button.
- **401 Unauthorized**: Firebase token expired or missing. Refresh page / Re-login.
- **CORS Error**: Check `backend/main.py`. Default allows `*`.
- **Google 400 Error (redirect_uri_mismatch)**: Ensure `http://localhost:8000/auth/google/callback` is exactly listed in Google Cloud Console.

---

## Dependencies

- `fastapi`, `uvicorn`: Web Server
- `firebase-admin`: Auth Verification
- `authlib`, `itsdangerous`: OAuth & Sessions
- `sqlalchemy`: Database ORM
- `google-auth`, `google-api-python-client`: Google APIs
- `langchain-google-genai`: AI Agent
