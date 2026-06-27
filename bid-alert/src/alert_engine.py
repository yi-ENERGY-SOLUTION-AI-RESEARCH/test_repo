"""Core alert orchestration: fetch, match, dedupe, notify."""

from __future__ import annotations

import logging
from datetime import date, timedelta

from src.api.kepco_client import KepcoClient
from src.api.narajangteo_client import NarajangteoClient
from src.db.repositories import Repository
from src.matching.keyword_matcher import filter_notices
from src.models import AlertRule, BidNotice, NotificationChannel
from src.notifications.email_sender import send_email_alert
from src.notifications.kakao_sender import get_valid_access_token, send_kakao_memo
from src.notifications.slack_sender import send_slack_alert

logger = logging.getLogger(__name__)


class AlertEngine:
    def __init__(self, repo: Repository | None = None) -> None:
        self.repo = repo or Repository(service_role=True)
        self.kepco = KepcoClient()
        self.narajangteo = NarajangteoClient()

    def fetch_for_sources(self, sources: list[str], *, days_back: int = 7) -> list[BidNotice]:
        end = date.today()
        start = end - timedelta(days=days_back)
        notices: list[BidNotice] = []

        if "kepco" in sources:
            notices.extend(self.kepco.fetch_notices(start_date=start, end_date=end))
        if "narajangteo" in sources:
            notices.extend(
                self.narajangteo.fetch_service_notices(
                    start_date=start,
                    end_date=end,
                    org_keyword="한국전력",
                )
            )
        return notices

    def find_new_matches(self, rule: AlertRule, notices: list[BidNotice]) -> list[BidNotice]:
        matched = filter_notices(notices, rule.keywords, match_mode=rule.match_mode)
        new_notices: list[BidNotice] = []
        for notice in matched:
            if notice.source not in rule.sources:
                continue
            if self.repo.is_notice_sent(rule.user_id, notice.source, notice.notice_id):
                continue
            new_notices.append(notice)
        return new_notices

    def dispatch_notifications(
        self,
        rule: AlertRule,
        notices: list[BidNotice],
        channels: list[NotificationChannel],
    ) -> list[str]:
        if not notices:
            return []

        subject = f"[입찰알림] {rule.name} — {len(notices)}건"
        used_channels: list[str] = []

        for channel in channels:
            if not channel.is_enabled:
                continue
            try:
                if channel.channel == "email":
                    email = channel.config.get("email_address")
                    if email:
                        send_email_alert(email, subject, notices)
                        used_channels.append("email")
                elif channel.channel == "slack":
                    webhook = channel.config.get("webhook_url")
                    if webhook:
                        send_slack_alert(webhook, notices, text=subject)
                        used_channels.append("slack")
                elif channel.channel == "kakao":
                    token_row = self.repo.get_oauth_token(rule.user_id, "kakao")
                    if token_row:
                        access_token, refreshed = get_valid_access_token(
                            access_token=token_row["access_token"],
                            refresh_token=token_row.get("refresh_token"),
                            expires_at=token_row.get("expires_at"),
                        )
                        if refreshed:
                            from src.notifications.kakao_sender import token_expires_at

                            self.repo.upsert_oauth_token(
                                rule.user_id,
                                "kakao",
                                access_token,
                                refreshed.get("refresh_token") or token_row.get("refresh_token"),
                                token_expires_at(refreshed.get("expires_in")),
                            )
                        send_kakao_memo(access_token, notices)
                        used_channels.append("kakao")
            except Exception as exc:
                logger.exception(
                    "Failed to send via %s for user %s: %s",
                    channel.channel,
                    rule.user_id,
                    exc,
                )

        for notice in notices:
            self.repo.record_sent_notice(
                rule.user_id,
                rule.id,
                notice.source,
                notice.notice_id,
                notice.title,
                used_channels,
            )

        return used_channels

    def run_rule(self, rule: AlertRule, channels: list[NotificationChannel]) -> list[BidNotice]:
        notices = self.fetch_for_sources(rule.sources)
        new_matches = self.find_new_matches(rule, notices)
        if new_matches:
            self.dispatch_notifications(rule, new_matches, channels)
        return new_matches

    def run_all_active_rules(self) -> dict[str, int]:
        rules = self.repo.list_alert_rules(active_only=True)
        stats = {"rules": 0, "notices": 0, "errors": 0}

        channels_by_user: dict[str, list[NotificationChannel]] = {}
        for rule in rules:
            stats["rules"] += 1
            if rule.user_id not in channels_by_user:
                channels_by_user[rule.user_id] = self.repo.list_channels(rule.user_id, enabled_only=True)
            user_channels = channels_by_user[rule.user_id]
            if not user_channels:
                continue
            try:
                matched = self.run_rule(rule, user_channels)
                stats["notices"] += len(matched)
            except Exception:
                stats["errors"] += 1
                logger.exception("Rule %s failed", rule.id)

        return stats

    def preview_rule(self, rule: AlertRule) -> list[BidNotice]:
        notices = self.fetch_for_sources(rule.sources)
        return filter_notices(notices, rule.keywords, match_mode=rule.match_mode)
