import hashlib
import json
import logging
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from ..database import get_db
from ..models import Expense, IdempotencyOperation, User
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

def hash_expense_batch(expenses: list[ExpenseCreate]) -> str:
    """Return a stable SHA-256 hash for a validated expense batch."""
    canonical_payload = [
        {
            "title": item.title,
            "amount": format(item.amount.normalize(), "f"),
            "category": item.category,
            "expense_date": item.expense_date.isoformat(),
        }
        for item in expenses
    ]

    canonical_json = json.dumps(
        canonical_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )

    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

@router.post(
    "/bulk",
    response_model=list[ExpenseResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create Expenses in Bulk",
)
def create_expense_bulk(
    expenses: list[ExpenseCreate],
    response: Response,
    idempotency_key: str | None = Header(
        default=None,
        alias="Idempotency-Key",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user_id = current_user.id

    # 1. Validate the request before doing any database writes.
    if not expenses:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="At least one expense is required.",
        )

    if idempotency_key is None or not idempotency_key.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The Idempotency-Key header is required.",
        )

    idempotency_key = idempotency_key.strip()

    if len(idempotency_key) > 255:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Idempotency-Key must not exceed 255 characters.",
        )

    # 2. Identify the logical request.
    request_hash = hash_expense_batch(expenses)

    operation_query = select(IdempotencyOperation).where(
        IdempotencyOperation.user_id == user_id,
        IdempotencyOperation.idempotency_key == idempotency_key,
    )

    existing_operation = db.scalar(operation_query)

    # 3. Handle ordinary retries before inserting anything.
    if existing_operation is not None:
        if existing_operation.request_hash != request_hash:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Idempotency key reused with a different request payload."
                ),
            )

        response.status_code = existing_operation.response_status
        return existing_operation.response_body

    # 4. Insert expenses and store the response in one transaction.
    try:
        new_expenses = [
            Expense(
                user_id=user_id,
                title=item.title,
                amount=item.amount,
                category=item.category,
                expense_date=item.expense_date,
            )
            for item in expenses
        ]

        db.add_all(new_expenses)

        # Send the expense INSERT statements to PostgreSQL.
        # Generated IDs and ORM version values should now be available.
        db.flush()


        response_body = [
            ExpenseResponse.model_validate(expense).model_dump(mode="json")
            for expense in new_expenses
        ]

        operation = IdempotencyOperation(
            user_id=user_id,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            response_status=status.HTTP_201_CREATED,
            response_body=response_body,
        )

        db.add(operation)

        # This flush can lose a race against another request using the
        # same key. Catch that particular constraint violation below.
        try:
            db.flush()

        except IntegrityError as exc:
            constraint_name = getattr(
                getattr(exc.orig, "diag", None),
                "constraint_name",
                None,
            )

            # The session cannot be used normally after a failed flush
            # until we roll back the failed transaction.
            db.rollback()

            if constraint_name != "uq_idempotency_operations_user_key":
                # This was a different integrity error, not the expected
                # idempotency-key race. Let the outer handler deal with it.
                raise

            # Another request committed an operation with this key.
            # Our uncommitted expense inserts have also been rolled back.
            winner_operation = db.scalar(operation_query)

            if winner_operation is None:
                logger.error(
                    "Idempotency key conflict occurred but no winning "
                    "operation was found for user %s",
                    user_id,
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Could not resolve the idempotency-key conflict.",
                ) from exc

            # A competing request may have used the same key with
            # a different payload, so compare hashes again.
            if winner_operation.request_hash != request_hash:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Idempotency key reused with a different "
                        "request payload."
                    ),
                )

            response.status_code = winner_operation.response_status
            return winner_operation.response_body

        # The expenses and their replayable response become durable together.
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

    response.status_code = status.HTTP_201_CREATED
    return response_body


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

    if expense.expected_version != existing_expense.version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Expense was modified by another request. Fetch the latest version and retry.",
        )

    existing_expense.title = expense.title
    existing_expense.amount = expense.amount
    existing_expense.category = expense.category
    existing_expense.expense_date = expense.expense_date

    try:
        db.commit()
    except StaleDataError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Expense was modified by another request. Fetch the latest version and retry.",
        )
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

    if expense.expected_version != existing_expense.version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Expense was modified by another request. Fetch the latest version and retry."
        )

    updates = expense.model_dump(
        exclude_unset=True,
        exclude={"expected_version"},
    )

    if not updates:
        raise HTTPException(
            status_code=400,
            detail="At least one field must be provided",
        )

    for field, value in updates.items():
        setattr(existing_expense, field, value)

    try:
        db.commit()
    except StaleDataError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Expense was modified by another request. Fetch the latest version and retry."
        )
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