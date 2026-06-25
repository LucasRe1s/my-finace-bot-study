from pydantic import BaseModel, field_validator

from .transaction import VALID_CATEGORIES


class LimitCreate(BaseModel):
    category: str
    monthly_limit: float

    @field_validator("category")
    @classmethod
    def category_valid(cls, v: str) -> str:
        if v not in VALID_CATEGORIES:
            raise ValueError(f"Categoria inválida: {v}")
        return v

    @field_validator("monthly_limit")
    @classmethod
    def limit_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Limite deve ser positivo")
        return round(v, 2)


class Limit(LimitCreate):
    id: str
    group_id: str
    spent: float = 0.0
    percent_used: float = 0.0
