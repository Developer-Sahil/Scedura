// For local development, use localhost. Vapi/Voice Agent features REQUIRES a public URL (like Ngrok).
const API_BASE = "http://localhost:8000";

let auth = null;
let provider = null;
let publicVapiKey = null;

// ── Remote Config ──────────────────────────────────────────────────────────
async function initRemoteConfig() {
    try {
        console.log("Fetching remote config from:", `${API_BASE}/config`);
        const response = await fetch(`${API_BASE}/config`);
        if (!response.ok) throw new Error("Backend unreachable");
        const config = await response.json();

        // Initialize Firebase
        firebase.initializeApp(config.firebase);
        auth = firebase.auth();
        provider = new firebase.auth.GoogleAuthProvider();

        // Save Vapi Key
        publicVapiKey = config.vapi.publicKey;

        // Attach Auth Listener
        auth.onAuthStateChanged(onAuthChanged);

        console.log("Application configuration loaded successfully.");
    } catch (error) {
        console.error("CRITICAL: Failed to load config:", error);
        showToast("error", "Application configuration failed. Check backend connection.");
    }
}

initRemoteConfig();

let currentUser = null;
let authToken = null;
let chatHistory = []; // Maintain local history for context-aware chat

// ── Auth Logic ────────────────────────────────────────────────────────────
const loginOverlay = document.getElementById("loginOverlay");
const appContainer = document.getElementById("appContainer");
const userAvatar = document.getElementById("userAvatar");
const userName = document.getElementById("userName");
const connectCalendarBtn = document.getElementById("connectCalendarBtn");

document.getElementById("googleLoginBtn").addEventListener("click", () => {
    if (!auth) {
        showToast("error", "Configuration still loading...");
        return;
    }
    auth.signInWithPopup(provider).catch((error) => {
        showToast("error", error.message);
    });
});

document.getElementById("logoutBtn").addEventListener("click", () => {
    if (auth) auth.signOut();
});

document.getElementById("connectCalendarBtn").addEventListener("click", () => {
    if (!currentUser) return;
    // Redirect to backend OAuth flow with UID
    window.location.href = `${API_BASE}/auth/google/login?uid=${currentUser.uid}`;
});

async function onAuthChanged(user) {
    if (user) {
        currentUser = user;
        authToken = await user.getIdToken();

        // UI Updates
        loginOverlay.style.display = "none";
        appContainer.style.display = "block";
        appContainer.classList.add("fade-in");

        userAvatar.src = user.photoURL;
        userName.textContent = user.displayName;

        // Check Calendar Status
        checkCalendarStatus();
    } else {
        currentUser = null;
        authToken = null;
        loginOverlay.style.display = "flex";
        appContainer.style.display = "none";
    }
}

async function checkCalendarStatus() {
    try {
        const res = await fetch(`${API_BASE}/auth/me`, {
            headers: { "Authorization": `Bearer ${authToken}` }
        });
        if (res.ok) {
            const data = await res.json();
            if (data.is_calendar_connected) {
                connectCalendarBtn.style.display = "none";
            } else {
                connectCalendarBtn.style.display = "inline-flex";
                showToast("error", "Please connect your Google Calendar!");
            }
        }
    } catch (e) {
        console.error("Auth check failed", e);
    }
}


// ── Toast Logic ───────────────────────────────────────────────────────────
function showToast(type, message, linkHtml = "") {
    const toast = document.getElementById("toast");
    const icon = document.getElementById("toastIcon");
    const msg = document.getElementById("toastMsg");

    toast.className = `toast ${type} show`;
    icon.innerHTML = type === "success" ? "✓" : "⚠️";
    msg.innerHTML = message + linkHtml;

    setTimeout(() => {
        toast.classList.remove("show");
    }, 5000);
}


// ── Scedura Voice Assistant Logic ──────────────────────────────────────────

// ── Vapi Voice Logic ──────────────────────────────────────────────────────
const micBtn = document.getElementById("micBtn");
const statusEl = document.getElementById("status");
const chatLog = document.getElementById("chatLog");

// Initialize Vapi variable
let vapi = null;

function getVapi() {
    if (!vapi) {
        if (!window.Vapi) {
            console.error("Vapi SDK not yet loaded from esm.sh");
            return null;
        }
        if (!publicVapiKey) {
            console.error("Vapi Public Key not yet loaded from backend config");
            return null;
        }
        vapi = new window.Vapi(publicVapiKey);
        setupVapiListeners();
    }
    return vapi;
}

function setupVapiListeners() {
    vapi.on("call-start", () => {
        statusEl.textContent = "Call active. Start speaking...";
        micBtn.classList.add("active");
    });

    vapi.on("call-end", () => {
        statusEl.textContent = "Call ended.";
        micBtn.classList.remove("active");
    });

    vapi.on("speech-start", () => {
        statusEl.textContent = "Scedura is listening...";
    });

    vapi.on("speech-end", () => {
        statusEl.textContent = "Scedura is processing...";
    });

    vapi.on("message", (message) => {
        if (message.type === "transcript" && message.transcriptType === "final") {
            addMessage(message.role === "assistant" ? "bot" : "user", message.transcript);
        }

        if (message.type === "tool-call-result") {
            try {
                const result = JSON.parse(message.result);
                if (result.calendar_link) {
                    showToast("success", "Booking confirmed! Redirecting...");
                    setTimeout(() => {
                        window.location.href = result.calendar_link;
                    }, 4000);
                }
            } catch (e) { }
        }
    });

    vapi.on("error", (e) => {
        console.error("Vapi Error Details:", e);
        if (e.error) console.error("Nested Error Object:", e.error);
        statusEl.textContent = "Error: " + (e.type || "Check Console");
        showToast("error", "Voice connection failed: " + (e.type || "Check Console"));
    });
}

function addMessage(role, text) {
    const div = document.createElement("div");
    div.className = `msg ${role}`;
    div.textContent = text;
    chatLog.appendChild(div);
    chatLog.scrollTop = chatLog.scrollHeight;
}

micBtn.addEventListener("click", () => {
    const v = getVapi();
    if (!v) {
        showToast("error", "Voice SDK is still loading. Please wait a second.");
        return;
    }

    console.log("Mic button clicked! Call active:", v.started);

    if (v.started) {
        console.log("Stopping active call...");
        v.stop();
    } else {
        if (!currentUser) {
            console.error("No user logged in. Aborting call.");
            showToast("error", "Please sign in first.");
            return;
        }

        statusEl.textContent = "Connecting...";
        const publicUrl = API_BASE;
        console.log("Attempting vapi.start with URL:", `${publicUrl}/vapi/webhook`);

        if (publicUrl.includes("localhost") || publicUrl.includes("127.0.0.1")) {
            console.warn("CRITICAL: Vapi cannot reach localhost. A public Ngrok URL is REQUIRED.");
            showToast("error", "Public URL (Ngrok) required!");
        }

        try {
            v.start({
                assistant: {
                    model: {
                        provider: "custom-llm",
                        url: `${publicUrl}/vapi/webhook`
                    },
                    metadata: {
                        user_email: currentUser.email
                    },
                    firstMessage: "Hello. I am Scedura. How can I help with your calendar?"
                },
                serverUrl: `${publicUrl}/vapi/webhook`
            });
            console.log("vapi.start() executed successfully.");
        } catch (err) {
            console.error("Vapi start failed:", err);
            statusEl.textContent = "Vapi Error - See Console";
            showToast("error", "Vapi connection failed.");
        }
    }
});
