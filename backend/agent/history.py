from datetime import datetime, timezone

from supabase import Client

MAX_HISTORY = 10


def get_history(db: Client, user_id: str) -> list[dict]:
    result = (
        db.table("conversations")
        .select("messages")
        .eq("user_id", user_id)
        .single()
        .execute()
    )
    if not result.data:
        return []
    return result.data.get("messages", [])


def save_history(db: Client, user_id: str, messages: list[dict]) -> None:
    trimmed = messages[-MAX_HISTORY:]
    db.table("conversations").upsert(
        {
            "user_id": user_id,
            "messages": trimmed,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
        on_conflict="user_id",
    ).execute()
