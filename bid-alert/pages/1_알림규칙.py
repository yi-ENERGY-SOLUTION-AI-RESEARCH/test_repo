"""알림 규칙 설정 페이지."""

from __future__ import annotations

import sys
from datetime import time
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")

from src.auth.session import get_user_repository, require_auth  # noqa: E402
from src.db.repositories import Repository  # noqa: E402
from src.matching.keyword_matcher import parse_keywords  # noqa: E402

st.set_page_config(page_title="알림 규칙", page_icon="⚙️")
user_id = require_auth()
repo = get_user_repository()

st.title("⚙️ 알림 규칙 설정")
st.caption("관심 키워드와 데이터 소스를 설정하세요.")

rules = repo.list_alert_rules(user_id)

with st.expander("새 규칙 추가", expanded=not rules):
    name = st.text_input("규칙 이름", value="한전 PSS/E 용역", key="new_name")
    keywords_text = st.text_area(
        "관심 키워드 (줄바꿈 또는 쉼표로 구분)",
        value="전력계통 해석\nPSS/E\n전력계통영향평가",
        key="new_keywords",
        height=120,
    )
    match_mode = st.radio("매칭 방식", ["or", "and"], format_func=lambda x: "하나라도 포함 (OR)" if x == "or" else "모두 포함 (AND)", horizontal=True)
    sources = st.multiselect(
        "데이터 소스",
        ["kepco", "narajangteo"],
        default=["kepco"],
        format_func=lambda x: "한전 전자입찰" if x == "kepco" else "나라장터 용역",
    )
    notify_time = st.time_input("매일 알림 시각 (KST)", value=time(8, 0))
    is_active = st.checkbox("활성화", value=True)

    if st.button("규칙 저장", type="primary"):
        keywords = parse_keywords(keywords_text)
        if not keywords:
            st.error("키워드를 1개 이상 입력하세요.")
        elif not sources:
            st.error("데이터 소스를 1개 이상 선택하세요.")
        else:
            time_str = notify_time.strftime("%H:%M:%S") if notify_time else "08:00:00"
            repo.upsert_alert_rule(
                user_id,
                rule_id=None,
                name=name,
                keywords=keywords,
                match_mode=match_mode,
                sources=sources,
                notify_time=time_str,
                is_active=is_active,
            )
            st.success("규칙이 저장되었습니다.")
            st.rerun()

st.divider()
st.subheader("등록된 규칙")

if not rules:
    st.info("등록된 규칙이 없습니다.")
else:
    for rule in rules:
        with st.container(border=True):
            st.markdown(f"**{rule.name}** {'✅' if rule.is_active else '⏸️'}")
            st.caption(f"키워드: {', '.join(rule.keywords)} | {rule.match_mode.upper()} | {', '.join(rule.sources)} | {rule.notify_time[:5]}")
            if st.button("삭제", key=f"del_{rule.id}"):
                repo.delete_alert_rule(user_id, rule.id)
                st.rerun()
