from datetime import datetime, timezone

from supabase import Client

MAX_HISTORY = 10


def _table(chat_key: str | None) -> str:
    # Privado em conversations; cada chat de grupo em group_chat_history.
    return "group_chat_history" if chat_key else "conversations"


def get_history(db: Client, user_id: str, chat_key: str | None = None) -> list[dict]:
    query = db.table(_table(chat_key)).select("messages").eq("user_id", user_id)
    if chat_key:
        query = query.eq("chat_key", chat_key)
    result = query.maybe_single().execute()
    if not result or not result.data:
        return []
    return result.data.get("messages", [])


def save_history(db: Client, user_id: str, messages: list[dict], chat_key: str | None = None) -> None:
    row = {
        "user_id": user_id,
        "messages": messages[-MAX_HISTORY:],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if chat_key:
        row["chat_key"] = chat_key
    db.table(_table(chat_key)).upsert(
        row, on_conflict="user_id,chat_key" if chat_key else "user_id"
    ).execute()
