"""한국전력공사 전자입찰계약정보 API client.

Docs: https://www.data.go.kr/data/15148223/openapi.do
Uses 전력데이터개방포털 (bigdata.kepco.co.kr) with apiKey.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

import httpx

from src.config import get_settings
from src.models import BidNotice

logger = logging.getLogger(__name__)

KEPCO_NOTICE_URL = "https://srm.kepco.net/bid/Common/Menu/BizMainFrm.jsp"


def _first_value(item: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = item.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _normalize_item(item: dict[str, Any]) -> BidNotice | None:
    notice_id = _first_value(item, "ntNum", "ntnum", "noticeNo", "bidNo")
    title = _first_value(item, "ntTitle", "nttitle", "bidTitle", "title")
    if not notice_id or not title:
        return None

    return BidNotice(
        source="kepco",
        notice_id=notice_id,
        title=title,
        close_date=_first_value(item, "ntCloseDate", "ntclosedate", "closeDate", "enddatetime"),
        progress=_first_value(item, "ntProgress", "ntprogress", "progress", "status"),
        org_name="한국전력공사",
        presumed_price=_first_value(item, "presumedprice", "presumedPrice", "estimatedPrice"),
        url=KEPCO_NOTICE_URL,
        raw=item,
    )


def _extract_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if "data" in payload and isinstance(payload["data"], list):
        return payload["data"]

    body = payload.get("response", payload)
    if isinstance(body, dict):
        items_container = body.get("body", body).get("items", body.get("items"))
        if isinstance(items_container, dict):
            item = items_container.get("item")
            if item is None:
                return []
            return item if isinstance(item, list) else [item]
        if isinstance(items_container, list):
            return items_container
    return []


class KepcoClient:
    def __init__(self, api_key: str | None = None, api_url: str | None = None) -> None:
        settings = get_settings()
        self.api_key = api_key or settings.kepco_api_key
        self.api_url = api_url or settings.kepco_api_url

    def fetch_notices(
        self,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        title_keyword: str | None = None,
        page_size: int = 100,
        max_pages: int = 10,
    ) -> list[BidNotice]:
        if not self.api_key:
            logger.warning("KEPCO_API_KEY is not set; skipping KEPCO fetch.")
            return []

        end = end_date or date.today()
        start = start_date or (end - timedelta(days=7))

        notices: list[BidNotice] = []
        for page in range(1, max_pages + 1):
            params: dict[str, Any] = {
                "apiKey": self.api_key,
                "returnType": "json",
                "pageNo": page,
                "numOfRows": page_size,
                "pageSize": page_size,
                "strDateS": start.strftime("%Y%m%d"),
                "strDateE": end.strftime("%Y%m%d"),
            }
            if title_keyword:
                params["ntTitle"] = title_keyword

            try:
                response = httpx.get(self.api_url, params=params, timeout=30.0)
                response.raise_for_status()
                payload = response.json()
            except Exception as exc:
                logger.exception("KEPCO API request failed on page %s: %s", page, exc)
                break

            items = _extract_items(payload)
            if not items:
                break

            for item in items:
                notice = _normalize_item(item)
                if notice:
                    notices.append(notice)

            if len(items) < page_size:
                break

        return notices
