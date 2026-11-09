import os
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from app.models import Admin, Product, User


# Set these before importing the application.
# Tests must not connect to the development database.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["USER_AUTH_MODE"] = "basic"
os.environ["JWT_SECRET"] = (
    "test-only-secret-abcdefghijklmnopqrstuvwxyz-0123456789"
)

from app import database, security
from app.database import Base, enable_foreign_keys, get_db
from app.main import app
from app.models import Product, User


@pytest.fixture
def db_factory(tmp_path, monkeypatch):
    database_file = tmp_path / "test.db"

    test_engine = create_engine(
        f"sqlite:///{database_file.as_posix()}",
        connect_args={"check_same_thread": False},
    )

    event.listen(
        test_engine,
        "connect",
        enable_foreign_keys,
    )

    Base.metadata.create_all(test_engine)

    factory = sessionmaker(
        bind=test_engine,
        expire_on_commit=False,
    )

    monkeypatch.setattr(database, "SessionLocal", factory)
    monkeypatch.setattr(security, "SessionLocal", factory)

    yield factory

    test_engine.dispose()


@pytest.fixture
def client(db_factory):
    def override_get_db():
        with db_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def purchase_setup(db_factory):
    with db_factory.begin() as session:
        user = User(
            first_name="John",
            last_name="Smith",
            username="john",
            birthdate=date(2000, 1, 1),
            account_balance=Decimal("10000.00"),
        )

        product = Product(
            name="Petrol 95",
            price_per_litre=Decimal("500.00"),
            available_litres=Decimal("1000.00"),
        )

        session.add_all([user, product])
        session.flush()

        return {
            "user_id": user.id,
            "product_id": product.id,
        }
@pytest.fixture
def admin_headers(db_factory):
    api_key = "reviewer.testing-key"

    with db_factory.begin() as session:
        session.add(
            Admin(
                username="reviewer",
                api_key_hash=security.hash_secret(api_key),
            )
        )

    return {"X-Admin-Key": api_key}