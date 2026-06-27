"""Email notification via SMTP."""

from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from src.config import get_settings
from src.models import BidNotice


def _format_notice_html(notice: BidNotice) -> str:
    lines = [
        f"<li><strong>{notice.title}</strong>",
        f"<br>출처: {notice.source}",
    ]
    if notice.org_name:
        lines.append(f"<br>기관: {notice.org_name}")
    if notice.close_date:
        lines.append(f"<br>마감: {notice.close_date}")
    if notice.presumed_price:
        lines.append(f"<br>추정가: {notice.presumed_price}")
    if notice.url:
        lines.append(f'<br><a href="{notice.url}">원문 보기</a>')
    lines.append("</li>")
    return "".join(lines)


def send_email_alert(to_address: str, subject: str, notices: list[BidNotice]) -> None:
    settings = get_settings()
    if not settings.smtp_user or not settings.smtp_password:
        raise RuntimeError("SMTP credentials are not configured.")

    body_items = "".join(_format_notice_html(n) for n in notices)
    html = f"""
    <html><body>
    <p>매칭된 입찰공고 {len(notices)}건입니다.</p>
    <ul>{body_items}</ul>
    </body></html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from or settings.smtp_user
    msg["To"] = to_address
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        server.starttls()
        server.login(settings.smtp_user, settings.smtp_password)
        server.sendmail(msg["From"], [to_address], msg.as_string())
