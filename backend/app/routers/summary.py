import calendar
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from supabase import Client

from ..auth import get_current_user
from ..database import get_supabase
from ..routers.transactions import _get_user_group

router = APIRouter(prefix="/summary", tags=["summary"])


@router.get("/")
async def get_summary(
    month: Optional[str] = Query(None, description="YYYY-MM, padrão: mês atual"),
    user: dict = Depends(get_current_user),
):
    if not month:
        today = date.today()
        month = f"{today.year}-{today.month:02d}"

    year, mon = month.split("-")
    first_day = f"{year}-{mon}-01"
    last_day = f"{year}-{mon}-{calendar.monthrange(int(year), int(mon))[1]}"

    db = get_supabase()
    group_id = _get_user_group(db, user["id"])
    result = (
        db.table("transactions")
        .select("type, amount, category")
        .eq("group_id", group_id)
        .gte("date", first_day)
        .lte("date", last_day)
        .execute()
    )

    transactions = result.data or []
    total_income = sum(t["amount"] for t in transactions if t["type"] == "income")
    total_expense = sum(t["amount"] for t in transactions if t["type"] == "expense")

    by_category: dict[str, float] = {}
    for t in transactions:
        if t["type"] == "expense":
            by_category[t["category"]] = by_category.get(t["category"], 0) + t["amount"]

    return {
        "month": month,
        "total_income": round(total_income, 2),
        "total_expense": round(total_expense, 2),
        "balance": round(total_income - total_expense, 2),
        "by_category": [
            {"category": k, "total": round(v, 2)}
            for k, v in sorted(by_category.items(), key=lambda x: -x[1])
        ],
    }
