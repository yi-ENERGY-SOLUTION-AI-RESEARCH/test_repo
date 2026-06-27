"""Keyword matching for bid notices."""

from __future__ import annotations

from src.models import BidNotice


def parse_keywords(text: str) -> list[str]:
    if not text or not text.strip():
        return []
    parts: list[str] = []
    for line in text.replace(",", "\n").splitlines():
        keyword = line.strip()
        if keyword:
            parts.append(keyword)
    return parts


def _normalize(text: str) -> str:
    return text.lower().replace(" ", "")


def matches_keywords(
    notice: BidNotice,
    keywords: list[str],
    *,
    match_mode: str = "or",
) -> bool:
    if not keywords:
        return False

    haystack = _normalize(
        " ".join(
            filter(
                None,
                [notice.title, notice.org_name or "", notice.progress or ""],
            )
        )
    )
    normalized_keywords = [_normalize(k) for k in keywords if k.strip()]

    if match_mode == "and":
        return all(k in haystack for k in normalized_keywords)
    return any(k in haystack for k in normalized_keywords)


def filter_notices(
    notices: list[BidNotice],
    keywords: list[str],
    *,
    match_mode: str = "or",
) -> list[BidNotice]:
    return [n for n in notices if matches_keywords(n, keywords, match_mode=match_mode)]
