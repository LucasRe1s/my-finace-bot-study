from datetime import datetime, timedelta, timezone

import pytest

from app.services.identities import (
    InvalidLinkCode,
    LinkConflict,
    find_user_by_identity,
    get_or_create_user,
    link_identity,
)
from tests.fakes import FakeSupabase

FUTURE = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
PAST = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()


@pytest.fixture
def db():
    return FakeSupabase(unique={
        "user_identities": [("channel", "external_id")],
        "conversations": [("user_id",)],
    })


def _identity(db, user_id, external_id="555", channel="telegram"):
    db.tables.setdefault("user_identities", []).append(
        {"id": f"ident-{user_id}", "user_id": user_id, "channel": channel, "external_id": external_id}
    )


def _code(db, user_id="web-user", code="ABC12345", expires_at=FUTURE):
    db.tables.setdefault("telegram_link_codes", []).append(
        {"code": code, "user_id": user_id, "expires_at": expires_at, "used_at": None}
    )


def test_creates_user_and_identity_on_first_contact(db):
    user, is_new = get_or_create_user(db, "telegram", "555", "Ana")

    assert is_new
    assert user["name"] == "Ana"
    assert db.tables["user_identities"][0] == {
        "id": db.tables["user_identities"][0]["id"],
        "user_id": user["id"], "channel": "telegram", "external_id": "555",
    }


def test_finds_existing_user_by_identity(db):
    db.tables["users"] = [{"id": "u1", "name": "Ana"}]
    _identity(db, "u1")

    user, is_new = get_or_create_user(db, "telegram", "555", "Outro nome")

    assert not is_new
    assert user["id"] == "u1"
    assert len(db.tables["users"]) == 1


def test_same_external_id_on_other_channel_is_another_user(db):
    db.tables["users"] = [{"id": "u1", "name": "Ana"}]
    _identity(db, "u1", channel="telegram")

    user, is_new = get_or_create_user(db, "whatsapp", "555", "Ana")

    assert is_new
    assert user["id"] != "u1"


def test_adopts_legacy_telegram_user_without_identity(db):
    db.tables["users"] = [{"id": "legacy", "name": "Ana", "telegram_id": 555}]

    user = find_user_by_identity(db, "telegram", "555")

    assert user["id"] == "legacy"
    assert db.tables["user_identities"][0]["user_id"] == "legacy"


def test_link_adds_identity_to_web_account(db):
    db.tables["users"] = [{"id": "web-user", "name": "ana@x.com"}]
    _code(db)

    link_identity(db, "ABC12345", "telegram", "555")

    assert find_user_by_identity(db, "telegram", "555")["id"] == "web-user"
    assert db.tables["telegram_link_codes"][0]["used_at"] is not None


def test_link_rejects_expired_code(db):
    _code(db, expires_at=PAST)
    with pytest.raises(InvalidLinkCode):
        link_identity(db, "ABC12345", "telegram", "555")


def test_link_code_works_only_once(db):
    db.tables["users"] = [{"id": "web-user", "name": "ana@x.com"}]
    _code(db)
    link_identity(db, "ABC12345", "telegram", "555")
    with pytest.raises(InvalidLinkCode):
        link_identity(db, "ABC12345", "telegram", "777")


def test_link_merges_bot_only_user_keeping_its_group(db):
    db.tables["users"] = [{"id": "web-user", "name": "ana@x.com"}, {"id": "bot-user", "name": "Ana"}]
    _identity(db, "bot-user")
    db.tables["groups"] = [{"id": "g1", "name": "Casa", "owner_id": "bot-user"}]
    db.tables["group_members"] = [{"id": "m1", "group_id": "g1", "user_id": "bot-user", "role": "owner"}]
    db.tables["transactions"] = [{"id": "t1", "group_id": "g1", "user_id": "bot-user"}]
    db.tables["conversations"] = [
        {"id": "c1", "user_id": "bot-user", "messages": []},
        {"id": "c2", "user_id": "web-user", "messages": []},
    ]
    _code(db)

    link_identity(db, "ABC12345", "telegram", "555")

    assert db.tables["groups"][0]["owner_id"] == "web-user"
    assert db.tables["group_members"] == [{"id": "m1", "group_id": "g1", "user_id": "web-user", "role": "owner"}]
    assert db.tables["transactions"][0]["user_id"] == "web-user"
    assert [c["user_id"] for c in db.tables["conversations"]] == ["web-user"]
    assert [u["id"] for u in db.tables["users"]] == ["web-user"]
    assert find_user_by_identity(db, "telegram", "555")["id"] == "web-user"


def test_link_refuses_when_both_accounts_have_different_groups(db):
    db.tables["users"] = [{"id": "web-user"}, {"id": "bot-user"}]
    _identity(db, "bot-user")
    db.tables["group_members"] = [
        {"id": "m1", "group_id": "g-bot", "user_id": "bot-user", "role": "owner"},
        {"id": "m2", "group_id": "g-web", "user_id": "web-user", "role": "owner"},
    ]
    _code(db)

    with pytest.raises(LinkConflict):
        link_identity(db, "ABC12345", "telegram", "555")

    assert db.tables["telegram_link_codes"][0]["used_at"] is None
    assert {u["id"] for u in db.tables["users"]} == {"web-user", "bot-user"}


def test_link_when_both_in_same_group_drops_duplicate_membership(db):
    db.tables["users"] = [{"id": "web-user"}, {"id": "bot-user"}]
    _identity(db, "bot-user")
    db.tables["groups"] = [{"id": "g1", "owner_id": "web-user"}]
    db.tables["group_members"] = [
        {"id": "m1", "group_id": "g1", "user_id": "web-user", "role": "owner"},
        {"id": "m2", "group_id": "g1", "user_id": "bot-user", "role": "member"},
    ]
    _code(db)

    link_identity(db, "ABC12345", "telegram", "555")

    assert db.tables["group_members"] == [{"id": "m1", "group_id": "g1", "user_id": "web-user", "role": "owner"}]


def test_link_to_same_account_is_noop(db):
    db.tables["users"] = [{"id": "web-user"}]
    _identity(db, "web-user")
    _code(db)

    link_identity(db, "ABC12345", "telegram", "555")

    assert len(db.tables["user_identities"]) == 1


def test_bot_name_replaces_email_placeholder(db):
    db.tables["users"] = [{"id": "u1", "name": "ana@x.com"}]
    _identity(db, "u1")

    user, _ = get_or_create_user(db, "telegram", "555", "Ana")

    assert user["name"] == "Ana"
    assert db.tables["users"][0]["name"] == "Ana"


def test_bot_name_does_not_override_real_name(db):
    db.tables["users"] = [{"id": "u1", "name": "Ana Paula"}]
    _identity(db, "u1")

    user, _ = get_or_create_user(db, "telegram", "555", "Aninha")

    assert user["name"] == "Ana Paula"
