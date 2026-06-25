from pydantic import BaseModel, field_validator, model_validator
from datetime import date
from enum import Enum
from typing import Optional

VALID_CATEGORIES = {
    "Alimentação", "Transporte", "Moradia", "Saúde",
    "Educação", "Lazer", "Vestuário", "Outros"
}


class TransactionType(str, Enum):
    income = "income"
    expense = "expense"


class TransactionCreate(BaseModel):
    amount: float
    type: TransactionType
    category: str
    description: str = ""
    date: Optional[date] = None

    @field_validator("amount")
    @classmethod
    def amount_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Valor deve ser positivo")
        return round(v, 2)

    @field_validator("category")
    @classmethod
    def category_valid(cls, v: str) -> str:
        if v not in VALID_CATEGORIES:
            raise ValueError(f"Categoria inválida. Use uma de: {', '.join(sorted(VALID_CATEGORIES))}")
        return v

    @model_validator(mode="after")
    def default_date(self) -> "TransactionCreate":
        if self.date is None:
            self.date = date.today()
        return self


class Transaction(TransactionCreate):
    id: str
    user_id: str
    group_id: str
    created_at: str
