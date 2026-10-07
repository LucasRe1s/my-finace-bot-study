import random
import string
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ..auth import get_current_user
from ..database import get_supabase
from ..routers.transactions import _ensure_user_profile
from core.rate_limit import SlidingWindowLimiter

router = APIRouter(prefix="/auth", tags=["auth"])

_CODE_ALPHABET = string.ascii_uppercase + string.digits
_CODE_LENGTH = 8
_CODE_TTL_MINUTES = 10

# Cada codigo vale 10 min; 5 por janela sobra para quem errou e evita spam na tabela.
_code_limiter = SlidingWindowLimiter(max_events=5, window_seconds=600)


def _generate_code() -> str:
    return "".join(random.choices(_CODE_ALPHABET, k=_CODE_LENGTH))


class LinkCodeResponse(BaseModel):
    code: str
    expires_at: str


@router.post("/telegram-link-code", response_model=LinkCodeResponse, status_code=status.HTTP_201_CREATED)
async def create_telegram_link_code(user: dict = Depends(get_current_user)):
    """Gera um codigo de uso unico (valido por 10 min) para o usuario web
    vincular sua conta ao bot do Telegram via `/start <codigo>`."""
    if not _code_limiter.allow(user["id"]):
        raise HTTPException(status_code=429, detail="Muitos códigos gerados. Aguarde alguns minutos.")
    db = get_supabase(user["token"])
    _ensure_user_profile(db, user)

    code = _generate_code()
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=_CODE_TTL_MINUTES)).isoformat()
    db.table("telegram_link_codes").insert({
        "code": code,
        "user_id": user["id"],
        "expires_at": expires_at,
    }).execute()
    return {"code": code, "expires_at": expires_at}
