from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str

class ExpenseCreate(BaseModel):
    title: str = Field(min_length=1,max_length=255)
    amount: Decimal = Field(gt=0, max_digits=10,decimal_places=2)
    category: str = Field(max_length=255)
    expense_date: date

class ExpenseResponse(BaseModel):
    id: int
    title: str
    amount: Decimal
    category: str
    expense_date: date
    version: int

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
    amount: Decimal = Field(gt=0,max_digits=10,decimal_places=2)
    category: str = Field(max_length=255)
    expense_date:date
    expected_version: int = Field(ge=1)


class ExpensePatch(BaseModel):
    title: str = Field(default=None, max_length=255)
    amount: Decimal = Field(default=None, gt=0,max_digits=10,decimal_places=2)
    category: str = Field(default=None, max_length=255)
    expense_date: date = None
    expected_version: int = Field(ge=1)


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

class PasswordChangeResponse(BaseModel):
    message: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
