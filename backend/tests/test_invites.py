from datetime import datetime, timedelta, timezone

import pytest

from app.services.invites import AlreadyInGroup, InviteNotFound, accept_invite, create_invite
from app.services.membership import group_name, names_by_id
from tests.fakes import FakeSupabase

FUTURE = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
PAST = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()


@pytest.fixture
def db():
    fake = FakeSupabase()
    fake.tables["groups"] = [{"id": "g1", "name": "Família Silva"}]
    fake.tables["invites"] = [{"id": "i1", "group_id": "g1", "token": "tok", "accepted_at": None, "expires_at": FUTURE}]
    return fake


def test_accept_adds_member_and_marks_invite(db):
    assert accept_invite(db, "tok", "u1") == "g1"
    assert db.tables["group_members"] == [{"id": db.tables["group_members"][0]["id"], "group_id": "g1", "user_id": "u1", "role": "member"}]
    assert db.tables["invites"][0]["accepted_at"] is not None


def test_accept_is_single_use(db):
    accept_invite(db, "tok", "u1")
    with pytest.raises(InviteNotFound):
        accept_invite(db, "tok", "u2")


def test_accept_rejects_expired(db):
    db.tables["invites"][0]["expires_at"] = PAST
    with pytest.raises(InviteNotFound):
        accept_invite(db, "tok", "u1")


def test_accept_rejects_user_already_in_group(db):
    db.tables["group_members"] = [{"id": "m", "group_id": "outro", "user_id": "u1", "role": "owner"}]
    with pytest.raises(AlreadyInGroup):
        accept_invite(db, "tok", "u1")
    assert db.tables["invites"][0]["accepted_at"] is None


def test_create_invite_without_email(db):
    invite = create_invite(db, "g1", "u1")
    assert invite["group_id"] == "g1" and invite["invited_by"] == "u1" and invite["email"] is None


def test_names_by_id_ignores_missing_and_none():
    db = FakeSupabase()
    db.tables["users"] = [{"id": "u1", "name": "Ana"}, {"id": "u2", "name": None}]
    assert names_by_id(db, ["u1", "u2", None, "u3"]) == {"u1": "Ana", "u2": ""}
    assert names_by_id(db, []) == {}


def test_group_name_fallback():
    db = FakeSupabase()
    assert group_name(db, "nao-existe") == "grupo financeiro"
