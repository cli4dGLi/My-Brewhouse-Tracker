"""Gating live pages before loading data and keeping login state server-side."""
from collections import deque
from hashlib import sha256
import hmac
import json
import math
import os
import secrets
import threading
import time

import streamlit as st

AUTH_KEY = "_beer_loss_auth"
USERNAME_KEY = "_beer_loss_username"
PASSWORD_KEY = "_beer_loss_password"
MESSAGE_KEY = "_beer_loss_login_message"
IDLE_SECONDS = 30 * 60
SESSION_SECONDS = 12 * 60 * 60
_SERVER_KEY = secrets.token_bytes(32)


def setting(name, default=""):
    if name in os.environ:
        return os.environ[name]
    try:
        return str(st.secrets.get(name, default))
    except Exception:
        return default


def configured(username, password):
    return (1 <= len(username) <= 120 and not username.upper().startswith("REPLACE")
            and 16 <= len(password) <= 1024 and not password.upper().startswith("REPLACE"))


def password_matches(provided, expected):
    if not isinstance(provided, str) or len(provided) > 1024:
        return False
    # Comparing fixed-length digests and supporting Unicode without exposing it.
    return hmac.compare_digest(sha256(provided.encode()).digest(), sha256(expected.encode()).digest())


def revision(username, password):
    credentials = json.dumps([username, password], ensure_ascii=False).encode()
    return hmac.new(_SERVER_KEY, credentials, "sha256").hexdigest()


def session_valid(state, username, password, now):
    auth = state.get(AUTH_KEY)
    if not configured(username, password) or not isinstance(auth, dict):
        return False
    try:
        return (hmac.compare_digest(auth["revision"], revision(username, password))
                and 0 <= now - auth["started"] < SESSION_SECONDS
                and 0 <= now - auth["last_seen"] < IDLE_SECONDS)
    except (KeyError, TypeError):
        return False


def clear_session():
    # Clearing form values, administrator credentials and authentication together.
    for name in list(st.session_state):
        del st.session_state[name]


class LoginThrottle:
    """Limiting attempts across browser sessions within one server process."""

    def __init__(self, limit=10, window=60):
        self.limit = limit
        self.window = window
        self.attempts = deque()
        self.lock = threading.Lock()

    def claim(self, now):
        with self.lock:
            while self.attempts and now - self.attempts[0] >= self.window:
                self.attempts.popleft()
            if len(self.attempts) >= self.limit:
                return max(1, math.ceil(self.window - (now - self.attempts[0])))
            self.attempts.append(now)
            return 0


@st.cache_resource
def login_throttle():
    return LoginThrottle()


def attempt_login():
    # Removing submitted credentials before rendering the next page.
    provided_username = st.session_state.pop(USERNAME_KEY, "").strip()
    provided = st.session_state.pop(PASSWORD_KEY, "")
    expected_username = setting("APP_USERNAME").strip()
    expected = setting("APP_PASSWORD")
    if not configured(expected_username, expected):
        clear_session()
        return
    now = time.monotonic()
    wait = login_throttle().claim(now)
    if wait:
        st.session_state[MESSAGE_KEY] = f"Too many sign-in attempts. Try again in {wait} seconds."
        return
    # Checking both values and returning the same error for either mismatch.
    username_ok = password_matches(provided_username, expected_username)
    password_ok = password_matches(provided, expected)
    if not (username_ok & password_ok):
        st.session_state[MESSAGE_KEY] = "Incorrect username or password."
        return
    clear_session()
    st.session_state[AUTH_KEY] = {"revision": revision(expected_username, expected), "started": now, "last_seen": now}


def require_login():
    mode = setting("APP_MODE", "live").strip().lower()
    if mode == "demo":
        return
    if mode != "live":
        clear_session()
        st.error("APP_MODE must be live or demo.")
        st.stop()
    expected_username = setting("APP_USERNAME").strip()
    expected = setting("APP_PASSWORD")
    if not configured(expected_username, expected):
        clear_session()
        st.error("Sign-in is not configured. The administrator must set APP_USERNAME and a private APP_PASSWORD of at least 16 characters in Streamlit Secrets.")
        st.stop()
    now = time.monotonic()
    if session_valid(st.session_state, expected_username, expected, now):
        st.session_state[AUTH_KEY]["last_seen"] = now
        st.sidebar.button("Sign out", on_click=clear_session, key="sign_out", width="stretch")
        return
    if AUTH_KEY in st.session_state:
        clear_session()
        st.info("Your session expired or access settings changed. Please sign in again.")
    st.title("🍺 Beer Loss Operations")
    st.write("Sign in to view the dashboard and enter production logs.")
    with st.form("application_login"):
        st.text_input("Username", key=USERNAME_KEY, max_chars=120)
        st.text_input("Application password", type="password", key=PASSWORD_KEY, max_chars=1024)
        st.form_submit_button("Sign in", on_click=attempt_login)
    message = st.session_state.pop(MESSAGE_KEY, None)
    if message:
        st.error(message)
    st.caption("Access is restricted to people who have been given the application username and password.")
    st.stop()
