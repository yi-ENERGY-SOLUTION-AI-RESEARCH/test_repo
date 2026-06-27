"""Slack Incoming Webhook notifications."""

from __future__ import annotations

import httpx

from src.models import BidNotice


def _notice_blocks(notices: list[BidNotice]) -> list[dict]:
    blocks: list[dict] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"입찰공고 알림 ({len(notices)}건)"},
        }
    ]
    for notice in notices[:10]:
        fields = [
            {"type": "mrkdwn", "text": f"*공고명*\n{notice.title}"},
            {"type": "mrkdwn", "text": f"*출처*\n{notice.source}"},
        ]
        if notice.close_date:
            fields.append({"type": "mrkdwn", "text": f"*마감*\n{notice.close_date}"})
        if notice.org_name:
            fields.append({"type": "mrkdwn", "text": f"*기관*\n{notice.org_name}"})
        blocks.append({"type": "section", "fields": fields[:4]})
        if notice.url:
            blocks.append(
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "원문 보기"},
                            "url": notice.url,
                        }
                    ],
                }
            )
        blocks.append({"type": "divider"})
    if len(notices) > 10:
        blocks.append(
            {
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": f"외 {len(notices) - 10}건 더 있습니다."}],
            }
        )
    return blocks


def send_slack_alert(webhook_url: str, notices: list[BidNotice], *, text: str | None = None) -> None:
    payload = {
        "text": text or f"매칭 입찰공고 {len(notices)}건",
        "blocks": _notice_blocks(notices),
    }
    response = httpx.post(webhook_url, json=payload, timeout=20.0)
    response.raise_for_status()
