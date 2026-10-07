import os

os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-anon-key")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-key")
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-secret-test-secret-test-secret-123")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123456:TEST")

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_user():
    return {"id": "user-uuid-123", "email": "test@example.com"}


@pytest.fixture
def valid_token():
    import jwt
    from app.config import settings
    payload = {
        "sub": "user-uuid-123",
        "email": "test@example.com",
        "aud": "authenticated",
        "role": "authenticated",
    }
    return jwt.encode(payload, settings.supabase_jwt_secret, algorithm="HS256")
