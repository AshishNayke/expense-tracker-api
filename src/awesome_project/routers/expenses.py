import logging
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Expense, User
from ..schemas import (
    ExpenseCategorySummary,
    ExpenseCreate,
    ExpenseDailySummary,
    ExpensePatch,
    ExpenseResponse,
    ExpenseSummary,
    ExpenseUpdate,
    MonthlyCategoryReport,
    MonthlyDailyReport,
)
from ..security import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/expenses", tags=["expenses"])


@router.get(
    "",
    response_model=list[ExpenseResponse],
    summary="List the current User's Expenses",
)
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

    stmt = stmt.order_by(Expense.amount.desc(), Expense.id.asc())
    stmt = stmt.limit(limit).offset(offset)

    expenses = db.scalars(stmt).all()
    return expenses

@router.get(
    "/summary",
    response_model=ExpenseSummary
)
def get_expense_summary(
    category: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if (from_date is None) != (to_date is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="from_date and to_date must be provided together",
        )

    if (
        from_date is not None
        and to_date is not None
        and from_date > to_date
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="from_date must be less than or equal to to_date",
        )

    stmt = select(func.coalesce(func.sum(Expense.amount),Decimal("0.00"))).where(Expense.user_id == current_user.id)
    if category is not None:
        stmt = stmt.where(Expense.category == category)
    if from_date is not None:
        stmt = stmt.where(Expense.expense_date >= from_date)
    if to_date is not None:
        stmt = stmt.where(Expense.expense_date <= to_date)
    total = db.scalar(stmt)
    return {"total": total}

@router.get(
    "/report/categories",
    response_model=list[ExpenseCategorySummary],
)
def get_expense_category_report(
    from_date: date | None = None,
    to_date: date | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if (from_date is None) != (to_date is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="from_date and to_date must be provided together",
        )

    if (
        from_date is not None
        and to_date is not None
        and from_date > to_date
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="from_date must be less than or equal to to_date",
        )

    total = func.sum(Expense.amount).label("total")

    stmt = (
        select(
            Expense.category,
            total,
        )
        .where(Expense.user_id == current_user.id)
        .group_by(Expense.category)
        .order_by(total.desc())
    )

    if from_date is not None:
        stmt = stmt.where(Expense.expense_date >= from_date)

    if to_date is not None:
        stmt = stmt.where(Expense.expense_date <= to_date)

    rows = db.execute(stmt).all()

    return [
        {
            "category": row.category,
            "total": row.total,
        }
        for row in rows
    ]

@router.get(
    "/report/daily",
    response_model=list[ExpenseDailySummary],
)
def get_daily_expense_report(
    from_date: date,
    to_date: date,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if from_date > to_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="from_date must be less than or equal to to_date",
        )

    total = func.sum(Expense.amount).label("total")

    stmt = (
        select(
            Expense.expense_date,
            total,
        )
        .where(
            Expense.user_id == current_user.id,
            Expense.expense_date >= from_date,
            Expense.expense_date <= to_date,
        )
        .group_by(Expense.expense_date)
        .order_by(Expense.expense_date)
    )

    rows = db.execute(stmt).all()

    return [
        {
            "date": row.expense_date,
            "total": row.total,
        }
        for row in rows
    ]

@router.get(
    "/report/monthly",
    response_model= MonthlyCategoryReport | MonthlyDailyReport
)
def get_monthly_expense_report(
    year: int = Query(ge=1,le=9999),
    month: int = Query(ge=1,le=12),
    daily: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if year == 9999 and month == 12:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Reports for december 9999 are not supported due to year range limits.",
)

    start_date=date(year,month,1)

    next_month= month + 1
    next_year=year

    if next_month == 13:
        next_month=1
        next_year = year+1
    end_date=date(next_year,next_month,1)

    group_total = func.sum(Expense.amount).label("total")
    grouping_column = Expense.expense_date if daily is True else Expense.category

    stmt = (
        select(
            grouping_column,
            group_total,
        )
        .where(
            Expense.user_id == current_user.id,
            Expense.expense_date >= start_date,
            Expense.expense_date < end_date,
        )
        .group_by(grouping_column)
        .order_by(grouping_column)
    )
    rows = db.execute(stmt).all()
    category_result=[]
    daily_result=[]
    all_total=Decimal(0)

    for row in rows:
        grouping_value = row[0]
        grouping_total = row[1]
        all_total+=grouping_total
        if daily:
            daily_result.append(
                ExpenseDailySummary(
                    date=grouping_value,
                    total=grouping_total,
                )
            )
        else:
            category_result.append(
                ExpenseCategorySummary(
                    category=grouping_value,
                    total=grouping_total,
                )
            )
    if daily:
        return {
            "year":year,
            "month": month,
            "total": all_total,
            "daily": daily_result,
        }
    else:
        return {
            "year":year,
            "month": month,
            "total": all_total,
            "categories": category_result
        }


@router.get(
    "/{expense_id}",
    response_model=ExpenseResponse,
    summary="Get an Expense by ID",
)
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
    summary="Create a New Expense",
)
def create_expense(
    expense: ExpenseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user_id = current_user.id

    new_expense = Expense(
        title=expense.title,
        amount=expense.amount,
        category=expense.category,
        user_id=user_id,
        expense_date=expense.expense_date
    )

    db.add(new_expense)

    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception(
            "Database error creating expense for user %s",
            user_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )

    db.refresh(new_expense)
    return new_expense

@router.post(
    "/bulk",
    response_model=list[ExpenseResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create Expenses in Bulk"
)
def create_expense_bulk(
    expenses: list[ExpenseCreate],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not expenses:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="At least one expense is required"
        )

    user_id = current_user.id

    new_expenses = []
    for expense in expenses:
        new_expenses.append(
        Expense(
            title=expense.title,
            amount=expense.amount,
            category=expense.category,
            user_id=current_user.id,
            expense_date=expense.expense_date
        )
    )

    try:
        db.add_all(new_expenses)
        db.flush()
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception(
            "Failed to create %s bulk expenses for user %s",
            len(expenses),
            user_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )

    for expense in new_expenses:
        db.refresh(expense)

    return new_expenses


@router.put(
    "/{expense_id}",
    response_model=ExpenseResponse,
    summary="Replace an Expense",
)
def update_expense(
    expense_id: int,
    expense: ExpenseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user_id = current_user.id

    stmt = select(Expense).where(
        Expense.id == expense_id,
        Expense.user_id == user_id,
    )
    existing_expense = db.scalar(stmt)

    if existing_expense is None:
        raise HTTPException(status_code=404, detail="Expense not found")

    existing_expense.title = expense.title
    existing_expense.amount = expense.amount
    existing_expense.category = expense.category
    existing_expense.expense_date = expense.expense_date

    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception(
            "Database error updating expense %s for user %s",
            expense_id,
            user_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )

    db.refresh(existing_expense)

    return existing_expense


@router.patch(
    "/{expense_id}",
    response_model=ExpenseResponse,
    summary="Partially Update an Expense",
)
def patch_expense(
    expense_id: int,
    expense: ExpensePatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user_id = current_user.id

    stmt = select(Expense).where(
        Expense.id == expense_id,
        Expense.user_id == user_id,
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
    except SQLAlchemyError:
        db.rollback()
        logger.exception(
            "Database error patching expense %s for user %s",
            expense_id,
            user_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )

    db.refresh(existing_expense)

    return existing_expense


@router.delete(
    "/{expense_id}",
    response_model=ExpenseResponse,
    summary="Delete an Expense",
)
def delete_expense(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user_id = current_user.id

    stmt = select(Expense).where(
        Expense.id == expense_id,
        Expense.user_id == user_id,
    )
    expense = db.scalar(stmt)

    if expense is None:
        raise HTTPException(status_code=404, detail="Expense not found")

    # This copies the values into safe, pure Python memory.
    response_data = ExpenseResponse.model_validate(expense)

    db.delete(expense)
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception(
            "Failed to delete expense %s for user %s",
            expense_id,
            user_id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete expense",
        )

    return response_data