from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class ExpenseCreate(BaseModel):
    title: str = Field(min_length=1,max_length=255)
    amount: Decimal = Field(gt=0)
    category: str = Field(max_length=255)
    expense_date: date

class ExpenseResponse(BaseModel):
    id: int
    title: str
    amount: Decimal
    category: str
    expense_date: date

    model_config = {"from_attributes": True}

class ExpenseSummary(BaseModel):
    total: Decimal

class ExpenseCategorySummary(BaseModel):
    category: str
    total: Decimal

class ExpenseDailySummary(BaseModel):
    date: date
    total: Decimal

class MonthlyCategoryReport(BaseModel):
    year: int
    month: int
    total: Decimal
    categories: list[ExpenseCategorySummary]

class MonthlyDailyReport(BaseModel):
    year: int
    month: int
    total: Decimal
    daily: list[ExpenseDailySummary]

class ExpenseUpdate(BaseModel):
    title: str = Field(max_length=255)
    amount: Decimal = Field(gt=0)
    category: str = Field(max_length=255)
    expense_date:date


class ExpensePatch(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    amount: Decimal | None = Field(default=None, gt=0)
    category: str | None = Field(default=None, max_length=255)
    expense_date: date | None = None


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

class PasswordChange(BaseModel):
    current_password: str = Field(min_length=8)
    new_password: str = Field(min_length=8)

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
