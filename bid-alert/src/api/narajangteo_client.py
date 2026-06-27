"""조달청 나라장터 입찰공고정보서비스 — 용역 API client.

Docs: https://www.data.go.kr/data/15129394/openapi.do
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any
import httpx

from src.config import get_settings
from src.models import BidNotice

logger = logging.getLogger(__name__)

BASE_URL = "http://apis.data.go.kr/1230000/ad/BidPublicInfoService"
OPERATION = "getBidPblancListInfoServc"
NARA_NOTICE_BASE = "https://www.g2b.go.kr/"


def _first_value(item: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = item.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _normalize_item(item: dict[str, Any]) -> BidNotice | None:
    notice_id = _first_value(item, "bidNtceNo", "bidntceno")
    title = _first_value(item, "bidNtceNm", "bidntcenm")
    if not notice_id or not title:
        return None

    ord = _first_value(item, "bidNtceOrd", "bidntceord") or "0"
    notice_key = f"{notice_id}-{ord}"

    return BidNotice(
        source="narajangteo",
        notice_id=notice_key,
        title=title,
        close_date=_first_value(item, "bidClseDt", "bidclsedt"),
        progress=_first_value(item, "ntceInsttNm", "ntceinsttnm"),
        org_name=_first_value(item, "dminsttNm", "dminsttnm", "ntceInsttNm", "ntceinsttnm"),
        presumed_price=_first_value(item, "asignBdgtAmt", "asignbdgtamt", "presmptPrce", "presmptprce"),
        url=NARA_NOTICE_BASE,
        raw=item,
    )


def _extract_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    body = payload.get("response", {}).get("body", {})
    items_container = body.get("items")
    if not items_container:
        return []
    if isinstance(items_container, dict):
        item = items_container.get("item")
        if item is None:
            return []
        return item if isinstance(item, list) else [item]
    return items_container if isinstance(items_container, list) else []


class NarajangteoClient:
    def __init__(self, service_key: str | None = None) -> None:
        settings = get_settings()
        self.service_key = service_key or settings.data_go_kr_api_key

    def fetch_service_notices(
        self,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        org_keyword: str | None = None,
        page_size: int = 100,
        max_pages: int = 10,
    ) -> list[BidNotice]:
        if not self.service_key:
            logger.warning("DATA_GO_KR_API_KEY is not set; skipping Narajangteo fetch.")
            return []

        end = end_date or date.today()
        start = start_date or (end - timedelta(days=7))

        bgn = datetime.combine(start, datetime.min.time()).strftime("%Y%m%d0000")
        end_dt = datetime.combine(end, datetime.max.time()).strftime("%Y%m%d2359")

        notices: list[BidNotice] = []
        for page in range(1, max_pages + 1):
            params = {
                "serviceKey": self.service_key,
                "pageNo": str(page),
                "numOfRows": str(page_size),
                "type": "json",
                "inqryDiv": "1",
                "inqryBgnDt": bgn,
                "inqryEndDt": end_dt,
            }

            url = f"{BASE_URL}/{OPERATION}"
            try:
                response = httpx.get(url, params=params, timeout=30.0)
                response.raise_for_status()
                payload = response.json()
            except Exception as exc:
                logger.exception("Narajangteo API request failed on page %s: %s", page, exc)
                break

            items = _extract_items(payload)
            if not items:
                break

            for item in items:
                notice = _normalize_item(item)
                if not notice:
                    continue
                if org_keyword:
                    org = (notice.org_name or "").lower()
                    if org_keyword.lower() not in org and org_keyword.lower() not in notice.title.lower():
                        continue
                notices.append(notice)

            total_count = int(payload.get("response", {}).get("body", {}).get("totalCount", 0) or 0)
            if page * page_size >= total_count or len(items) < page_size:
                break

        return notices
