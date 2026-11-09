from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Response, status
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import User
from app.schemas import TokenResponse
from app.security import (
    create_access_token,
    hash_secret,
    verify_secret,
)


router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"],
)

dummy_password_hash = hash_secret(
    "dummy-password-for-verification"
)


@router.post(
    "/token/",
    response_model=TokenResponse,
)
def login(
    response: Response,
    username: Annotated[
        str,
        Form(min_length=1, max_length=50),
    ],
    password: Annotated[
        SecretStr,
        Form(min_length=1, max_length=128),
    ],
    db: Annotated[Session, Depends(get_db)],
):
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid username or password.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    user = db.scalar(
        select(User).where(
            User.username == username
        )
    )

    stored_hash = (
        user.password_hash
        if user is not None and user.password_hash
        else dummy_password_hash
    )

    password_is_valid = verify_secret(
        password.get_secret_value(),
        stored_hash,
    )

    if (
        user is None
        or user.password_hash is None
        or not password_is_valid
    ):
        raise unauthorized

    token = create_access_token(
        user_id=user.id,
        auth_version=user.auth_version,
    )

    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"

    return TokenResponse(
        access_token=token,
        expires_in=get_settings().access_token_minutes * 60,
    )