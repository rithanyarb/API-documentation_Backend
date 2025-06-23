# === backend/app/schemas/auth.py ===
from pydantic import BaseModel, Field
from typing import Optional

class CreateUserRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: str = Field(min_length=3)
    name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=6)
    is_active: bool = True

class UserResponse(BaseModel):
    id: int
    username: str
    name: str
    email: str
    is_active: bool

class Token(BaseModel):
    access_token: str
    token_type: str

class LoginResponse(BaseModel):
    user: UserResponse
    access_token: str