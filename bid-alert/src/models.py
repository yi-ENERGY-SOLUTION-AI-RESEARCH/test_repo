"""Shared data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class BidNotice:
    source: str
    notice_id: str
    title: str
    close_date: str | None = None
    progress: str | None = None
    org_name: str | None = None
    presumed_price: str | None = None
    url: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class AlertRule:
    id: str
    user_id: str
    name: str
    keywords: list[str]
    match_mode: str
    sources: list[str]
    notify_time: str
    is_active: bool


@dataclass
class NotificationChannel:
    id: str
    user_id: str
    channel: str
    config: dict[str, Any]
    is_enabled: bool


@dataclass
class AlertResult:
    rule: AlertRule
    notices: list[BidNotice]
    channels_used: list[str]
    sent_at: datetime
