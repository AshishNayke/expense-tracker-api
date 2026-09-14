from fastapi import FastAPI

from .routers.expenses import router as expenses_router
from .routers.users import router as users_router

app = FastAPI(title="Expense Tracker API")

@app.get("/")
def root():
    return {"message": "Expense Tracker API is running"}


app.include_router(expenses_router)
app.include_router(users_router)