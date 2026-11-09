from decimal import Decimal

from sqlalchemy import BigInteger
from sqlalchemy.types import TypeDecorator


class FixedDecimal(TypeDecorator):
    """Store a two-decimal Decimal value as an exact integer."""

    impl = BigInteger
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None

        if not isinstance(value, Decimal):
            raise TypeError("Use Decimal for monetary values and quantities.")

        if not value.is_finite():
            raise ValueError("The value must be a finite number.")

        if abs(value) > Decimal("9999999999999999.99"):
            raise ValueError("The value is too large.")

        scaled_value = value * 100

        if scaled_value != scaled_value.to_integral_value():
            raise ValueError("Use at most two decimal places.")

        return int(scaled_value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None

        return Decimal(value).scaleb(-2)