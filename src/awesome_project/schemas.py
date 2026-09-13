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
