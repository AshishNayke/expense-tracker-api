from decimal import Decimal

from pydantic import BaseModel, Field


class ExpenseCreate(BaseModel):
    title: str = Field(max_length=255)
    amount: Decimal = Field(gt=0)
    category: str = Field(max_length=255)


class ExpenseResponse(BaseModel):
    id: int
    title: str
    amount: Decimal
    category: str

    model_config = {"from_attributes": True}


class ExpenseUpdate(BaseModel):
    title: str = Field(max_length=255)
    amount: Decimal = Field(gt=0)
    category: str = Field(max_length=255)


class ExpensePatch(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    amount: Decimal | None = Field(default=None, gt=0)
    category: str | None = Field(default=None, max_length=255)


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: str = Field(max_length=255)
    password: str = Field(min_length=8)


class UserResponse(BaseModel):
    id: int
    username: str
    email: str

    model_config = {
        "from_attributes": True
    }

class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8) 

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
