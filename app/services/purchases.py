from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import Product, Purchase
from app.schemas import PurchaseCreate, PurchaseCreated
from app.security import UserIdentity, resolve_user

def purchase_fuel(
    db: Session,
    identity: UserIdentity,
    data: PurchaseCreate,
) -> PurchaseCreated:
    with db.begin():
        db.execute(text("BEGIN IMMEDIATE"))

        user = resolve_user(db, identity)



        product = db.get(Product, data.product_id)

        if product is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product does not exist.",
            )

        if data.litres > product.available_litres:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Not enough fuel available.",
            )

        total_price = (
            product.price_per_litre * data.litres
        ).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

        if total_price > user.account_balance:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Insufficient balance.",
            )

        user.account_balance -= total_price
        product.available_litres -= data.litres

        purchase = Purchase(
            user_id=user.id,
            product_id=product.id,
            product_name=product.name,
            price_per_litre=product.price_per_litre,
            litres=data.litres,
            total_price=total_price,
        )

        db.add(purchase)
        db.flush()
        db.refresh(purchase)

        response = PurchaseCreated(
            id=purchase.id,
            product=purchase.product_name,
            litres=purchase.litres,
            total_price=purchase.total_price,
            created_at=purchase.created_at,
            remaining_balance=user.account_balance,
            remaining_stock_litres=product.available_litres,
        )

    return response