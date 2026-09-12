from fastapi import FastAPI , HTTPException , Depends 
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from .database import get_db
from .models import Expense
from decimal import Decimal

app = FastAPI(title="Expense Tracker API")

class ExpenseCreate(BaseModel):
    title: str = Field(max_length=255)
    amount: Decimal = Field(gt=0)
    category: str = Field(max_length=255)

class ExpenseResponse(BaseModel):
    id: int
    title: str = Field(max_length=255)
    amount: Decimal 
    category: str = Field(max_length=255)
    model_config = {
        "from_attributes": True
    }
class ExpenseUpdate(BaseModel):
    title: str = Field(max_length=255)
    amount: Decimal = Field(gt=0)
    category: str = Field(max_length=255)

class ExpensePatch(BaseModel):
    title: str | None = Field(default=None,max_length=255)
    amount: Decimal | None = Field(default=None, gt=0)
    category: str | None = Field(default=None,max_length=255)

@app.get("/")
def root():
    return {"message": "Expense Tracker API is running"}

@app.get("/expenses", response_model=list[ExpenseResponse])
def get_expenses(db: Session = Depends(get_db)):
    expenses = db.query(Expense).all()
    return expenses
 
@app.get("/expenses/{id}",response_model=ExpenseResponse)
def get_expense(
    id:int,
    db: Session = Depends(get_db),
):
    expense = db.get(Expense,id)
    if expense is None:
        raise HTTPException(status_code=404, detail="Expense not found")
    return expense

@app.post("/expenses", response_model=ExpenseResponse)
def create_expense(
    expense: ExpenseCreate,
    db: Session = Depends(get_db),
):
    new_expense = Expense(
    title=expense.title,
    amount=expense.amount,
    category=expense.category,
)
    db.add(new_expense)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise

    db.refresh(new_expense)
    return new_expense

@app.put("/expenses/{id}",response_model=ExpenseResponse)
def update_expense(
    id:int,
    expense:ExpenseUpdate,
    db: Session = Depends(get_db),
):
    existing_expense = db.get(Expense, id)
    
    if existing_expense is None:
        raise HTTPException(status_code=404, detail="Expense not found")
    existing_expense.title = expense.title
    existing_expense.amount = expense.amount
    existing_expense.category = expense.category
    
    db.commit()
    db.refresh(existing_expense)

    return existing_expense

@app.patch("/expenses/{id}", response_model=ExpenseResponse)
def patch_expense(
    id: int,
    expense: ExpensePatch,
    db: Session = Depends(get_db),
):
    existing_expense = db.get(Expense, id)
    
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
    db.commit()
    db.refresh(existing_expense)

    return existing_expense

@app.delete("/expenses/{id}",response_model=ExpenseResponse)
def delete_expense(
    id:int,
    db: Session = Depends(get_db),
):
    expense = db.get(Expense, id)

    if expense is None:
        raise HTTPException(status_code=404, detail="Expense not found")

    db.delete(expense)
    db.commit()

    return expense

