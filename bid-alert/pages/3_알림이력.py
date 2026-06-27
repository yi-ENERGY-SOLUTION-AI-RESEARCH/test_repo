"""알림 발송 이력 페이지."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")

from src.auth.session import get_user_repository, require_auth  # noqa: E402

st.set_page_config(page_title="알림 이력", page_icon="📋")
user_id = require_auth()
repo = get_user_repository()

st.title("📋 알림 발송 이력")

history = repo.list_sent_notices(user_id, limit=100)

if not history:
    st.info("발송 이력이 없습니다.")
else:
    for row in history:
        channels = ", ".join(row.get("channels") or [])
        st.markdown(
            f"**{row.get('notice_title', '-')}**  \n"
            f"출처: `{row.get('source', '-')}` | "
            f"공고ID: `{row.get('notice_id', '-')}` | "
            f"발송: {str(row.get('sent_at', ''))[:19]} | "
            f"채널: {channels or '-'}"
        )
        st.divider()
