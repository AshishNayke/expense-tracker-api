from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Expense, User
from ..schemas import (
    ExpenseCreate,
    ExpensePatch,
    ExpenseResponse,
    ExpenseUpdate,
)
from ..security import get_current_user

router = APIRouter(prefix="/expenses", tags=["expenses"])


@router.get("", response_model=list[ExpenseResponse])
def get_expenses(
    category: str | None = None,
    limit: int = Query(default=20, gt=0, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(Expense).where(Expense.user_id == current_user.id)

    if category is not None:
        stmt = stmt.where(Expense.category == category)

    stmt = stmt.order_by(Expense.amount.desc())
    stmt = stmt.limit(limit).offset(offset)

    expenses = db.scalars(stmt).all()
    return expenses


@router.get("/{expense_id}", response_model=ExpenseResponse)
def get_expense(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(Expense).where(
        Expense.id == expense_id,
        Expense.user_id == current_user.id,
    )
    expense = db.scalar(stmt)

    if expense is None:
        raise HTTPException(status_code=404, detail="Expense not found")

    return expense


@router.post(
    "", 
    response_model=ExpenseResponse, 
    status_code=status.HTTP_201_CREATED,
)
def create_expense(
    expense: ExpenseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    new_expense = Expense(
        title=expense.title,
        amount=expense.amount,
        category=expense.category,
        user_id=current_user.id,
    )

    db.add(new_expense)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise

    db.refresh(new_expense)
    return new_expense


@router.put("/{expense_id}", response_model=ExpenseResponse)
def update_expense(
    expense_id: int,
    expense: ExpenseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(Expense).where(
        Expense.id == expense_id,
        Expense.user_id == current_user.id,
    )
    existing_expense = db.scalar(stmt)

    if existing_expense is None:
        raise HTTPException(status_code=404, detail="Expense not found")

    existing_expense.title = expense.title
    existing_expense.amount = expense.amount
    existing_expense.category = expense.category

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise

    db.refresh(existing_expense)

    return existing_expense


@router.patch("/{expense_id}", response_model=ExpenseResponse)
def patch_expense(
    expense_id: int,
    expense: ExpensePatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(Expense).where(
        Expense.id == expense_id,
        Expense.user_id == current_user.id,
    )
    existing_expense = db.scalar(stmt)

    if existing_expense is None:
        raise HTTPException(status_code=404, detail="Expense not found")

    updates = expense.model_dump(exclude_unset=True)

    if not updates:
        raise HTTPException(
            status_code=400,
            detail="At least one field must be provided",
        )

    for field, value in updates.items():
        setattr(existing_expense, field, value)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise

    db.refresh(existing_expense)

    return existing_expense


@router.delete("/{expense_id}", response_model=ExpenseResponse)
def delete_expense(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(Expense).where(
        Expense.id == expense_id,
        Expense.user_id == current_user.id,
    )
    expense = db.scalar(stmt)

    if expense is None:
        raise HTTPException(status_code=404, detail="Expense not found")

    db.delete(expense)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()

    return expense