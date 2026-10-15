from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from ..auth import get_current_user
from ..database import get_service_supabase, get_supabase
from ..models.group import InviteCreate
from ..services.invites import AlreadyInGroup, InviteNotFound, accept_invite as accept_invite_service, create_invite
from ..services.membership import group_name, names_by_id
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
    invite = create_invite(db, group_id, user["id"], data.email)
    if invite is None:
        raise HTTPException(status_code=500, detail="Erro ao criar convite. Tente novamente.")
    return invite


@router.get("/invite/{token}")
async def get_invite_preview(token: str):
    """Endpoint publico: quem recebeu o link de convite ainda nao tem conta.
    Roda com o client de servico porque o role anon nao le mais invites/groups
    (migration 011); so devolve email e nome do grupo de um token valido."""
    db = get_service_supabase()
    invite = (
        db.table("invites")
        .select("email, group_id")
        .eq("token", token)
        .is_("accepted_at", "null")
        .gte("expires_at", datetime.now(timezone.utc).isoformat())
        .maybe_single()
        .execute()
    )
    if not invite or not invite.data:
        raise HTTPException(status_code=404, detail="Convite inválido ou já utilizado")
    return {"email": invite.data["email"], "group_name": group_name(db, invite.data["group_id"])}


@router.get("/members")
async def list_members(
    user: dict = Depends(get_current_user),
):
    db = get_supabase(user["token"])
    try:
        group_id = _get_user_group(db, user["id"])
    except HTTPException:
        return []
    rows = db.table("group_members").select("user_id, role").eq("group_id", group_id).execute().data or []
    names = names_by_id(get_service_supabase(), [r["user_id"] for r in rows])
    return [{**r, "name": names.get(r["user_id"], "")} for r in rows]


@router.post("/accept")
async def accept_invite(
    token: str = Query(...),
    user: dict = Depends(get_current_user),
):
    db = get_supabase(user["token"])
    _ensure_user_profile(db, user)
    try:
        accept_invite_service(get_service_supabase(), token, user["id"])
    except AlreadyInGroup:
        raise HTTPException(status_code=409, detail="Você já participa de um grupo financeiro.")
    except InviteNotFound:
        raise HTTPException(status_code=404, detail="Convite inválido ou já utilizado")
    return {"message": "Convite aceito com sucesso"}
