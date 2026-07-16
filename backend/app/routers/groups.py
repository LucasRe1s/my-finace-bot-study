from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from ..auth import get_current_user
from ..database import get_supabase
from ..models.group import InviteCreate
from ..routers.transactions import _ensure_user_profile, _get_user_group

router = APIRouter(prefix="/groups", tags=["groups"])


class GroupCreate(BaseModel):
    name: str


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_group(
    data: GroupCreate,
    user: dict = Depends(get_current_user),
):
    db = get_supabase(user["token"])
    _ensure_user_profile(db, user)
    result = db.table("groups").insert({"name": data.name, "owner_id": user["id"]}).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Erro ao criar grupo. Tente novamente.")
    group = result.data[0]
    db.table("group_members").insert({"group_id": group["id"], "user_id": user["id"], "role": "owner"}).execute()
    return group


@router.post("/invite", status_code=status.HTTP_201_CREATED)
async def invite_member(
    data: InviteCreate,
    user: dict = Depends(get_current_user),
):
    db = get_supabase(user["token"])
    group_id = _get_user_group(db, user["id"])
    result = db.table("invites").insert({
        "group_id": group_id,
        "invited_by": user["id"],
        "email": data.email,
    }).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Erro ao criar convite. Tente novamente.")
    return result.data[0]


@router.get("/invite/{token}")
async def get_invite_preview(token: str):
    """Endpoint publico: quem recebeu o link de convite ainda nao tem conta,
    entao roda sem autenticacao (role anon) so pra mostrar pra qual grupo/email
    o convite e antes do signup/login."""
    db = get_supabase()
    invite = (
        db.table("invites")
        .select("email, group_id")
        .eq("token", token)
        .is_("accepted_at", "null")
        .maybe_single()
        .execute()
    )
    if not invite or not invite.data:
        raise HTTPException(status_code=404, detail="Convite inválido ou já utilizado")

    group = db.table("groups").select("name").eq("id", invite.data["group_id"]).maybe_single().execute()
    group_name = group.data["name"] if group and group.data else "grupo financeiro"
    return {"email": invite.data["email"], "group_name": group_name}


@router.get("/members")
async def list_members(
    user: dict = Depends(get_current_user),
):
    db = get_supabase(user["token"])
    try:
        group_id = _get_user_group(db, user["id"])
    except HTTPException:
        return []
    result = db.table("group_members").select("user_id, role").eq("group_id", group_id).execute()
    return result.data or []


@router.post("/accept")
async def accept_invite(
    token: str = Query(...),
    user: dict = Depends(get_current_user),
):
    db = get_supabase(user["token"])
    invite = db.table("invites").select("*").eq("token", token).is_("accepted_at", "null").single().execute()
    if not invite.data:
        raise HTTPException(status_code=404, detail="Convite inválido ou já utilizado")

    _ensure_user_profile(db, user)
    db.table("group_members").insert({
        "group_id": invite.data["group_id"],
        "user_id": user["id"],
        "role": "member",
    }).execute()
    db.table("invites").update({"accepted_at": datetime.now(timezone.utc).isoformat()}).eq("id", invite.data["id"]).execute()
    return {"message": "Convite aceito com sucesso"}
