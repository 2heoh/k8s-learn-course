from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, ConfigDict


class PlayerBase(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr


class PlayerCreate(PlayerBase):
    pass


class PlayerUpdateFull(PlayerBase):
    """
    Полное обновление ресурса (PUT).
    """


class PlayerPartialUpdate(BaseModel):
    """
    Частичное обновление (PATCH).
    """

    username: Optional[str] = Field(default=None, min_length=3, max_length=50)
    email: Optional[EmailStr] = None


class PlayerRead(BaseModel):
    id: int
    username: str
    email: EmailStr
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

