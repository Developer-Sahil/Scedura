// ── Config ────────────────────────────────────────────────────────────────
const API_BASE = "https://entopic-everleigh-unanthologized.ngrok-free.dev";

const firebaseConfig = {
    apiKey: "AIzaSyCDUdRMRYCyLtR9tT84rAuYDzCU42rbHtk",
    authDomain: "scedura-344cd.firebaseapp.com",
    projectId: "scedura-344cd",
    storageBucket: "scedura-344cd.firebasestorage.app",
    messagingSenderId: "686782617144",
    appId: "1:686782617144:web:b572a01591ee8963f938cd",
    measurementId: "G-MD91J505W4"
};

// Initialize Firebase
firebase.initializeApp(firebaseConfig);
const auth = firebase.auth();
const provider = new firebase.auth.GoogleAuthProvider();

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
    auth.signInWithPopup(provider).catch((error) => {
        showToast("error", error.message);
    });
});

document.getElementById("logoutBtn").addEventListener("click", () => {
    auth.signOut();
});

document.getElementById("connectCalendarBtn").addEventListener("click", () => {
    if (!currentUser) return;
    // Redirect to backend OAuth flow with UID
    window.location.href = `${API_BASE}/auth/google/login?uid=${currentUser.uid}`;
});

auth.onAuthStateChanged(async (user) => {
    if (user) {
        currentUser = user;
        authToken = await user.getIdToken();

        // UI Updates
        loginOverlay.style.display = "none";
        appContainer.style.display = "block"; // Changed to block to allow flex children logic
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
});

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

// ── Form Logic ────────────────────────────────────────────────────────────
function setLoading(isLoading) {
    const btn = document.getElementById("submitBtn");
    const spinner = document.getElementById("spinner");
    const label = document.getElementById("btnLabel");
    btn.disabled = isLoading;
    spinner.style.display = isLoading ? "block" : "none";
    label.textContent = isLoading ? "Processing..." : "Confirm Scheduling";
}

function formatIST(isoString) {
    try {
        return new Date(isoString).toLocaleString("en-IN", {
            timeZone: "Asia/Kolkata",
            weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
        });
    } catch { return isoString; }
}

// Default date
(function setDefaultDate() {
    const dateInput = document.getElementById("date");
    if (!dateInput) return; // Guard for safety
    const today = new Date().toLocaleDateString("en-CA");
    dateInput.value = today;
    dateInput.min = today;
})();

document.getElementById("meetingForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!authToken) {
        showToast("error", "You must be logged in.");
        return;
    }

    const name = document.getElementById("name").value.trim();
    const date = document.getElementById("date").value;
    const time = document.getElementById("time").value;
    const title = document.getElementById("title").value.trim();

    if (!name || !date || !time) {
        showToast("error", "Please fill in all required fields.");
        return;
    }

    setLoading(true);

    try {
        const response = await fetch(`${API_BASE}/create-meeting`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${authToken}`
            },
            body: JSON.stringify({ name, date, time, title: title || undefined }),
        });

        const data = await response.json();

        if (!response.ok) {
            showToast("error", data.detail || "Booking failed.");
            return;
        }

        // Success
        showToast("success", `Booked: ${data.title}. Redirecting to calendar...`);
        e.target.reset();

        // Redirect to calendar after a short delay
        if (data.calendar_link) {
            setTimeout(() => {
                window.location.href = data.calendar_link;
            }, 2000);
        }

        // Restore default date
        const dateInput = document.getElementById("date");
        if (dateInput) dateInput.value = new Date().toLocaleDateString("en-CA");

    } catch (err) {
        console.error(err);
        showToast("error", "Connection error. Ensure backend is running.");
    } finally {
        setLoading(false);
    }
});

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
        vapi = new window.Vapi("pGYsZruQzo8cpdFVZyJc");
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
