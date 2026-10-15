"""Identidades por canal (user_identities). `db` e sempre o client de servico:
quem chama (bot/adaptadores) ainda nao tem sessao de usuario."""
import logging
from datetime import datetime, timezone

from supabase import Client

from .membership import find_user_group

logger = logging.getLogger("api")


class InvalidLinkCode(Exception):
    """Codigo inexistente, expirado ou ja usado."""


class LinkConflict(Exception):
    """As duas contas ja participam de grupos financeiros diferentes."""


def find_user_by_identity(db: Client, channel: str, external_id: str) -> dict | None:
    identity = (
        db.table("user_identities")
        .select("user_id")
        .eq("channel", channel)
        .eq("external_id", external_id)
        .maybe_single()
        .execute()
    )
    if identity and identity.data:
        user = db.table("users").select("*").eq("id", identity.data["user_id"]).maybe_single().execute()
        return user.data if user else None
    if channel == "telegram":
        return _adopt_legacy_telegram_user(db, external_id)
    return None


def _adopt_legacy_telegram_user(db: Client, external_id: str) -> dict | None:
    """Usuarios criados antes da migration 012 (ou entre ela e o deploy) so tem
    users.telegram_id. Cria a identidade na primeira mensagem. Sai junto com a
    coluna telegram_id."""
    legacy = db.table("users").select("*").eq("telegram_id", int(external_id)).maybe_single().execute()
    if not legacy or not legacy.data:
        return None
    db.table("user_identities").insert(
        {"user_id": legacy.data["id"], "channel": "telegram", "external_id": external_id}
    ).execute()
    return legacy.data


def get_or_create_user(db: Client, channel: str, external_id: str, display_name: str) -> tuple[dict, bool]:
    user = find_user_by_identity(db, channel, external_id)
    if user:
        # Conta web nasce com o email como nome; o nome do canal e melhor.
        current = user.get("name") or ""
        if display_name and (not current or "@" in current):
            db.table("users").update({"name": display_name}).eq("id", user["id"]).execute()
            user = {**user, "name": display_name}
        return user, False

    created = db.table("users").insert({"name": display_name}).execute().data[0]
    try:
        db.table("user_identities").insert(
            {"user_id": created["id"], "channel": channel, "external_id": external_id}
        ).execute()
    except Exception:
        # Duas primeiras mensagens simultaneas: a outra venceu a constraint
        # UNIQUE(channel, external_id). Descarta este usuario e usa o dela.
        db.table("users").delete().eq("id", created["id"]).execute()
        user = find_user_by_identity(db, channel, external_id)
        if user is None:
            raise
        return user, False
    logger.info("Novo usuario %s:%s (%s)", channel, external_id, display_name)
    return created, True


def link_identity(db: Client, code: str, channel: str, external_id: str) -> None:
    """Liga a identidade do canal a conta web dona do codigo. Se a identidade
    ja pertencia a outro usuario (conta so-bot), funde esse usuario na conta web."""
    now = datetime.now(timezone.utc).isoformat()
    valid = (
        db.table("telegram_link_codes")
        .select("user_id")
        .eq("code", code)
        .is_("used_at", "null")
        .gte("expires_at", now)
        .execute()
    )
    if not valid.data:
        raise InvalidLinkCode()
    target_id = valid.data[0]["user_id"]

    current = find_user_by_identity(db, channel, external_id)
    old_id = current["id"] if current and current["id"] != target_id else None
    if old_id:
        old_group, target_group = find_user_group(db, old_id), find_user_group(db, target_id)
        if old_group and target_group and old_group != target_group:
            raise LinkConflict()

    # Reivindica o codigo antes de mexer nos dados: so um consumo vence.
    claimed = (
        db.table("telegram_link_codes")
        .update({"used_at": now})
        .eq("code", code)
        .is_("used_at", "null")
        .execute()
    )
    if not claimed.data:
        raise InvalidLinkCode()

    if current is None:
        db.table("user_identities").insert(
            {"user_id": target_id, "channel": channel, "external_id": external_id}
        ).execute()
    elif old_id:
        _merge_user(db, old_id=old_id, target_id=target_id, target_group=target_group)


def _merge_user(db: Client, old_id: str, target_id: str, target_group: str | None) -> None:
    # Transfere a posse antes de apagar o usuario antigo: groups.owner_id tem
    # ON DELETE CASCADE e apagaria o grupo inteiro com as transacoes.
    db.table("groups").update({"owner_id": target_id}).eq("owner_id", old_id).execute()
    if target_group is None:
        db.table("group_members").update({"user_id": target_id}).eq("user_id", old_id).execute()
    else:
        # Mesmo grupo (o conflito ja foi barrado): so remove a linha duplicada.
        db.table("group_members").delete().eq("user_id", old_id).execute()
    db.table("transactions").update({"user_id": target_id}).eq("user_id", old_id).execute()
    # conversations.user_id e UNIQUE; o historico do bot e efemero, descarta.
    db.table("conversations").delete().eq("user_id", old_id).execute()
    db.table("user_identities").update({"user_id": target_id}).eq("user_id", old_id).execute()
    db.table("users").delete().eq("id", old_id).execute()
