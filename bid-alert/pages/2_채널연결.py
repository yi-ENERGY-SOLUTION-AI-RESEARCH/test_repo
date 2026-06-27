"""채널 연결 페이지 — 이메일, Slack, 카카오."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")

from src.auth.email_policy import company_email_error_message, require_company_email  # noqa: E402
from src.auth.session import allowed_domain_label, get_user_repository, require_auth  # noqa: E402
from src.notifications.kakao_sender import build_kakao_auth_url  # noqa: E402

st.set_page_config(page_title="채널 연결", page_icon="🔗")
user_id = require_auth()
repo = get_user_repository()

st.title("🔗 알림 채널 연결")

channels = {c.channel: c for c in repo.list_channels(user_id)}

# --- Email ---
st.subheader("📧 이메일")
st.caption(f"알림 수신 주소도 {allowed_domain_label()} 회사 메일만 등록할 수 있습니다.")
email_channel = channels.get("email")
default_email = (email_channel.config.get("email_address") if email_channel else st.session_state.get("user_email", ""))
email_address = st.text_input("알림 수신 이메일", value=default_email or "")
email_enabled = st.checkbox("이메일 알림 사용", value=email_channel.is_enabled if email_channel else True, key="email_on")
if st.button("이메일 저장"):
    try:
        normalized = require_company_email(email_address)
        repo.upsert_channel(user_id, "email", {"email_address": normalized}, is_enabled=email_enabled)
        st.success("이메일 설정 저장 완료")
    except ValueError:
        st.error(company_email_error_message())

st.divider()

# --- Slack ---
st.subheader("💬 Slack")
st.caption("Slack 앱에서 Incoming Webhook URL을 생성해 붙여넣으세요.")
slack_channel = channels.get("slack")
webhook_url = st.text_input(
    "Slack Webhook URL",
    value=slack_channel.config.get("webhook_url", "") if slack_channel else "",
    type="password",
)
slack_enabled = st.checkbox("Slack 알림 사용", value=slack_channel.is_enabled if slack_channel else False, key="slack_on")
if st.button("Slack 저장"):
    repo.upsert_channel(user_id, "slack", {"webhook_url": webhook_url}, is_enabled=slack_enabled)
    st.success("Slack 설정 저장 완료")

st.divider()

# --- Kakao ---
st.subheader("💛 카카오톡 (나에게 보내기)")
st.warning(
    "카카오 '나에게 보내기'는 **푸시 알림이 없고** 나와의 채팅에 메모만 남습니다.",
    icon="⚠️",
)

kakao_channel = channels.get("kakao")
kakao_token = repo.get_oauth_token(user_id, "kakao")
connected = bool(kakao_token or (kakao_channel and kakao_channel.config.get("connected")))

if connected:
    st.success("카카오톡 연결됨")
    kakao_enabled = st.checkbox("카카오 알림 사용", value=kakao_channel.is_enabled if kakao_channel else True, key="kakao_on")
    if st.button("카카오 설정 저장"):
        repo.upsert_channel(user_id, "kakao", {"connected": True}, is_enabled=kakao_enabled)
        st.success("저장 완료")
    if st.button("카카오 연결 해제"):
        repo.delete_oauth_token(user_id, "kakao")
        repo.upsert_channel(user_id, "kakao", {"connected": False}, is_enabled=False)
        st.rerun()
else:
    try:
        auth_url = build_kakao_auth_url(state="kakao")
        st.link_button("카카오톡 연결하기", auth_url, type="primary")
        st.caption("연결 후 이 페이지로 돌아옵니다. Redirect URI가 Kakao Developers에 등록되어 있어야 합니다.")
    except RuntimeError as exc:
        st.error(str(exc))
