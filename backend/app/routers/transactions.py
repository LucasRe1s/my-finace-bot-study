import calendar
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from supabase import Client

from ..auth import get_current_user
from ..database import get_service_supabase, get_supabase
from ..models.transaction import Transaction, TransactionCreate
from ..services.membership import find_user_group as _find_user_group, names_by_id

router = APIRouter(prefix="/transactions", tags=["transactions"])


def _ensure_user_profile(db: Client, user: dict) -> None:
    """Cria/atualiza a linha em public.users para o usuário autenticado via Supabase Auth.

    A migration 002 removeu o FK de public.users para auth.users (para o bot
    criar usuarios com UUID proprio), entao usuarios web nunca ganham essa linha
    automaticamente -- e groups/group_members referenciam public.users(id) via
    FK. Sem isso, criar grupo ou aceitar convite falha com violacao de FK.
    Nao sobrescreve o nome de quem ja existe."""
    db.table("users").upsert(
        {"id": user["id"], "name": user.get("email", "")},
        on_conflict="id",
        ignore_duplicates=True,
    ).execute()


def _get_user_group(db: Client, user_id: str) -> str:
    group_id = _find_user_group(db, user_id)
    if group_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não pertence a nenhum grupo. Crie um grupo ou aceite um convite.",
        )
    return group_id


@router.post("/", response_model=Transaction, status_code=status.HTTP_201_CREATED)
async def create_transaction(
    data: TransactionCreate,
    user: dict = Depends(get_current_user),
):
    db = get_supabase(user["token"])
    group_id = _get_user_group(db, user["id"])
    result = (
        db.table("transactions")
        .insert({
            "user_id": user["id"],
            "group_id": group_id,
            "amount": data.amount,
            "type": data.type.value,
            "category": data.category,
            "description": data.description,
            "date": str(data.date),
        })
        .execute()
    )
    return result.data[0]


@router.get("/", response_model=list[Transaction])
async def list_transactions(
    month: Optional[str] = Query(None, description="Formato YYYY-MM, ex: 2026-06"),
    category: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    user: dict = Depends(get_current_user),
):
    db = get_supabase(user["token"])
    group_id = _get_user_group(db, user["id"])
    query = db.table("transactions").select("*").eq("group_id", group_id)

    if month:
        year, mon = month.split("-")
        first_day = f"{year}-{mon}-01"
        last_day = f"{year}-{mon}-{calendar.monthrange(int(year), int(mon))[1]}"
        query = query.gte("date", first_day).lte("date", last_day)

    if category:
        query = query.eq("category", category)

    if type:
        query = query.eq("type", type)

    rows = query.order("date", desc=True).execute().data or []
    names = names_by_id(get_service_supabase(), [t.get("user_id") for t in rows])
    return [{**t, "user_name": names.get(t.get("user_id"))} for t in rows]


UNDO_WINDOW_MINUTES = 10


@router.post("/undo-last", response_model=Transaction)
async def undo_last_transaction(user: dict = Depends(get_current_user)):
    """Apaga a ultima transacao do proprio usuario criada nos ultimos 10 min."""
    db = get_supabase(user["token"])
    since = (datetime.now(timezone.utc) - timedelta(minutes=UNDO_WINDOW_MINUTES)).isoformat()
    result = (
        db.table("transactions")
        .select("*")
        .eq("user_id", user["id"])
        .gte("created_at", since)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Nenhuma transação sua nos últimos {UNDO_WINDOW_MINUTES} minutos.",
        )
    tx = result.data[0]
    db.table("transactions").delete().eq("id", tx["id"]).execute()
    return tx
