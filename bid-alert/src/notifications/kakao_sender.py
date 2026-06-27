"""Kakao OAuth and '나에게 보내기' API."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx

from src.config import get_settings
from src.models import BidNotice

KAKAO_AUTH_URL = "https://kauth.kakao.com/oauth/authorize"
KAKAO_TOKEN_URL = "https://kauth.kakao.com/oauth/token"
KAKAO_MEMO_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"


def build_kakao_auth_url(*, state: str = "kakao") -> str:
    settings = get_settings()
    if not settings.kakao_rest_api_key:
        raise RuntimeError("KAKAO_REST_API_KEY is not configured.")

    params = {
        "client_id": settings.kakao_rest_api_key,
        "redirect_uri": settings.kakao_redirect_uri,
        "response_type": "code",
        "scope": "talk_message",
        "state": state,
    }
    return f"{KAKAO_AUTH_URL}?{urlencode(params)}"


def exchange_kakao_code(code: str) -> dict:
    settings = get_settings()
    data = {
        "grant_type": "authorization_code",
        "client_id": settings.kakao_rest_api_key,
        "redirect_uri": settings.kakao_redirect_uri,
        "code": code,
    }
    response = httpx.post(KAKAO_TOKEN_URL, data=data, timeout=20.0)
    response.raise_for_status()
    return response.json()


def refresh_kakao_token(refresh_token: str) -> dict:
    settings = get_settings()
    data = {
        "grant_type": "refresh_token",
        "client_id": settings.kakao_rest_api_key,
        "refresh_token": refresh_token,
    }
    response = httpx.post(KAKAO_TOKEN_URL, data=data, timeout=20.0)
    response.raise_for_status()
    return response.json()


def token_expires_at(expires_in: int | None) -> str | None:
    if not expires_in:
        return None
    return (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat()


def _feed_template(notices: list[BidNotice]) -> dict:
    first = notices[0]
    description_lines = []
    for notice in notices[:5]:
        line = notice.title
        if notice.close_date:
            line += f" (마감: {notice.close_date})"
        description_lines.append(line)
    if len(notices) > 5:
        description_lines.append(f"... 외 {len(notices) - 5}건")

    content = {
        "title": f"입찰공고 알림 {len(notices)}건",
        "description": "\n".join(description_lines),
    }
    if first.url:
        content["link"] = {"web_url": first.url, "mobile_web_url": first.url}
    return {
        "object_type": "feed",
        "content": content,
        "buttons": [
            {
                "title": "원문 보기",
                "link": {"web_url": first.url or "", "mobile_web_url": first.url or ""},
            }
        ]
        if first.url
        else [],
    }


def send_kakao_memo(access_token: str, notices: list[BidNotice]) -> None:
    template = _feed_template(notices)
    data = {"template_object": json.dumps(template, ensure_ascii=False)}
    headers = {"Authorization": f"Bearer {access_token}"}
    response = httpx.post(KAKAO_MEMO_URL, headers=headers, data=data, timeout=20.0)
    response.raise_for_status()


def get_valid_access_token(
    *,
    access_token: str,
    refresh_token: str | None,
    expires_at: str | None,
) -> tuple[str, dict | None]:
    """Return a valid access token; refresh if expired. Second value is refresh payload if refreshed."""
    if expires_at:
        try:
            expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            if expiry > datetime.now(timezone.utc) + timedelta(minutes=1):
                return access_token, None
        except ValueError:
            pass

    if not refresh_token:
        return access_token, None

    payload = refresh_kakao_token(refresh_token)
    return payload["access_token"], payload
