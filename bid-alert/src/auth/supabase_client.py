"""Supabase client helpers."""

from __future__ import annotations

from supabase import Client, create_client

from src.config import get_settings


def get_supabase_client(*, service_role: bool = False, access_token: str | None = None) -> Client:
    settings = get_settings()
    if not settings.supabase_url:
        raise RuntimeError("SUPABASE_URL is not configured.")

    key = settings.supabase_service_role_key if service_role else settings.supabase_anon_key
    if not key:
        name = "SUPABASE_SERVICE_ROLE_KEY" if service_role else "SUPABASE_ANON_KEY"
        raise RuntimeError(f"{name} is not configured.")

    client = create_client(settings.supabase_url, key)
    if access_token and not service_role:
        client.postgrest.auth(access_token)
    return client
