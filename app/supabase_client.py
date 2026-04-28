"""Supabase client helper.

Returns a configured ``supabase.Client`` when ``SUPABASE_URL`` and
``SUPABASE_KEY`` are present in the environment (production on Render),
or ``None`` when they are absent (local development falls back to the
SQLite database configured via ``LIBRE_LIBROS_DATABASE_URL``).
"""
from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()


@lru_cache
def get_supabase_client() -> Client | None:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        return None
    return create_client(url, key)


def is_supabase_enabled() -> bool:
    return get_supabase_client() is not None
