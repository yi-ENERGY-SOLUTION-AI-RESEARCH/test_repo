"""Company email domain policy for signup, login, and notification channels."""

from __future__ import annotations

from src.config import get_settings


def normalize_email(email: str) -> str:
    return email.strip().lower()


def get_allowed_domain() -> str:
    domain = get_settings().allowed_email_domain.strip().lower()
    return domain.lstrip("@")


def is_allowed_company_email(email: str) -> bool:
    normalized = normalize_email(email)
    if "@" not in normalized:
        return False
    local, domain = normalized.rsplit("@", 1)
    return bool(local) and domain == get_allowed_domain()


def company_email_error_message() -> str:
    return f"회사 이메일(@{get_allowed_domain()})만 사용할 수 있습니다."


def require_company_email(email: str) -> str:
    normalized = normalize_email(email)
    if not is_allowed_company_email(normalized):
        raise ValueError(company_email_error_message())
    return normalized
