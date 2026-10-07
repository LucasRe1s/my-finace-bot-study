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
