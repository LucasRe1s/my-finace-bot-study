from fastapi import APIRouter, Depends
from ..auth import get_current_user

router = APIRouter(prefix="/summary", tags=["summary"])


@router.get("/")
async def get_summary(user: dict = Depends(get_current_user)):
    return {}
