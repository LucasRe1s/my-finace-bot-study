import random
import string
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
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


class TelegramLinkRequest(BaseModel):
    code: str
    telegram_id: int


@router.post("/telegram-link")
async def consume_telegram_link_code(data: TelegramLinkRequest):
    """Chamado pelo bot (sem sessao de usuario) quando alguem manda /start
    <codigo>. Associa o telegram_id a conta web dona do codigo, migrando
    grupo/transacoes/historico caso esse telegram_id ja tivesse uma identidade
    de bot separada."""
    db = get_supabase()
    now = datetime.now(timezone.utc).isoformat()

    result = (
        db.table("telegram_link_codes")
        .select("*")
        .eq("code", data.code)
        .is_("used_at", "null")
        .gte("expires_at", now)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Código inválido ou expirado.")

    target_user_id = result.data[0]["user_id"]

    existing = (
        db.table("users")
        .select("id")
        .eq("telegram_id", data.telegram_id)
        .maybe_single()
        .execute()
    )
    if existing and existing.data and existing.data["id"] != target_user_id:
        old_user_id = existing.data["id"]
        for table in ("group_members", "transactions", "conversations"):
            db.table(table).update({"user_id": target_user_id}).eq("user_id", old_user_id).execute()
        db.table("users").delete().eq("id", old_user_id).execute()

    db.table("users").update({"telegram_id": data.telegram_id}).eq("id", target_user_id).execute()
    db.table("telegram_link_codes").update({"used_at": now}).eq("code", data.code).execute()

    return {"message": "Telegram vinculado com sucesso."}
