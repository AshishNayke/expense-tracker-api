import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import settings
from .logging_config import configure_logging
from .routers.expenses import router as expenses_router
from .routers.health import router as health_router
from .routers.users import router as users_router

configure_logging()

logger = logging.getLogger(__name__)



@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application starting")
    yield

    logger.info("Application shutting down")



app = FastAPI(
    title="Expense Tracker API",
    lifespan=lifespan,
    docs_url="/docs" if settings.app_env == "development" else None,
    redoc_url="/redoc" if settings.app_env == "development" else None,
)

@app.get("/")
def root():
    return {"message": "Expense Tracker API is running"}


app.include_router(expenses_router)
app.include_router(users_router)
app.include_router(health_router)