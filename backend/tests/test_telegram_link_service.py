from unittest.mock import MagicMock

import pytest

from app.services.telegram_link import InvalidLinkCode, link_telegram_account


def _db_with_code(existing_user=None):
    db = MagicMock()
    db.table.return_value.select.return_value.eq.return_value.is_.return_value.gte.return_value.execute.return_value.data = [
        {"code": "ABC12345", "user_id": "web-user-uuid", "used_at": None}
    ]
    db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = existing_user
    return db


def test_link_sets_telegram_id_and_marks_code_used():
    db = _db_with_code()
    link_telegram_account(db, "ABC12345", 999888777)

    update_payloads = [c.args[0] for c in db.table.return_value.update.call_args_list]
    assert {"telegram_id": 999888777} in update_payloads
    assert any("used_at" in p for p in update_payloads)
    db.table.return_value.delete.assert_not_called()


def test_link_rejects_invalid_or_expired_code():
    db = MagicMock()
    db.table.return_value.select.return_value.eq.return_value.is_.return_value.gte.return_value.execute.return_value.data = []
    with pytest.raises(InvalidLinkCode):
        link_telegram_account(db, "BADCODE1", 999888777)


def test_link_merges_existing_bot_only_user():
    db = _db_with_code(existing_user={"id": "bot-only-user-uuid"})
    link_telegram_account(db, "ABC12345", 999888777)

    update_payloads = [c.args[0] for c in db.table.return_value.update.call_args_list]
    assert {"user_id": "web-user-uuid"} in update_payloads
    db.table.return_value.delete.assert_called_once()
