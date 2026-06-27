"""Company email domain policy tests."""

import pytest

from src.auth.email_policy import (
    company_email_error_message,
    is_allowed_company_email,
    normalize_email,
    require_company_email,
)


def test_normalize_email():
    assert normalize_email("  KCH@YesYoungin.com ") == "kch@yesyoungin.com"


def test_allowed_company_email():
    assert is_allowed_company_email("kch@yesyoungin.com")
    assert not is_allowed_company_email("user@gmail.com")
    assert not is_allowed_company_email("invalid")
    assert not is_allowed_company_email("@yesyoungin.com")


def test_require_company_email():
    assert require_company_email("KCH@yesyoungin.com") == "kch@yesyoungin.com"
    with pytest.raises(ValueError, match="yesyoungin.com"):
        require_company_email("other@gmail.com")


def test_error_message():
    assert "yesyoungin.com" in company_email_error_message()
