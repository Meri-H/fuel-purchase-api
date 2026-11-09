from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Barrier

import pytest
from sqlalchemy import event, func, select

from app.models import Product, Purchase, User


@pytest.mark.parametrize(
    "shared_resource",
    ["balance", "stock"],
)
def test_simultaneous_purchases(
    client,
    db_factory,
    purchase_setup,
    shared_resource,
):
    user_id = purchase_setup["user_id"]
    product_id = purchase_setup["product_id"]

    second_username = "john"

    with db_factory.begin() as session:
        user = session.get(User, user_id)
        product = session.get(Product, product_id)

        if shared_resource == "balance":
            user.account_balance = Decimal("5000.00")
            product.available_litres = Decimal("100.00")

        else:
            user.account_balance = Decimal("10000.00")
            product.available_litres = Decimal("10.00")

            session.add(
                User(
                    first_name="Mary",
                    last_name="Jones",
                    username="mary",
                    birthdate=date(2001, 5, 10),
                    account_balance=Decimal("10000.00"),
                )
            )

            second_username = "mary"

    barrier = Barrier(2)

    with db_factory() as session:
        engine = session.get_bind()

    def synchronize_requests(
        connection,
        cursor,
        statement,
        parameters,
        context,
        executemany,
    ):
        if statement.strip().upper() == "BEGIN IMMEDIATE":
            barrier.wait(timeout=10)

    def buy(username):
        return client.post(
            "/api/purchases/",
            headers={"X-Username": username},
            json={
                "product_id": product_id,
                "litres": "10.00",
            },
        )

    event.listen(
        engine,
        "before_cursor_execute",
        synchronize_requests,
    )

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(buy, "john")
            second = executor.submit(buy, second_username)

            responses = [
                first.result(timeout=30),
                second.result(timeout=30),
            ]

    finally:
        event.remove(
            engine,
            "before_cursor_execute",
            synchronize_requests,
        )

    assert sorted(
        response.status_code for response in responses
    ) == [201, 400]

    failed_response = next(
        response
        for response in responses
        if response.status_code == 400
    )

    if shared_resource == "balance":
        expected_error = "Insufficient balance."
        expected_stock = Decimal("90.00")
        expected_total_balance = Decimal("0.00")

    else:
        expected_error = "Not enough fuel available."
        expected_stock = Decimal("0.00")
        expected_total_balance = Decimal("15000.00")

    assert failed_response.json()["error"] == expected_error

    with db_factory() as session:
        product = session.get(Product, product_id)

        balances = session.scalars(
            select(User.account_balance)
        ).all()

        purchase_count = session.scalar(
            select(func.count()).select_from(Purchase)
        )

        assert purchase_count == 1
        assert product.available_litres == expected_stock

        assert all(balance >= 0 for balance in balances)

        assert sum(
            balances,
            Decimal("0.00"),
        ) == expected_total_balance