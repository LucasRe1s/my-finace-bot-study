from datetime import datetime, timezone

from supabase import Client

from .membership import find_user_group


class InviteNotFound(Exception):
    """Convite inexistente, expirado ou ja usado."""


class AlreadyInGroup(Exception):
    """O usuario ja participa de um grupo financeiro."""


def create_invite(db: Client, group_id: str, invited_by: str, email: str | None = None) -> dict | None:
    result = db.table("invites").insert({"group_id": group_id, "invited_by": invited_by, "email": email}).execute()
    return result.data[0] if result.data else None


def accept_invite(db: Client, token: str, user_id: str) -> str:
    """Coloca o usuario no grupo do convite e devolve o group_id. `db` e o
    client de servico: o usuario nao tem permissao de UPDATE em invites."""
    if find_user_group(db, user_id) is not None:
        raise AlreadyInGroup()

    now = datetime.now(timezone.utc).isoformat()
    # UPDATE condicional: so um aceite vence, mesmo com requisicoes simultaneas.
    claimed = (
        db.table("invites")
        .update({"accepted_at": now})
        .eq("token", token)
        .is_("accepted_at", "null")
        .gte("expires_at", now)
        .execute()
    )
    if not claimed.data:
        raise InviteNotFound()

    group_id = claimed.data[0]["group_id"]
    db.table("group_members").insert({"group_id": group_id, "user_id": user_id, "role": "member"}).execute()
    return group_id
