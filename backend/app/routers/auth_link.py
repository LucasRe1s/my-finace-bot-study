import random
import string
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel

from ..auth import get_current_user
from ..database import get_supabase
from ..routers.transactions import _ensure_user_profile

router = APIRouter(prefix="/auth", tags=["auth"])

_CODE_ALPHABET = string.ascii_uppercase + string.digits
_CODE_LENGTH = 8
_CODE_TTL_MINUTES = 10


def _generate_code() -> str:
    return "".join(random.choices(_CODE_ALPHABET, k=_CODE_LENGTH))


class LinkCodeResponse(BaseModel):
    code: str
    expires_at: str


@router.post("/telegram-link-code", response_model=LinkCodeResponse, status_code=status.HTTP_201_CREATED)
async def create_telegram_link_code(user: dict = Depends(get_current_user)):
    """Gera um codigo de uso unico (valido por 10 min) para o usuario web
    vincular sua conta ao bot do Telegram via `/start <codigo>`."""
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
