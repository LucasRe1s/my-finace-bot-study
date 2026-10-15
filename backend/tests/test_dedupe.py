from unittest.mock import MagicMock, patch

import pytest
from postgrest.exceptions import APIError

from core.dedupe import claim_update


def _db(insert_side_effect=None):
    db = MagicMock()
    execute = db.table.return_value.insert.return_value.execute
    if insert_side_effect:
        execute.side_effect = insert_side_effect
    return db


def test_first_time_claims_and_inserts_key():
    db = _db()
    with patch("core.dedupe.get_service_supabase", return_value=db):
        assert claim_update("telegram:42") is True
    db.table.assert_called_with("processed_updates")
    db.table.return_value.insert.assert_called_once_with({"key": "telegram:42"})


def test_duplicate_key_is_not_claimed():
    db = _db(APIError({"code": "23505", "message": "duplicate key value"}))
    with patch("core.dedupe.get_service_supabase", return_value=db):
        assert claim_update("telegram:42") is False


def test_other_database_errors_propagate():
    db = _db(APIError({"code": "42P01", "message": "relation does not exist"}))
    with patch("core.dedupe.get_service_supabase", return_value=db):
        with pytest.raises(APIError):
            claim_update("telegram:42")
