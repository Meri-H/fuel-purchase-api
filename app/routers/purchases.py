from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Purchase
from app.schemas import PurchaseCreate, PurchaseCreated, PurchaseRead
from app.security import (
    UserIdentity,
    get_user_identity,
    resolve_user,
)
from app.services.purchases import purchase_fuel


router = APIRouter(
    prefix="/api/purchases",
    tags=["Purchases"],
)


@router.post(
    "/",
    response_model=PurchaseCreated,
    status_code=status.HTTP_201_CREATED,
)
def create_purchase(
    data: PurchaseCreate,
    db: Annotated[Session, Depends(get_db)],
    identity: Annotated[
        UserIdentity,
        Depends(get_user_identity),
    ],
):
    return purchase_fuel(
        db=db,
        identity=identity,
        data=data,
    )


@router.get(
    "/",
    response_model=list[PurchaseRead],
)
def list_purchases(
    db: Annotated[Session, Depends(get_db)],
    identity: Annotated[
        UserIdentity,
        Depends(get_user_identity),
    ],
):
    user = resolve_user(db, identity)

    return db.scalars(
        select(Purchase)
        .where(Purchase.user_id == user.id)
        .order_by(
            Purchase.created_at.desc(),
            Purchase.id.desc(),
        )
    ).all()