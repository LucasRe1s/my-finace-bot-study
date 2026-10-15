import pytest
from unittest.mock import MagicMock
from agent.history import get_history, save_history


def test_get_history_empty():
    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = None
    result = get_history(mock_db, "user-123")
    assert result == []


def test_get_history_existing():
    mock_db = MagicMock()
    messages = [
        {"role": "user", "content": "Gastei 50 reais"},
        {"role": "assistant", "content": "Confirmo..."},
    ]
    mock_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
        "messages": messages
    }
    result = get_history(mock_db, "user-123")
    assert len(result) == 2
    assert result[0]["role"] == "user"


def test_save_history_trims_to_10():
    mock_db = MagicMock()
    mock_db.table.return_value.upsert.return_value.execute.return_value.data = [{}]

    messages = [{"role": "user", "content": f"msg {i}"} for i in range(15)]
    save_history(mock_db, "user-123", messages)

    call_args = mock_db.table.return_value.upsert.call_args[0][0]
    assert len(call_args["messages"]) == 10
    assert call_args["messages"][0]["content"] == "msg 5"


def test_group_history_is_separate_per_chat():
    from tests.fakes import FakeSupabase

    db = FakeSupabase()
    save_history(db, "u1", [{"role": "user", "content": "privado"}])
    save_history(db, "u1", [{"role": "user", "content": "grupo A"}], chat_key="telegram:-1")
    save_history(db, "u1", [{"role": "user", "content": "grupo A de novo"}], chat_key="telegram:-1")
    save_history(db, "u1", [{"role": "user", "content": "grupo B"}], chat_key="telegram:-2")

    assert get_history(db, "u1")[0]["content"] == "privado"
    assert get_history(db, "u1", "telegram:-1")[0]["content"] == "grupo A de novo"
    assert get_history(db, "u1", "telegram:-2")[0]["content"] == "grupo B"
    assert len(db.tables["group_chat_history"]) == 2
