from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.types import FixedDecimal
from datetime import date, datetime


class Product(Base):
    __tablename__ = "products"

    __table_args__ = (
        CheckConstraint(
            "price_per_litre >= 0",
            name="product_price_nonnegative",
        ),
        CheckConstraint(
            "available_litres >= 0",
            name="product_stock_nonnegative",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    price_per_litre: Mapped[Decimal] = mapped_column(
        FixedDecimal(),
        nullable=False,
    )

    available_litres: Mapped[Decimal] = mapped_column(
        FixedDecimal(),
        nullable=False,
    )

class User(Base):
    __tablename__ = "users"

    __table_args__ = (
        CheckConstraint(
            "account_balance >= 0",
            name="user_balance_nonnegative",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    first_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    last_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
    )

    birthdate: Mapped[date] = mapped_column(
        nullable=False,
    )

    account_balance: Mapped[Decimal] = mapped_column(
        FixedDecimal(),
        default=Decimal("0.00"),
        server_default="0",
        nullable=False,
    )

    password_hash: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    auth_version: Mapped[int] = mapped_column(
        default=0,
        server_default="0",
        nullable=False,
    )

class Admin(Base):
    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(primary_key=True)

    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
    )

    api_key_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

class Purchase(Base):
    __tablename__ = "purchases"

    __table_args__ = (
        CheckConstraint(
            "litres > 0",
            name="purchase_litres_positive",
        ),
        CheckConstraint(
            "price_per_litre >= 0",
            name="purchase_price_nonnegative",
        ),
        CheckConstraint(
            "total_price >= 0",
            name="purchase_total_nonnegative",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
    )

    product_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    price_per_litre: Mapped[Decimal] = mapped_column(
        FixedDecimal(),
        nullable=False,
    )

    litres: Mapped[Decimal] = mapped_column(
        FixedDecimal(),
        nullable=False,
    )

    total_price: Mapped[Decimal] = mapped_column(
        FixedDecimal(),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(),
        server_default=func.current_timestamp(),
        nullable=False,
    )