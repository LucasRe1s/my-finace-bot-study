from datetime import datetime, timezone

from supabase import Client


class InvalidLinkCode(Exception):
    """Codigo inexistente, expirado ou ja usado."""


def link_telegram_account(db: Client, code: str, telegram_id: int) -> None:
    """Associa o telegram_id a conta web dona do codigo, migrando grupo,
    transacoes e historico caso esse telegram_id ja tivesse uma identidade de
    bot separada. `db` precisa ser o client de servico: quem chama ainda nao
    tem sessao de usuario."""
    now = datetime.now(timezone.utc).isoformat()

    result = (
        db.table("telegram_link_codes")
        .select("*")
        .eq("code", code)
        .is_("used_at", "null")
        .gte("expires_at", now)
        .execute()
    )
    if not result.data:
        raise InvalidLinkCode()

    target_user_id = result.data[0]["user_id"]

    existing = (
        db.table("users")
        .select("id")
        .eq("telegram_id", telegram_id)
        .maybe_single()
        .execute()
    )
    if existing and existing.data and existing.data["id"] != target_user_id:
        old_user_id = existing.data["id"]
        for table in ("group_members", "transactions", "conversations"):
            db.table(table).update({"user_id": target_user_id}).eq("user_id", old_user_id).execute()
        db.table("users").delete().eq("id", old_user_id).execute()

    db.table("users").update({"telegram_id": telegram_id}).eq("id", target_user_id).execute()
    db.table("telegram_link_codes").update({"used_at": now}).eq("code", code).execute()
