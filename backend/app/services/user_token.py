from datetime import datetime, timedelta, timezone

import jwt

from ..config import settings


def generate_user_token(user_id: str) -> str:
    """JWT (HS256, secret legado do Supabase) para o bot agir em nome do
    usuario na propria API, sob RLS. Vale 24h."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "aud": "authenticated",
        "role": "authenticated",
        "iat": now,
        "exp": now + timedelta(hours=24),
    }
    return jwt.encode(payload, settings.supabase_jwt_secret, algorithm="HS256")
