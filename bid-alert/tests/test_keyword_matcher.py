"""Keyword matcher tests."""

from src.matching.keyword_matcher import filter_notices, matches_keywords, parse_keywords
from src.models import BidNotice


def test_parse_keywords():
    assert parse_keywords("a, b\nc") == ["a", "b", "c"]


def test_or_match():
    notice = BidNotice(source="kepco", notice_id="1", title="전력계통 해석 및 PSS/E 용역")
    assert matches_keywords(notice, ["PSS/E"], match_mode="or")
    assert matches_keywords(notice, ["없는키워드"], match_mode="or") is False


def test_and_match():
    notice = BidNotice(source="kepco", notice_id="1", title="전력계통 해석 PSS/E")
    assert matches_keywords(notice, ["전력계통", "PSS/E"], match_mode="and")
    assert matches_keywords(notice, ["전력계통", "없음"], match_mode="and") is False


def test_filter_notices():
    notices = [
        BidNotice(source="kepco", notice_id="1", title="A PSS/E"),
        BidNotice(source="kepco", notice_id="2", title="B only"),
    ]
    result = filter_notices(notices, ["PSS/E"], match_mode="or")
    assert len(result) == 1
    assert result[0].notice_id == "1"
