from unittest.mock import patch

import pytest

from app import database
from app.config import settings


@pytest.fixture(autouse=True)
def _clear_cache():
    database.get_service_supabase.cache_clear()
    yield
    database.get_service_supabase.cache_clear()


def test_service_client_uses_service_role_key(monkeypatch):
    monkeypatch.setattr(settings, "supabase_service_role_key", "service-key")
    with patch("app.database.create_client") as create_client:
        database.get_service_supabase()
    create_client.assert_called_once_with(settings.supabase_url, "service-key")


def test_service_client_is_cached(monkeypatch):
    monkeypatch.setattr(settings, "supabase_service_role_key", "service-key")
    with patch("app.database.create_client") as create_client:
        database.get_service_supabase()
        database.get_service_supabase()
    create_client.assert_called_once()


def test_service_client_requires_key(monkeypatch):
    monkeypatch.setattr(settings, "supabase_service_role_key", "")
    with pytest.raises(RuntimeError, match="SUPABASE_SERVICE_ROLE_KEY"):
        database.get_service_supabase()


def test_cors_origin_list_splits_and_strips(monkeypatch):
    monkeypatch.setattr(settings, "cors_origins", "https://a.app, https://b.app ,")
    assert settings.cors_origin_list == ["https://a.app", "https://b.app"]
