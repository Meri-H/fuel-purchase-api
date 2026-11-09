import pytest
from sqlalchemy import func, select

from app.models import User
from app.security import verify_secret


TEST_PASSWORD = "Learning-password-123!"


def user_payload(username="john"):
    return {
        "first_name": "John",
        "last_name": "Smith",
        "username": username,
        "birthdate": "2000-01-01",
        "password": TEST_PASSWORD,
    }


@pytest.mark.parametrize(
    "api_key",
    [
        None,
        "invalid",
        "reviewer.wrong-secret",
    ],
)
@pytest.mark.parametrize(
    "method, path, payload",
    [
        (
            "POST",
            "/api/admin/products/",
            {
                "name": "Diesel",
                "price_per_litre": "500.00",
                "available_litres": "100.00",
            },
        ),
        (
            "PATCH",
            "/api/admin/products/1/",
            {"price_per_litre": "550.00"},
        ),
        (
            "POST",
            "/api/admin/users/",
            {
                "first_name": "John",
                "last_name": "Smith",
                "username": "john",
                "birthdate": "2000-01-01",
            },
        ),
        (
            "PATCH",
            "/api/admin/users/1/",
            {"account_balance": "1000.00"},
        ),
    ],
)
def test_management_requires_valid_admin_key(
    client,
    admin_headers,
    api_key,
    method,
    path,
    payload,
):
    headers = {}

    if api_key is not None:
        headers["X-Admin-Key"] = api_key

    response = client.request(
        method,
        path,
        headers=headers,
        json=payload,
    )

    assert response.status_code == 401


def test_create_user_defaults_and_password_hash(
    client,
    db_factory,
    admin_headers,
):
    response = client.post(
        "/api/admin/users/",
        headers=admin_headers,
        json=user_payload(),
    )

    assert response.status_code == 201

    body = response.json()

    assert body["username"] == "john"
    assert body["account_balance"] == "0.00"
    assert "password" not in body
    assert "password_hash" not in body
    assert "auth_version" not in body

    with db_factory() as session:
        user = session.get(User, body["id"])

        assert user.password_hash != TEST_PASSWORD
        assert verify_secret(
            TEST_PASSWORD,
            user.password_hash,
        )


def test_duplicate_username_creates_no_extra_user(
    client,
    db_factory,
    admin_headers,
):
    first = client.post(
        "/api/admin/users/",
        headers=admin_headers,
        json=user_payload(),
    )

    second = client.post(
        "/api/admin/users/",
        headers=admin_headers,
        json=user_payload(),
    )

    assert first.status_code == 201
    assert second.status_code == 409

    with db_factory() as session:
        count = session.scalar(
            select(func.count()).select_from(User)
        )

        assert count == 1


def test_update_balance_and_password(
    client,
    db_factory,
    admin_headers,
):
    created = client.post(
        "/api/admin/users/",
        headers=admin_headers,
        json=user_payload(),
    )

    assert created.status_code == 201

    user_id = created.json()["id"]
    new_password = "Updated-password-123!"

    response = client.patch(
        f"/api/admin/users/{user_id}/",
        headers=admin_headers,
        json={
            "account_balance": "15000.00",
            "password": new_password,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["account_balance"] == "15000.00"
    assert body["username"] == "john"
    assert "password" not in body
    assert "password_hash" not in body

    with db_factory() as session:
        user = session.get(User, user_id)

        assert user.auth_version == 1
        assert verify_secret(
            new_password,
            user.password_hash,
        )
        assert not verify_secret(
            TEST_PASSWORD,
            user.password_hash,
        )


def test_username_conflict_rejects_entire_update(
    client,
    db_factory,
    admin_headers,
):
    john = client.post(
        "/api/admin/users/",
        headers=admin_headers,
        json=user_payload("john"),
    )

    mary = client.post(
        "/api/admin/users/",
        headers=admin_headers,
        json=user_payload("mary"),
    )

    assert john.status_code == 201
    assert mary.status_code == 201

    john_id = john.json()["id"]

    response = client.patch(
        f"/api/admin/users/{john_id}/",
        headers=admin_headers,
        json={
            "username": "mary",
            "account_balance": "9999.00",
        },
    )

    assert response.status_code == 409

    with db_factory() as session:
        user = session.get(User, john_id)

        assert user.username == "john"
        assert user.account_balance == 0