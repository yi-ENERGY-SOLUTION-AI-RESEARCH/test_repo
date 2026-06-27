"""입찰공고 알림 Streamlit 앱 — 메인 대시보드."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")

from src.streamlit_secrets import load_streamlit_secrets  # noqa: E402

load_streamlit_secrets()

from src.alert_engine import AlertEngine  # noqa: E402
from src.auth.session import get_user_repository, init_session_state, login, logout, require_auth, signup  # noqa: E402
from src.notifications.kakao_sender import (  # noqa: E402
    build_kakao_auth_url,
    exchange_kakao_code,
    token_expires_at,
)

st.set_page_config(page_title="입찰공고 알림", page_icon="📢", layout="wide")


def handle_kakao_callback(user_id: str) -> None:
    params = st.query_params
    code = params.get("code")
    state = params.get("state")
    if not code or state != "kakao":
        return

    try:
        token_data = exchange_kakao_code(code)
        repo = get_user_repository()
        repo.upsert_oauth_token(
            user_id,
            "kakao",
            token_data["access_token"],
            token_data.get("refresh_token"),
            token_expires_at(token_data.get("expires_in")),
        )
        repo.upsert_channel(user_id, "kakao", {"connected": True}, is_enabled=True)
        st.success("카카오톡 연결이 완료되었습니다.")
    except Exception as exc:
        st.error(f"카카오 연결 실패: {exc}")
    finally:
        st.query_params.clear()


def render_auth_form() -> None:
    st.title("📢 입찰공고 알림")
    st.caption("공공데이터 OPEN API 기반 입찰공고 키워드 알림 서비스")

    tab_login, tab_signup = st.tabs(["로그인", "회원가입"])
    with tab_login:
        email = st.text_input("이메일", key="login_email")
        password = st.text_input("비밀번호", type="password", key="login_password")
        if st.button("로그인", type="primary"):
            try:
                login(email, password)
                st.rerun()
            except Exception as exc:
                st.error(f"로그인 실패: {exc}")

    with tab_signup:
        new_email = st.text_input("이메일", key="signup_email")
        new_password = st.text_input("비밀번호", type="password", key="signup_password")
        if st.button("회원가입"):
            try:
                signup(new_email, new_password)
                st.success("회원가입 완료. 이메일 확인 후 로그인하세요.")
            except Exception as exc:
                st.error(f"회원가입 실패: {exc}")


def render_dashboard(user_id: str) -> None:
    st.title("대시보드")
    st.caption(f"로그인: {st.session_state.user_email}")

    repo = get_user_repository()
    rules = repo.list_alert_rules(user_id)
    history = repo.list_sent_notices(user_id, limit=10)

    col1, col2, col3 = st.columns(3)
    col1.metric("활성 규칙", sum(1 for r in rules if r.is_active))
    col2.metric("전체 규칙", len(rules))
    col3.metric("최근 발송", len(history))

    st.subheader("지금 테스트 조회")
    active_rules = [r for r in rules if r.is_active]
    if not active_rules:
        st.info("활성 알림 규칙이 없습니다. '알림 규칙' 페이지에서 설정하세요.")
    else:
        rule_names = {f"{r.name} ({r.id[:8]})": r for r in active_rules}
        selected = st.selectbox("규칙 선택", list(rule_names.keys()))
        rule = rule_names[selected]

        if st.button("매칭 공고 미리보기"):
            engine = AlertEngine(repo=get_user_repository())
            matches = engine.preview_rule(rule)
            if matches:
                for notice in matches[:20]:
                    st.markdown(f"- **{notice.title}** ({notice.source}) — 마감: {notice.close_date or '-'}")
                if len(matches) > 20:
                    st.caption(f"외 {len(matches) - 20}건")
            else:
                st.info("매칭된 공고가 없습니다.")

        if st.button("지금 알림 발송 (테스트)"):
            channels = repo.list_channels(user_id, enabled_only=True)
            if not channels:
                st.warning("연결된 알림 채널이 없습니다. '채널 연결' 페이지를 확인하세요.")
            else:
                engine = AlertEngine(repo=get_user_repository())
                notices = engine.fetch_for_sources(rule.sources)
                new_matches = engine.find_new_matches(rule, notices)
                if not new_matches:
                    st.info("신규 매칭 공고가 없습니다 (이미 발송했거나 매칭 없음).")
                else:
                    used = engine.dispatch_notifications(rule, new_matches, channels)
                    st.success(f"{len(new_matches)}건 알림 발송 완료 — 채널: {', '.join(used)}")

    st.subheader("최근 알림 이력")
    if history:
        for row in history:
            st.markdown(
                f"- {row.get('sent_at', '')[:19]} | **{row.get('notice_title', '')}** "
                f"({row.get('source', '')}) → {', '.join(row.get('channels') or [])}"
            )
    else:
        st.caption("아직 발송 이력이 없습니다.")


def main() -> None:
    init_session_state()

    if st.session_state.authenticated:
        user_id = require_auth()
        handle_kakao_callback(user_id)

        with st.sidebar:
            st.markdown(f"**{st.session_state.user_email}**")
            if st.button("로그아웃"):
                logout()
                st.rerun()

        render_dashboard(user_id)
    else:
        render_auth_form()


if __name__ == "__main__":
    main()
