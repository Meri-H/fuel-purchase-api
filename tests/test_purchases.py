from decimal import Decimal
from datetime import date

import pytest
from sqlalchemy import event, func, select

from app.models import Product, Purchase, User


def database_snapshot(db_factory, user_id, product_id):
    with db_factory() as session:
        user = session.get(User, user_id)
        product = session.get(Product, product_id)

        purchase_count = session.scalar(
            select(func.count()).select_from(Purchase)
        )

        return (
            user.account_balance,
            product.available_litres,
            purchase_count,
        )


def test_successful_purchase(
    client,
    db_factory,
    purchase_setup,
):
    response = client.post(
        "/api/purchases/",
        headers={"X-Username": "john"},
        json={
            "product_id": purchase_setup["product_id"],
            "litres": "10.00",
        },
    )

    assert response.status_code == 201

    body = response.json()

    assert body["product"] == "Petrol 95"
    assert body["litres"] == "10.00"
    assert body["total_price"] == "5000.00"
    assert body["remaining_balance"] == "5000.00"
    assert body["remaining_stock_litres"] == "990.00"

    snapshot = database_snapshot(
        db_factory,
        purchase_setup["user_id"],
        purchase_setup["product_id"],
    )

    assert snapshot == (
        Decimal("5000.00"),
        Decimal("990.00"),
        1,
    )

    with db_factory() as session:
        purchase = session.scalar(select(Purchase))

        assert purchase.user_id == purchase_setup["user_id"]
        assert purchase.product_id == purchase_setup["product_id"]
        assert purchase.litres == Decimal("10.00")
        assert purchase.total_price == Decimal("5000.00")


@pytest.mark.parametrize(
    "failure_case, expected_status, expected_message",
    [
        ("balance", 400, "Insufficient balance."),
        ("stock", 400, "Not enough fuel available."),
        ("product", 404, "Product does not exist."),
    ],
)
def test_failed_purchase_changes_nothing(
    client,
    db_factory,
    purchase_setup,
    failure_case,
    expected_status,
    expected_message,
):
    user_id = purchase_setup["user_id"]
    product_id = purchase_setup["product_id"]
    requested_product_id = product_id

    with db_factory.begin() as session:
        if failure_case == "balance":
            user = session.get(User, user_id)
            user.account_balance = Decimal("1.00")

        elif failure_case == "stock":
            product = session.get(Product, product_id)
            product.available_litres = Decimal("1.00")

        else:
            requested_product_id = product_id + 1000

    before = database_snapshot(
        db_factory,
        user_id,
        product_id,
    )

    response = client.post(
        "/api/purchases/",
        headers={"X-Username": "john"},
        json={
            "product_id": requested_product_id,
            "litres": "10.00",
        },
    )

    assert response.status_code == expected_status
    assert response.json()["error"] == expected_message

    after = database_snapshot(
        db_factory,
        user_id,
        product_id,
    )

    assert after == before

@pytest.mark.parametrize(
    "litres",
    [
        "0.00",
        "-0.00",
        "-1.00",
        "invalid",
        "NaN",
        "Infinity",
        "0.001",
        True,
    ],
)
def test_invalid_litres_change_nothing(
    client,
    db_factory,
    purchase_setup,
    litres,
):
    before = database_snapshot(
        db_factory,
        purchase_setup["user_id"],
        purchase_setup["product_id"],
    )

    response = client.post(
        "/api/purchases/",
        headers={"X-Username": "john"},
        json={
            "product_id": purchase_setup["product_id"],
            "litres": litres,
        },
    )

    assert response.status_code == 422

    after = database_snapshot(
        db_factory,
        purchase_setup["user_id"],
        purchase_setup["product_id"],
    )

    assert after == before

@pytest.mark.parametrize(
    "field",
    [
        "price_per_litre",
        "account_balance",
        "available_litres",
        "user_id",
    ],
)
def test_purchase_rejects_extra_fields(
    client,
    db_factory,
    purchase_setup,
    field,
):
    before = database_snapshot(
        db_factory,
        purchase_setup["user_id"],
        purchase_setup["product_id"],
    )

    response = client.post(
        "/api/purchases/",
        headers={"X-Username": "john"},
        json={
            "product_id": purchase_setup["product_id"],
            "litres": "10.00",
            field: 1,
        },
    )

    assert response.status_code == 422

    after = database_snapshot(
        db_factory,
        purchase_setup["user_id"],
        purchase_setup["product_id"],
    )

    assert after == before

