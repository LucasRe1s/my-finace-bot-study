from pydantic import BaseModel, EmailStr


class InviteCreate(BaseModel):
    # Opcional: convites gerados no bot nao tem email.
    email: EmailStr | None = None
