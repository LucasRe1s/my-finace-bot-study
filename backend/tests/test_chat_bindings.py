import pytest

from app.services.chat_bindings import (
    ChatAlreadyBound,
    ChatNotBound,
    GroupAlreadyBound,
    NotGroupOwner,
    bind_chat,
    find_binding,
    move_chat,
    unbind_chat,
)
from tests.fakes import FakeSupabase


@pytest.fixture
def db():
    fake = FakeSupabase(unique={"chat_bindings": [("channel", "chat_id"), ("group_id",)]})
    fake.tables["groups"] = [{"id": "g1", "name": "Casa", "owner_id": "ana"}]
    return fake


def test_owner_binds_chat(db):
    group = bind_chat(db, "telegram", "-100", "ana")
    assert group["id"] == "g1"
    assert find_binding(db, "telegram", "-100")["group_id"] == "g1"


def test_non_owner_cannot_bind(db):
    with pytest.raises(NotGroupOwner):
        bind_chat(db, "telegram", "-100", "bia")


def test_chat_cannot_be_bound_twice(db):
    db.tables["groups"].append({"id": "g2", "name": "Outro", "owner_id": "caio"})
    bind_chat(db, "telegram", "-100", "ana")
    with pytest.raises(ChatAlreadyBound):
        bind_chat(db, "telegram", "-100", "caio")


def test_group_has_at_most_one_chat(db):
    bind_chat(db, "telegram", "-100", "ana")
    with pytest.raises(GroupAlreadyBound):
        bind_chat(db, "telegram", "-200", "ana")


def test_unbind_by_owner(db):
    bind_chat(db, "telegram", "-100", "ana")
    unbind_chat(db, "telegram", "-100", "ana")
    assert find_binding(db, "telegram", "-100") is None


def test_unbind_rules(db):
    with pytest.raises(ChatNotBound):
        unbind_chat(db, "telegram", "-100", "ana")
    bind_chat(db, "telegram", "-100", "ana")
    with pytest.raises(NotGroupOwner):
        unbind_chat(db, "telegram", "-100", "bia")


def test_move_chat_after_supergroup_migration(db):
    bind_chat(db, "telegram", "-100", "ana")
    move_chat(db, "telegram", "-100", "-100999")
    assert find_binding(db, "telegram", "-100") is None
    assert find_binding(db, "telegram", "-100999")["group_id"] == "g1"
