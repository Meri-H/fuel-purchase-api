from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import jwt
import pytest
from sqlalchemy import func, select

from app.config import get_settings
from app.models import Product, Purchase, User
from app.security import (
    TOKEN_ALGORITHM,
    create_access_token,
    decode_access_token,
    hash_secret,
)


TEST_PASSWORD = "Learning-password-123!"


@pytest.fixture(autouse=True)
def token_mode(monkeypatch):
    monkeypatch.setenv("USER_AUTH_MODE", "token")
    get_settings.cache_clear()

    yield

    get_settings.cache_clear()


@pytest.fixture
def auth_setup(db_factory, purchase_setup):
    with db_factory.begin() as session:
        user = session.get(
            User,
            purchase_setup["user_id"],
        )
        user.password_hash = hash_secret(TEST_PASSWORD)

    return purchase_setup


def login_headers(client, username="john", password=TEST_PASSWORD):
    response = client.post(
        "/api/auth/token/",
        data={
            "username": username,
            "password": password,
        },
    )

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["expires_in"] > 0

    return {
        "Authorization": (
            "Bearer " + response.json()["access_token"]
        )
    }


def test_token_controls_purchase_and_history_identity(
    client,
    db_factory,
    auth_setup,
):
    with db_factory.begin() as session:
        session.add(
            User(
                first_name="Mary",
                last_name="Jones",
                username="mary",
                birthdate=date(2001, 5, 10),
                account_balance=Decimal("10000.00"),
                password_hash=hash_secret(TEST_PASSWORD),
            )
        )

    john_headers = login_headers(client, "john")
    mary_headers = login_headers(client, "mary")

    john_purchase = client.post(
        "/api/purchases/",
        headers={
            **john_headers,
            "X-Username": "mary",
        },
        json={
            "product_id": auth_setup["product_id"],
            "litres": "10.00",
        },
    )

    mary_purchase = client.post(
        "/api/purchases/",
        headers={
            **mary_headers,
            "X-Username": "john",
        },
        json={
            "product_id": auth_setup["product_id"],
            "litres": "1.00",
        },
    )

    assert john_purchase.status_code == 201
    assert mary_purchase.status_code == 201

    john_history = client.get(
        "/api/purchases/",
        headers={
            **john_headers,
            "X-Username": "mary",
        },
    )

    mary_history = client.get(
        "/api/purchases/",
        headers={
            **mary_headers,
            "X-Username": "john",
        },
    )

    assert john_history.status_code == 200
    assert mary_history.status_code == 200

    assert [
        purchase["id"] for purchase in john_history.json()
    ] == [john_purchase.json()["id"]]

    assert [
        purchase["id"] for purchase in mary_history.json()
    ] == [mary_purchase.json()["id"]]

    with db_factory() as session:
        john = session.get(User, auth_setup["user_id"])
        mary = session.scalar(
            select(User).where(User.username == "mary")
        )

        assert john.account_balance == Decimal("5000.00")
        assert mary.account_balance == Decimal("9500.00")


@pytest.mark.parametrize(
    "username, password",
    [
        ("john", "wrong-password"),
        ("unknown", TEST_PASSWORD),
    ],
)
def test_login_rejects_incorrect_credentials(
    client,
    auth_setup,
    username,
    password,
):
    response = client.post(
        "/api/auth/token/",
        data={
            "username": username,
            "password": password,
        },
    )

    assert response.status_code == 401
    assert response.json()["error"] == "Invalid username or password."


@pytest.mark.parametrize(
    "kind",
    [
        "missing",
        "malformed",
        "expired",
        "wrong_signature",
        "unknown_user",
    ],
)
def test_invalid_tokens_cannot_access_purchases(
    client,
    db_factory,
    auth_setup,
    kind,
):
    token = create_access_token(
        user_id=auth_setup["user_id"],
        auth_version=0,
    )

    if kind == "missing":
        token = None

    elif kind == "malformed":
        token = "invalid-token"

    elif kind == "unknown_user":
        token = create_access_token(
            user_id=auth_setup["user_id"] + 1000,
            auth_version=0,
        )

    else:
        claims = decode_access_token(token)
        signing_secret = get_settings().jwt_secret.get_secret_value()

        if kind == "expired":
            claims["exp"] = (
                datetime.now(UTC) - timedelta(minutes=1)
            ).timestamp()

        else:
            signing_secret = (
                "different-test-secret-abcdefghijklmnopqrstuvwxyz"
            )

        token = jwt.encode(
            claims,
            signing_secret,
            algorithm=TOKEN_ALGORITHM,
        )

    headers = {"X-Username": "john"}

    if token is not None:
        headers["Authorization"] = "Bearer " + token

    history = client.get(
        "/api/purchases/",
        headers=headers,
    )

    purchase = client.post(
        "/api/purchases/",
        headers=headers,
        json={
            "product_id": auth_setup["product_id"],
            "litres": "10.00",
        },
    )

    assert history.status_code == 401
    assert purchase.status_code == 401

    with db_factory() as session:
        user = session.get(User, auth_setup["user_id"])
        product = session.get(Product, auth_setup["product_id"])

        count = session.scalar(
            select(func.count()).select_from(Purchase)
        )

        assert user.account_balance == Decimal("10000.00")
        assert product.available_litres == Decimal("1000.00")
        assert count == 0


def test_password_reset_invalidates_old_token(
    client,
    auth_setup,
    admin_headers,
):
    old_headers = login_headers(client)

    reset = client.patch(
        f"/api/admin/users/{auth_setup['user_id']}/",
        headers=admin_headers,
        json={"password": "Updated-password-123!"},
    )

    assert reset.status_code == 200

    history = client.get(
        "/api/purchases/",
        headers=old_headers,
    )

    purchase = client.post(
        "/api/purchases/",
        headers=old_headers,
        json={
            "product_id": auth_setup["product_id"],
            "litres": "10.00",
        },
    )

    assert history.status_code == 401
    assert purchase.status_code == 401

    new_headers = login_headers(
        client,
        password="Updated-password-123!",
    )

    assert client.get(
        "/api/purchases/",
        headers=new_headers,
    ).status_code == 200


def test_user_token_does_not_grant_admin_access(
    client,
    auth_setup,
):
    headers = login_headers(client)

    response = client.patch(
        f"/api/admin/users/{auth_setup['user_id']}/",
        headers=headers,
        json={"account_balance": "99999.00"},
    )

    assert response.status_code == 401