@pytest.mark.parametrize(
    "headers, expected_status",
    [
        ({}, 400),
        ({"X-Username": ""}, 400),
        ({"X-Username": "unknown"}, 404),
    ],
)
def test_invalid_username_changes_nothing(
    client,
    db_factory,
    purchase_setup,
    headers,
    expected_status,
):
    before = database_snapshot(
        db_factory,
        purchase_setup["user_id"],
        purchase_setup["product_id"],
    )

    response = client.post(
        "/api/purchases/",
        headers=headers,
        json={
            "product_id": purchase_setup["product_id"],
            "litres": "10.00",
        },
    )

    assert response.status_code == expected_status

    after = database_snapshot(
        db_factory,
        purchase_setup["user_id"],
        purchase_setup["product_id"],
    )

    assert after == before

def test_history_contains_only_identified_users_purchases(
    client,
    db_factory,
    purchase_setup,
):
    with db_factory.begin() as session:
        session.add(
            User(
                first_name="Mary",
                last_name="Jones",
                username="mary",
                birthdate=date(2001, 5, 10),
                account_balance=Decimal("10000.00"),
            )
        )

    john_purchase = client.post(
        "/api/purchases/",
        headers={"X-Username": "john"},
        json={
            "product_id": purchase_setup["product_id"],
            "litres": "10.00",
        },
    )

    mary_purchase = client.post(
        "/api/purchases/",
        headers={"X-Username": "mary"},
        json={
            "product_id": purchase_setup["product_id"],
            "litres": "1.00",
        },
    )

    assert john_purchase.status_code == 201
    assert mary_purchase.status_code == 201

    john_history = client.get(
        "/api/purchases/",
        headers={"X-Username": "john"},
    )

    mary_history = client.get(
        "/api/purchases/",
        headers={"X-Username": "mary"},
    )

    assert john_history.status_code == 200
    assert mary_history.status_code == 200

    assert [
        purchase["id"] for purchase in john_history.json()
    ] == [john_purchase.json()["id"]]

    assert [
        purchase["id"] for purchase in mary_history.json()
    ] == [mary_purchase.json()["id"]]

    john_record = john_history.json()[0]

    assert john_record["product"] == "Petrol 95"
    assert john_record["litres"] == "10.00"
    assert john_record["total_price"] == "5000.00"
    assert john_record["created_at"].endswith("Z")

def test_database_writes_roll_back_after_unexpected_failure(
    client,
    db_factory,
    purchase_setup,
):
    before = database_snapshot(
        db_factory,
        purchase_setup["user_id"],
        purchase_setup["product_id"],
    )

    def fail_after_flush(session, flush_context):
        raise RuntimeError("Simulated write failure")

    event.listen(
        db_factory.class_,
        "after_flush",
        fail_after_flush,
    )

    try:
        with pytest.raises(
            RuntimeError,
            match="Simulated write failure",
        ):
            client.post(
                "/api/purchases/",
                headers={"X-Username": "john"},
                json={
                    "product_id": purchase_setup["product_id"],
                    "litres": "10.00",
                },
            )

    finally:
        event.remove(
            db_factory.class_,
            "after_flush",
            fail_after_flush,
        )

    after = database_snapshot(
        db_factory,
        purchase_setup["user_id"],
        purchase_setup["product_id"],
    )

    assert after == before

def test_busy_database_returns_503_without_changes(
    client,
    db_factory,
    purchase_setup,
):
    before = database_snapshot(
        db_factory,
        purchase_setup["user_id"],
        purchase_setup["product_id"],
    )

    with db_factory() as session:
        engine = session.get_bind()

    with engine.connect() as lock_connection:
        lock_connection.exec_driver_sql("BEGIN IMMEDIATE")

        response = client.post(
            "/api/purchases/",
            headers={"X-Username": "john"},
            json={
                "product_id": purchase_setup["product_id"],
                "litres": "10.00",
            },
        )

    assert response.status_code == 503

    assert response.json() == {
        "detail": "Database is busy. Please try again shortly."
    }

    assert response.headers["Retry-After"] == "1"

    after = database_snapshot(
        db_factory,
        purchase_setup["user_id"],
        purchase_setup["product_id"],
    )

    assert after == before