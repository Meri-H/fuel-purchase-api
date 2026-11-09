from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Product, User
from app.schemas import (
    ProductCreate,
    ProductRead,
    ProductUpdate,
    UserCreate,
    UserRead,
    UserUpdate,
)
from app.security import require_admin, hash_secret
from sqlalchemy import text, select


router = APIRouter(
    prefix="/api/admin",
    tags=["Administrator"],
    dependencies=[Depends(require_admin)],
)


@router.post(
    "/products/",
    response_model=ProductRead,
    status_code=status.HTTP_201_CREATED,
)
def create_product(
    data: ProductCreate,
    db: Annotated[Session, Depends(get_db)],
):
    with db.begin():
        product = Product(**data.model_dump())

        db.add(product)
        db.flush()

        response = ProductRead.model_validate(product)

    return response

@router.patch(
    "/products/{product_id}/",
    response_model=ProductRead,
)
def update_product(
    product_id: Annotated[int, Path(gt=0)],
    data: ProductUpdate,
    db: Annotated[Session, Depends(get_db)],
):
    changes = data.model_dump(exclude_unset=True)

    with db.begin():
        db.execute(text("BEGIN IMMEDIATE"))

        product = db.get(Product, product_id)

        if product is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product does not exist.",
            )

        for field_name, value in changes.items():
            setattr(product, field_name, value)

        db.flush()

        response = ProductRead.model_validate(product)

    return response

@router.post(
    "/users/",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
)
def create_user(
    data: UserCreate,
    db: Annotated[Session, Depends(get_db)],
):
    password_hash = None

    if data.password is not None:
        password_hash = hash_secret(
            data.password.get_secret_value()
        )

    user = User(
        **data.model_dump(exclude={"password"}),
        password_hash=password_hash,
    )

    with db.begin():
        db.execute(text("BEGIN IMMEDIATE"))

        existing_user_id = db.scalar(
            select(User.id).where(
                User.username == data.username
            )
        )

        if existing_user_id is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username already exists.",
            )

        db.add(user)
        db.flush()

        response = UserRead.model_validate(user)

    return response


@router.patch(
    "/users/{user_id}/",
    response_model=UserRead,
)
def update_user(
    user_id: Annotated[int, Path(gt=0)],
    data: UserUpdate,
    db: Annotated[Session, Depends(get_db)],
):
    changes = data.model_dump(
        exclude_unset=True,
        exclude={"password"},
    )

    password_hash = None

    if data.password is not None:
        password_hash = hash_secret(
            data.password.get_secret_value()
        )

    with db.begin():
        db.execute(text("BEGIN IMMEDIATE"))

        user = db.get(User, user_id)

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User does not exist.",
            )

        if "username" in changes:
            existing_user_id = db.scalar(
                select(User.id).where(
                    User.username == changes["username"],
                    User.id != user_id,
                )
            )

            if existing_user_id is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Username already exists.",
                )

        for field_name, value in changes.items():
            setattr(user, field_name, value)

        if password_hash is not None:
            user.password_hash = password_hash
            user.auth_version += 1

        db.flush()

        response = UserRead.model_validate(user)

    return response