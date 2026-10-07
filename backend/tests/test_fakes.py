import pytest

from tests.fakes import FakeSupabase, UniqueViolation


def test_insert_select_update_delete():
    db = FakeSupabase()
    created = db.table("users").insert({"name": "Ana"}).execute().data[0]
    assert db.table("users").select("*").eq("id", created["id"]).maybe_single().execute().data["name"] == "Ana"

    db.table("users").update({"name": "Ana Maria"}).eq("id", created["id"]).execute()
    assert db.tables["users"][0]["name"] == "Ana Maria"

    db.table("users").delete().eq("id", created["id"]).execute()
    assert db.table("users").select("*").eq("id", created["id"]).maybe_single().execute() is None


def test_unique_constraint():
    db = FakeSupabase(unique={"user_identities": [("channel", "external_id")]})
    db.table("user_identities").insert({"channel": "telegram", "external_id": "1", "user_id": "a"}).execute()
    with pytest.raises(UniqueViolation):
        db.table("user_identities").insert({"channel": "telegram", "external_id": "1", "user_id": "b"}).execute()


def test_is_null_and_gte_filters():
    db = FakeSupabase()
    db.tables["codes"] = [
        {"code": "A", "used_at": None, "expires_at": "2030-01-01"},
        {"code": "B", "used_at": "x", "expires_at": "2030-01-01"},
        {"code": "C", "used_at": None, "expires_at": "2020-01-01"},
    ]
    rows = db.table("codes").select("*").is_("used_at", "null").gte("expires_at", "2026-01-01").execute().data
    assert [r["code"] for r in rows] == ["A"]
