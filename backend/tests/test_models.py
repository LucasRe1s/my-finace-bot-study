import pytest
from datetime import date
from app.models.transaction import TransactionCreate, TransactionType


def test_transaction_amount_positive():
    with pytest.raises(ValueError):
        TransactionCreate(amount=-10, type="expense", category="Alimentação")


def test_transaction_invalid_category():
    with pytest.raises(ValueError):
        TransactionCreate(amount=10, type="expense", category="Mercado")


def test_transaction_valid():
    t = TransactionCreate(amount=50.0, type="expense", category="Alimentação")
    assert t.amount == 50.0
    assert t.date == date.today()


def test_transaction_amount_rounds():
    t = TransactionCreate(amount=50.999, type="expense", category="Alimentação")
    assert t.amount == 51.0
