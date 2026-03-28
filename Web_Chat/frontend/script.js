const TOKEN_KEY = "chat_access_token";
const USER_KEY = "chat_username";

// AUTO-DETECT BASE URL 
const BASE_URL = `${window.location.protocol}//${window.location.host}`;
const WS_URL = BASE_URL.replace("http", "ws");

const els = {
  authPanel: document.getElementById("auth-panel"),
  chatPanel: document.getElementById("chat-panel"),
  whoami: document.getElementById("whoami"),
  messages: document.getElementById("messages"),
  status: document.getElementById("status"),
  signupForm: document.getElementById("signup-form"),
  loginForm: document.getElementById("login-form"),
  messageForm: document.getElementById("message-form"),
  messageInput: document.getElementById("message-input"),
  logoutBtn: document.getElementById("logout-btn"),
  signupUsername: document.getElementById("signup-username"),
  signupPassword: document.getElementById("signup-password"),
  loginUsername: document.getElementById("login-username"),
  loginPassword: document.getElementById("login-password"),
};

let socket = null;

function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

function setSession(token, username) {
  localStorage.setItem(TOKEN_KEY, token);
  if (username) localStorage.setItem(USER_KEY, username);
}

function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

function setStatus(message) {
  els.status.textContent = message || "";
}

function authHeaders() {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function setAuthedView(isAuthed) {
  els.authPanel.classList.toggle("hidden", isAuthed);
  els.chatPanel.classList.toggle("hidden", !isAuthed);
}

function renderMessage(message) {
  const row = document.createElement("div");
  row.className = `message ${message.is_bot ? "bot" : "user"}`;

  const meta = document.createElement("div");
  meta.className = "meta";
  const when = message.created_at
    ? new Date(message.created_at).toLocaleString()
    : "";
  meta.textContent = `${message.username} • ${when}`;

  const body = document.createElement("div");
  body.className = "body";
  body.textContent = message.content;

  row.appendChild(meta);
  row.appendChild(body);
  els.messages.appendChild(row);
  els.messages.scrollTop = els.messages.scrollHeight;
}

function clearMessages() {
  els.messages.innerHTML = "";
}

async function loadMessages() {
  const res = await fetch(`${BASE_URL}/api/messages`);
  if (!res.ok) throw new Error("Could not load messages");

  const messages = await res.json();
  clearMessages();
  messages.forEach(renderMessage);
}

function closeSocket() {
  if (socket) {
    socket.close();
    socket = null;
  }
}

function openSocket() {
  closeSocket();

  const token = getToken();
  if (!token) return;

  socket = new WebSocket(
    `${WS_URL}/ws/chat?token=${encodeURIComponent(token)}`
  );

  socket.onopen = () => setStatus("Connected");
  socket.onclose = () => setStatus("Disconnected");
  socket.onerror = () => setStatus("WebSocket error");

  socket.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data);

      if (payload.type === "message" && payload.message) {
        renderMessage(payload.message);
      }
    } catch (e) {
      console.error("Socket parse error:", e);
    }
  };
}

async function bootstrapSession() {
  const token = getToken();
  const username = localStorage.getItem(USER_KEY);

  if (!token) {
    setAuthedView(false);
    setStatus("Ready");
    return;
  }

  try {
    const res = await fetch(`${BASE_URL}/api/me`, {
      headers: authHeaders(),
    });

    if (!res.ok) {
      clearSession();
      setAuthedView(false);
      setStatus("Session expired");
      return;
    }

    const data = await res.json();
    const name = data.username || username || "user";

    els.whoami.textContent = `Signed in as ${name}`;
    setAuthedView(true);

    await loadMessages();
    openSocket();

    setStatus("Connected");
  } catch {
    clearSession();
    setAuthedView(false);
    setStatus("Ready");
  }
}

async function handleSignup(event) {
  event.preventDefault();

  const username = els.signupUsername.value.trim();
  const password = els.signupPassword.value;

  const res = await fetch(`${BASE_URL}/api/auth/signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });

  const data = await res.json();

  if (!res.ok) {
    setStatus(data.detail || "Signup failed");
    return;
  }

  setSession(data.access_token, username);
  els.whoami.textContent = `Signed in as ${username}`;
  setAuthedView(true);

  els.signupForm.reset();
  els.loginForm.reset();

  await loadMessages();
  openSocket();
}

async function handleLogin(event) {
  event.preventDefault();

  const username = els.loginUsername.value.trim();
  const password = els.loginPassword.value;

  const res = await fetch(`${BASE_URL}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });

  const data = await res.json();

  if (!res.ok) {
    setStatus(data.detail || "Login failed");
    return;
  }

  setSession(data.access_token, username);
  els.whoami.textContent = `Signed in as ${username}`;
  setAuthedView(true);

  els.signupForm.reset();
  els.loginForm.reset();

  await loadMessages();
  openSocket();
}

async function handleSendMessage(event) {
  event.preventDefault();

  const content = els.messageInput.value.trim();
  if (!content) return;

  const res = await fetch(`${BASE_URL}/api/messages`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
    },
    body: JSON.stringify({ content }),
  });

  const data = await res.json();

  if (!res.ok) {
    setStatus(data.detail || "Could not send message");
    return;
  }

  els.messageInput.value = "";

  // fallback if websocket fails
  if (!socket || socket.readyState !== WebSocket.OPEN) {
    renderMessage(data);
  }
}

function handleLogout() {
  clearSession();
  closeSocket();
  clearMessages();

  els.whoami.textContent = "";
  els.signupForm.reset();
  els.loginForm.reset();
  els.messageForm.reset();

  setAuthedView(false);
  setStatus("Signed out");
}

document.addEventListener("DOMContentLoaded", async () => {
  els.signupForm.addEventListener("submit", handleSignup);
  els.loginForm.addEventListener("submit", handleLogin);
  els.messageForm.addEventListener("submit", handleSendMessage);
  els.logoutBtn.addEventListener("click", handleLogout);

  await bootstrapSession();
});