from pydantic import BaseModel


class InviteCreate(BaseModel):
    email: str


class InviteResponse(BaseModel):
    id: str
    email: str
    group_id: str
    token: str
