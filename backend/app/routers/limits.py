import calendar
from datetime import date

from fastapi import APIRouter, Depends, status
from supabase import Client

from ..auth import get_current_user
from ..database import get_supabase
from ..models.limit import Limit, LimitCreate
from ..routers.transactions import _get_user_group

router = APIRouter(prefix="/limits", tags=["limits"])


def _get_month_spent(db: Client, group_id: str, category: str) -> float:
    today = date.today()
    first_day = f"{today.year}-{today.month:02d}-01"
    last_day = f"{today.year}-{today.month:02d}-{calendar.monthrange(today.year, today.month)[1]}"
    result = (
        db.table("transactions")
        .select("amount")
        .eq("group_id", group_id)
        .eq("category", category)
        .eq("type", "expense")
        .gte("date", first_day)
        .lte("date", last_day)
        .execute()
    )
    return round(sum(t["amount"] for t in (result.data or [])), 2)


@router.post("/", response_model=Limit, status_code=status.HTTP_201_CREATED)
async def upsert_limit(
    data: LimitCreate,
    user: dict = Depends(get_current_user),
):
    db = get_supabase()
    group_id = _get_user_group(db, user["id"])
    result = (
        db.table("category_limits")
        .upsert(
            {
                "group_id": group_id,
                "category": data.category,
                "monthly_limit": data.monthly_limit,
            },
            on_conflict="group_id,category",
        )
        .execute()
    )
    limit_data = result.data[0]
    spent = _get_month_spent(db, group_id, data.category)
    percent = round((spent / data.monthly_limit) * 100, 1) if data.monthly_limit > 0 else 0.0
    return {**limit_data, "spent": spent, "percent_used": percent}


@router.get("/", response_model=list[Limit])
async def list_limits(
    user: dict = Depends(get_current_user),
):
    db = get_supabase()
    group_id = _get_user_group(db, user["id"])
    result = db.table("category_limits").select("*").eq("group_id", group_id).execute()
    limits = []
    for lim in result.data or []:
        spent = _get_month_spent(db, group_id, lim["category"])
        percent = round((spent / lim["monthly_limit"]) * 100, 1) if lim["monthly_limit"] > 0 else 0.0
        limits.append({**lim, "spent": spent, "percent_used": percent})
    return limits
