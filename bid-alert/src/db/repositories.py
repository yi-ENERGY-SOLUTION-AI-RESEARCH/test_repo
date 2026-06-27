"""Database access layer."""

from __future__ import annotations

from typing import Any

from src.auth.supabase_client import get_supabase_client
from src.models import AlertRule, NotificationChannel


def _parse_keywords(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(k).strip() for k in value if str(k).strip()]
    return [k.strip() for k in str(value).split(",") if k.strip()]


class Repository:
    def __init__(self, *, service_role: bool = False, access_token: str | None = None) -> None:
        self.client = get_supabase_client(service_role=service_role, access_token=access_token)
        self.service_role = service_role

    # --- alert_rules ---

    def list_alert_rules(self, user_id: str | None = None, *, active_only: bool = False) -> list[AlertRule]:
        query = self.client.table("alert_rules").select("*")
        if user_id:
            query = query.eq("user_id", user_id)
        if active_only:
            query = query.eq("is_active", True)
        rows = query.order("created_at", desc=True).execute().data or []
        return [self._row_to_rule(row) for row in rows]

    def upsert_alert_rule(
        self,
        user_id: str,
        *,
        rule_id: str | None,
        name: str,
        keywords: list[str],
        match_mode: str,
        sources: list[str],
        notify_time: str,
        is_active: bool,
    ) -> AlertRule:
        payload = {
            "user_id": user_id,
            "name": name,
            "keywords": keywords,
            "match_mode": match_mode,
            "sources": sources,
            "notify_time": notify_time,
            "is_active": is_active,
        }
        if rule_id:
            row = self.client.table("alert_rules").update(payload).eq("id", rule_id).eq("user_id", user_id).execute()
        else:
            row = self.client.table("alert_rules").insert(payload).execute()
        data = (row.data or [None])[0]
        if not data:
            raise RuntimeError("Failed to save alert rule.")
        return self._row_to_rule(data)

    def delete_alert_rule(self, user_id: str, rule_id: str) -> None:
        self.client.table("alert_rules").delete().eq("id", rule_id).eq("user_id", user_id).execute()

    def _row_to_rule(self, row: dict[str, Any]) -> AlertRule:
        notify_time = row.get("notify_time", "08:00:00")
        if isinstance(notify_time, str) and len(notify_time) == 5:
            notify_time = f"{notify_time}:00"
        return AlertRule(
            id=row["id"],
            user_id=row["user_id"],
            name=row.get("name", "기본 규칙"),
            keywords=_parse_keywords(row.get("keywords")),
            match_mode=row.get("match_mode", "or"),
            sources=row.get("sources") or ["kepco"],
            notify_time=str(notify_time),
            is_active=bool(row.get("is_active", True)),
        )

    # --- notification_channels ---

    def list_channels(self, user_id: str | None = None, *, enabled_only: bool = False) -> list[NotificationChannel]:
        query = self.client.table("notification_channels").select("*")
        if user_id:
            query = query.eq("user_id", user_id)
        if enabled_only:
            query = query.eq("is_enabled", True)
        rows = query.execute().data or []
        return [self._row_to_channel(row) for row in rows]

    def upsert_channel(
        self,
        user_id: str,
        channel: str,
        config: dict[str, Any],
        *,
        is_enabled: bool = True,
    ) -> NotificationChannel:
        payload = {
            "user_id": user_id,
            "channel": channel,
            "config": config,
            "is_enabled": is_enabled,
        }
        row = self.client.table("notification_channels").upsert(payload, on_conflict="user_id,channel").execute()
        data = (row.data or [None])[0]
        if not data:
            raise RuntimeError(f"Failed to save {channel} channel.")
        return self._row_to_channel(data)

    def _row_to_channel(self, row: dict[str, Any]) -> NotificationChannel:
        return NotificationChannel(
            id=row["id"],
            user_id=row["user_id"],
            channel=row["channel"],
            config=row.get("config") or {},
            is_enabled=bool(row.get("is_enabled", True)),
        )

    # --- sent_notices ---

    def is_notice_sent(self, user_id: str, source: str, notice_id: str) -> bool:
        row = (
            self.client.table("sent_notices")
            .select("id")
            .eq("user_id", user_id)
            .eq("source", source)
            .eq("notice_id", notice_id)
            .limit(1)
            .execute()
        )
        return bool(row.data)

    def record_sent_notice(
        self,
        user_id: str,
        rule_id: str | None,
        source: str,
        notice_id: str,
        notice_title: str,
        channels: list[str],
    ) -> None:
        self.client.table("sent_notices").insert(
            {
                "user_id": user_id,
                "rule_id": rule_id,
                "source": source,
                "notice_id": notice_id,
                "notice_title": notice_title,
                "channels": channels,
            }
        ).execute()

    def list_sent_notices(self, user_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        rows = (
            self.client.table("sent_notices")
            .select("*")
            .eq("user_id", user_id)
            .order("sent_at", desc=True)
            .limit(limit)
            .execute()
        )
        return rows.data or []

    # --- oauth_tokens ---

    def get_oauth_token(self, user_id: str, provider: str = "kakao") -> dict[str, Any] | None:
        row = (
            self.client.table("oauth_tokens")
            .select("*")
            .eq("user_id", user_id)
            .eq("provider", provider)
            .limit(1)
            .execute()
        )
        return (row.data or [None])[0]

    def upsert_oauth_token(
        self,
        user_id: str,
        provider: str,
        access_token: str,
        refresh_token: str | None,
        expires_at: str | None,
    ) -> None:
        self.client.table("oauth_tokens").upsert(
            {
                "user_id": user_id,
                "provider": provider,
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_at": expires_at,
            },
            on_conflict="user_id,provider",
        ).execute()

    def delete_oauth_token(self, user_id: str, provider: str = "kakao") -> None:
        self.client.table("oauth_tokens").delete().eq("user_id", user_id).eq("provider", provider).execute()
