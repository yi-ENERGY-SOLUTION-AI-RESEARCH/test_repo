"""Streamlit session/auth helpers."""

from __future__ import annotations

import streamlit as st
from supabase import Client

from src.auth.email_policy import get_allowed_domain, require_company_email
from src.auth.supabase_client import get_supabase_client
from src.db.repositories import Repository


def init_session_state() -> None:
    defaults = {
        "authenticated": False,
        "user_id": None,
        "user_email": None,
        "access_token": None,
        "refresh_token": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def get_client() -> Client:
    token = st.session_state.get("access_token")
    return get_supabase_client(service_role=False, access_token=token)


def get_user_repository() -> Repository:
    return Repository(service_role=False, access_token=st.session_state.get("access_token"))


def login(email: str, password: str) -> None:
    normalized_email = require_company_email(email)
    client = get_client()
    result = client.auth.sign_in_with_password({"email": normalized_email, "password": password})
    session = result.session
    user = result.user
    if not session or not user:
        raise RuntimeError("로그인에 실패했습니다.")
    st.session_state.authenticated = True
    st.session_state.user_id = user.id
    st.session_state.user_email = user.email
    st.session_state.access_token = session.access_token
    st.session_state.refresh_token = session.refresh_token


def signup(email: str, password: str) -> None:
    normalized_email = require_company_email(email)
    client = get_client()
    client.auth.sign_up({"email": normalized_email, "password": password})


def logout() -> None:
    try:
        get_client().auth.sign_out()
    except Exception:
        pass
    for key in list(st.session_state.keys()):
        del st.session_state[key]


def require_auth() -> str:
    init_session_state()
    if not st.session_state.authenticated or not st.session_state.user_id:
        st.warning("로그인이 필요합니다.")
        st.stop()
    return st.session_state.user_id


def allowed_domain_label() -> str:
    return f"@{get_allowed_domain()}"
