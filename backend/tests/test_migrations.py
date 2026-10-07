import re
from pathlib import Path

MIGRATIONS = Path(__file__).resolve().parent.parent / "supabase" / "migrations"
REVOKE_FILE = "011_revoke_anon_access.sql"


def _sql(name: str) -> str:
    return (MIGRATIONS / name).read_text(encoding="utf-8")


def _anon_policies_before_011() -> set[str]:
    policies = set()
    for path in sorted(MIGRATIONS.glob("*.sql")):
        if path.name >= REVOKE_FILE:
            continue
        for name, body in re.findall(r'CREATE POLICY "(\w+)"(.*?);', path.read_text(encoding="utf-8"), re.S):
            if re.search(r"\bTO\s+anon\b", body):
                policies.add(name)
    return policies


def _dropped_in_011() -> set[str]:
    return set(re.findall(r'DROP POLICY IF EXISTS "(\w+)"', _sql(REVOKE_FILE)))


def test_every_anon_policy_is_dropped():
    anon = _anon_policies_before_011()
    assert anon, "esperava encontrar policies TO anon nas migrations antigas"
    assert anon <= _dropped_in_011()


def test_sec02_policies_are_dropped():
    assert {"invites_accept_update", "group_members_insert_self"} <= _dropped_in_011()


def test_anon_grants_are_revoked_on_app_tables():
    sql = _sql(REVOKE_FILE)
    for table in (
        "users", "conversations", "groups", "group_members", "transactions",
        "category_limits", "invites", "telegram_link_codes",
    ):
        assert re.search(rf"REVOKE ALL ON public\.{table} FROM anon;", sql), table


def test_user_identities_has_rls_and_no_anon():
    sql = _sql("012_user_identities.sql")
    assert "CREATE TABLE public.user_identities" in sql
    assert "UNIQUE (channel, external_id)" in sql
    assert "ALTER TABLE public.user_identities ENABLE ROW LEVEL SECURITY;" in sql
    assert "REVOKE ALL ON public.user_identities FROM anon;" in sql
    assert not re.search(r"\bTO\s+anon\b", sql)


def test_user_identities_backfills_telegram_ids():
    sql = _sql("012_user_identities.sql")
    assert re.search(r"INSERT INTO public\.user_identities.*FROM public\.users.*telegram_id IS NOT NULL", sql, re.S)


def test_invites_email_optional_and_expiring():
    sql = _sql("013_invites_expiry_optional_email.sql")
    assert "ALTER COLUMN email DROP NOT NULL" in sql
    assert re.search(r"ADD COLUMN expires_at TIMESTAMPTZ NOT NULL DEFAULT \(NOW\(\) \+ INTERVAL '7 days'\)", sql)


def test_chat_bindings_and_group_history():
    sql = _sql("014_chat_bindings.sql")
    assert "CREATE TABLE public.chat_bindings" in sql
    assert "UNIQUE (channel, chat_id)" in sql
    assert "UNIQUE (group_id)" in sql
    assert "CREATE TABLE public.group_chat_history" in sql
    assert "UNIQUE (user_id, chat_key)" in sql
    for table in ("chat_bindings", "group_chat_history"):
        assert f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY;" in sql
        assert f"REVOKE ALL ON public.{table} FROM anon;" in sql
    assert not re.search(r"\bTO\s+anon\b", sql)
