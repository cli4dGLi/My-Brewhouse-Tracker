"""Checking that anonymous visitors cannot load data or invoke app controls."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import time

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest
from streamlit.proto.TextInput_pb2 import TextInput

from beer_loss import auth, storage

APP = str(Path(__file__).parents[1] / "streamlit_app.py")
USERNAME = "test-operator"
PASSWORD = "test-only-private-password-2026"


def element(collection, label):
    return next(item for item in collection if item.label == label)


@pytest.fixture
def live(monkeypatch, tmp_path):
    st.cache_resource.clear()
    monkeypatch.setenv("APP_MODE", "live")
    monkeypatch.setenv("APP_USERNAME", USERNAME)
    monkeypatch.setenv("APP_PASSWORD", PASSWORD)
    monkeypatch.setenv("ADMIN_PIN", "test-only-administrator-pin")
    monkeypatch.setenv("DATABASE_URL", "postgresql://test-placeholder.invalid/never-connect?sslmode=require")
    real_engine = storage.make_engine
    calls = []

    def fake_engine(url, live=False):
        calls.append(live)
        assert live is True
        return real_engine("sqlite:///" + str(tmp_path / "auth-test.db"))

    monkeypatch.setattr(storage, "make_engine", fake_engine)
    yield calls
    st.cache_resource.clear()


def sign_in(app, password=PASSWORD, username=USERNAME):
    element(app.text_input, "Username").set_value(username)
    element(app.text_input, "Application password").set_value(password)
    element(app.button, "Sign in").click().run()
    assert not app.exception
    return app


def test_anonymous_visitor_cannot_load_database_or_view_pages(live):
    app = AppTest.from_file(APP).run()
    assert not app.exception
    assert not live
    assert not app.dataframe and not app.sidebar.radio
    assert [x.label for x in app.text_input] == ["Username", "Application password"]
    assert element(app.text_input, "Application password").proto.type == TextInput.PASSWORD


@pytest.mark.parametrize("password", ["", "short", "REPLACE-WITH-A-LONG-PRIVATE-PASSWORD"])
def test_missing_weak_or_placeholder_password_fails_closed(live, monkeypatch, password):
    monkeypatch.setenv("APP_PASSWORD", password)
    app = AppTest.from_file(APP).run()
    assert not app.exception
    assert any("Sign-in is not configured" in x.value for x in app.error)
    assert not live and not app.sidebar.radio


@pytest.mark.parametrize("username,password", [(USERNAME, "wrong-password"), ("wrong-user", PASSWORD), ("", PASSWORD)])
def test_incorrect_credentials_stay_locked_and_are_cleared(live, username, password):
    app = sign_in(AppTest.from_file(APP).run(), password, username)
    assert any("Incorrect username or password" in x.value for x in app.error)
    assert element(app.text_input, "Application password").value == ""
    assert element(app.text_input, "Username").value == ""
    assert not live and not app.sidebar.radio


def test_correct_password_unlocks_pages_and_logout_clears_state(live):
    app = sign_in(AppTest.from_file(APP).run())
    assert live == [True]
    assert app.sidebar.radio
    assert auth.PASSWORD_KEY not in app.session_state
    assert auth.USERNAME_KEY not in app.session_state
    app.session_state["private_draft"] = "a private operator note"
    app.session_state["access_ADMIN_PIN"] = "test-only-administrator-pin"
    element(app.sidebar.button, "Sign out").click().run()
    assert not app.exception
    assert not app.sidebar.radio and not app.dataframe
    assert auth.AUTH_KEY not in app.session_state
    assert "private_draft" not in app.session_state
    assert "access_ADMIN_PIN" not in app.session_state


@pytest.mark.parametrize("field, age", [("last_seen", auth.IDLE_SECONDS), ("started", auth.SESSION_SECONDS)])
def test_expired_session_is_locked_before_data_access(live, monkeypatch, field, age):
    app = sign_in(AppTest.from_file(APP).run())
    app.session_state[auth.AUTH_KEY][field] -= age
    monkeypatch.setattr(storage, "load", lambda *a, **k: pytest.fail("Data loaded after expiry"))
    app.run()
    assert not app.exception and not app.sidebar.radio
    assert auth.AUTH_KEY not in app.session_state


def test_password_rotation_invalidates_existing_session(live, monkeypatch):
    app = sign_in(AppTest.from_file(APP).run())
    monkeypatch.setenv("APP_PASSWORD", PASSWORD + "-rotated")
    monkeypatch.setattr(storage, "load", lambda *a, **k: pytest.fail("Data loaded after rotation"))
    app.run()
    assert not app.exception and not app.sidebar.radio
    assert auth.AUTH_KEY not in app.session_state


@pytest.mark.parametrize("username", ["", "   ", "REPLACE-WITH-YOUR-USERNAME", "x" * 121])
def test_missing_or_invalid_username_fails_closed(live, monkeypatch, username):
    monkeypatch.setenv("APP_USERNAME", username)
    app = AppTest.from_file(APP).run()
    assert not app.exception
    assert any("Sign-in is not configured" in x.value for x in app.error)
    assert not live and not app.sidebar.radio


def test_username_change_invalidates_existing_session(live, monkeypatch):
    app = sign_in(AppTest.from_file(APP).run())
    monkeypatch.setenv("APP_USERNAME", "replacement-operator")
    monkeypatch.setattr(storage, "load", lambda *a, **k: pytest.fail("Data loaded after username change"))
    app.run()
    assert not app.exception and not app.sidebar.radio
    assert auth.AUTH_KEY not in app.session_state


def test_username_allows_surrounding_whitespace(live, monkeypatch):
    monkeypatch.setenv("APP_USERNAME", "  " + USERNAME + " ")
    app = sign_in(AppTest.from_file(APP).run(), username=" " + USERNAME + "  ")
    assert app.sidebar.radio and live


def test_unicode_password_is_supported(live, monkeypatch):
    secret = "privé-test-password-🍺-2026"
    monkeypatch.setenv("APP_PASSWORD", secret)
    app = sign_in(AppTest.from_file(APP).run(), secret)
    assert app.sidebar.radio and live


def test_lockout_is_shared_between_browser_sessions(live):
    limiter = auth.login_throttle()
    for _ in range(10):
        assert limiter.claim(time.monotonic()) == 0
    app = sign_in(AppTest.from_file(APP).run())
    assert any("Too many sign-in attempts" in x.value for x in app.error)
    assert not live and not app.sidebar.radio


def test_throttle_is_thread_safe_and_allows_retry_after_window():
    limiter = auth.LoginThrottle(limit=10, window=60)
    with ThreadPoolExecutor(max_workers=20) as pool:
        results = list(pool.map(limiter.claim, [100.0] * 100))
    assert results.count(0) == 10
    assert results.count(60) == 90
    assert limiter.claim(160.0) == 0


def test_forged_boolean_authentication_is_not_accepted():
    assert not auth.session_valid({auth.AUTH_KEY: True}, USERNAME, PASSWORD, time.monotonic())
    assert not auth.password_matches(PASSWORD + "x", PASSWORD)
