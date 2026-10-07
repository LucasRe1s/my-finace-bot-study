"""Vinculo entre um chat de grupo (Telegram, futuramente WhatsApp) e um grupo
financeiro. `db` e o client de servico."""
from supabase import Client


class NotGroupOwner(Exception):
    """Quem pediu nao e dono do grupo financeiro."""


class ChatAlreadyBound(Exception):
    """O chat ja esta ligado a um grupo financeiro."""


class GroupAlreadyBound(Exception):
    """O grupo financeiro ja esta ligado a outro chat."""


class ChatNotBound(Exception):
    """O chat nao esta ligado a nenhum grupo financeiro."""


def find_binding(db: Client, channel: str, chat_id: str) -> dict | None:
    result = (
        db.table("chat_bindings")
        .select("*")
        .eq("channel", channel)
        .eq("chat_id", chat_id)
        .maybe_single()
        .execute()
    )
    return result.data if result else None


def _owned_group(db: Client, user_id: str) -> dict | None:
    result = db.table("groups").select("*").eq("owner_id", user_id).limit(1).execute()
    return result.data[0] if result.data else None


def bind_chat(db: Client, channel: str, chat_id: str, user_id: str) -> dict:
    group = _owned_group(db, user_id)
    if group is None:
        raise NotGroupOwner()
    if find_binding(db, channel, chat_id) is not None:
        raise ChatAlreadyBound()
    if db.table("chat_bindings").select("id").eq("group_id", group["id"]).limit(1).execute().data:
        raise GroupAlreadyBound()
    db.table("chat_bindings").insert(
        {"channel": channel, "chat_id": chat_id, "group_id": group["id"], "created_by": user_id}
    ).execute()
    return group


def unbind_chat(db: Client, channel: str, chat_id: str, user_id: str) -> None:
    binding = find_binding(db, channel, chat_id)
    if binding is None:
        raise ChatNotBound()
    owned = _owned_group(db, user_id)
    if owned is None or owned["id"] != binding["group_id"]:
        raise NotGroupOwner()
    db.table("chat_bindings").delete().eq("id", binding["id"]).execute()


def move_chat(db: Client, channel: str, old_chat_id: str, new_chat_id: str) -> None:
    db.table("chat_bindings").update({"chat_id": new_chat_id}).eq("channel", channel).eq("chat_id", old_chat_id).execute()
