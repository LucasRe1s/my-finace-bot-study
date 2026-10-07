from supabase import Client


def find_user_group(db: Client, user_id: str) -> str | None:
    result = db.table("group_members").select("group_id").eq("user_id", user_id).limit(1).execute()
    return result.data[0]["group_id"] if result.data else None


def names_by_id(db: Client, user_ids: list[str | None]) -> dict[str, str]:
    """Nome de cada usuario. Chamar com o client de servico, so com ids que ja
    vieram de uma consulta feita sob RLS (membros/transacoes do grupo)."""
    ids = sorted({uid for uid in user_ids if uid})
    if not ids:
        return {}
    result = db.table("users").select("id, name").in_("id", ids).execute()
    return {row["id"]: row.get("name") or "" for row in result.data or []}


def group_name(db: Client, group_id: str) -> str:
    result = db.table("groups").select("name").eq("id", group_id).maybe_single().execute()
    return result.data["name"] if result and result.data else "grupo financeiro"
