import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..schemas import (
    LoginRequest,
    PasswordChange,
    TokenResponse,
    UserCreate,
    UserResponse,
)
from ..security import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["users"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
def register_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
):
    user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
    )

    db.add(user)

    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email already exists",
        )

    return user


@router.post(
    "/login", response_model=TokenResponse, summary="Log in and obtain an access token"
)
def login_user(
    user_data: LoginRequest,
    db: Session = Depends(get_db),
):
    stmt = select(User).where(User.username == user_data.username)
    user = db.scalar(stmt)

    if user is None or not verify_password(
        user_data.password,
        user.hashed_password,
    ):
        logger.warning(
            "Failed login attempt: username=%s",
            user_data.username,
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    logger.info(
        "User logged in successfully: username=%s",
        user.username,
    )

    access_token = create_access_token({
        "sub": str(user.id),
        "email": user.email,
        "token_version": user.token_version,})

    return {
        "access_token": access_token,
        "token_type": "bearer",
    }

@router.post(
    "/change-password",
    summary="Change user's password",
)
def change_current_user_password(
    user_data: PasswordChange,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(
        user_data.current_password,
        current_user.hashed_password,
    ):
        logger.warning(
            "Failed password change attempt: username=%s",
            current_user.username,
        )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid current password",
        )
    if user_data.new_password == user_data.current_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password",
        )
    hashed_password=hash_password(user_data.new_password)

    current_user.hashed_password = hashed_password
    current_user.token_version +=1
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Failed to change password for user=%s", current_user.username)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")
    logger.info("Password changed for user=%s", current_user.username)
    return {"message":"Password changed successfully!"}

@router.get(
    "/me", response_model=UserResponse, summary="Get the current authenticated user"
)
def read_current_user(
    current_user: User = Depends(get_current_user),
):
    return current_user
