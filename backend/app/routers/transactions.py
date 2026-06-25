from fastapi import APIRouter, Depends
from ..auth import get_current_user

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("/")
async def list_transactions(user: dict = Depends(get_current_user)):
    return []
