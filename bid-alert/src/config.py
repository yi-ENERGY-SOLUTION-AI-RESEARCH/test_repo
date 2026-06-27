"""Application configuration."""

from __future__ import annotations

import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""

    data_go_kr_api_key: str = ""
    kepco_api_key: str = ""
    kepco_api_url: str = "https://bigdata.kepco.co.kr/openapi/v1/contract/electBidContInfo.do"

    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""

    kakao_rest_api_key: str = ""
    kakao_redirect_uri: str = "http://localhost:8501"
    app_base_url: str = "http://localhost:8501"


@lru_cache
def get_settings() -> Settings:
    return Settings(
        supabase_url=os.getenv("SUPABASE_URL", ""),
        supabase_anon_key=os.getenv("SUPABASE_ANON_KEY", ""),
        supabase_service_role_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""),
        data_go_kr_api_key=os.getenv("DATA_GO_KR_API_KEY", ""),
        kepco_api_key=os.getenv("KEPCO_API_KEY", ""),
        kepco_api_url=os.getenv(
            "KEPCO_API_URL",
            "https://bigdata.kepco.co.kr/openapi/v1/contract/electBidContInfo.do",
        ),
        smtp_host=os.getenv("SMTP_HOST", "smtp.gmail.com"),
        smtp_port=int(os.getenv("SMTP_PORT", "587")),
        smtp_user=os.getenv("SMTP_USER", ""),
        smtp_password=os.getenv("SMTP_PASSWORD", ""),
        smtp_from=os.getenv("SMTP_FROM", os.getenv("SMTP_USER", "")),
        kakao_rest_api_key=os.getenv("KAKAO_REST_API_KEY", ""),
        kakao_redirect_uri=os.getenv("KAKAO_REDIRECT_URI", "http://localhost:8501"),
        app_base_url=os.getenv("APP_BASE_URL", "http://localhost:8501"),
    )
