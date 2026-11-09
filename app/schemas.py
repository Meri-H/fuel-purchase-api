from decimal import Decimal
from typing import Annotated, Literal
from datetime import UTC, date, datetime
from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    PlainSerializer,
    StringConstraints,
    model_validator,
    AfterValidator,
    AliasChoices,
    field_validator,
    SecretStr
)


def reject_boolean(value):
    if isinstance(value, bool):
        raise ValueError("A boolean is not a valid decimal value.")

    return value


DecimalValue = Annotated[
    Decimal,
    BeforeValidator(reject_boolean),
    Field(
        max_digits=18,
        decimal_places=2,
        allow_inf_nan=False,
    ),
    PlainSerializer(
        lambda value: "0.00" if value == 0 else format(value, ".2f"),
        return_type=str,
        when_used="json",
    ),
]

Username = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=50,
        pattern=r"^[A-Za-z0-9_-]+$",
    ),
]


Balance = Annotated[
    DecimalValue,
    Field(
        ge=Decimal("0.00"),
        le=Decimal("9999999999999999.99"),
    ),
]


Password = Annotated[
    SecretStr,
    Field(
        min_length=12,
        max_length=128,
    ),
]


def validate_birthdate(value: date) -> date:
    if value > date.today():
        raise ValueError("Birthdate cannot be in the future.")

    return value


Birthdate = Annotated[
    date,
    AfterValidator(validate_birthdate),
]

ProductAmount = Annotated[
    DecimalValue,
    Field(
        ge=Decimal("0.00"),
        le=Decimal("99999999.99"),
    ),
]


Name = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=100,
    ),
]


class BaseSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
    )


class ProductCreate(BaseSchema):
    name: Name
    price_per_litre: ProductAmount
    available_litres: ProductAmount


class ProductRead(ProductCreate):
    id: int

class BaseUpdateSchema(BaseSchema):
    @model_validator(mode="before")
    @classmethod
    def validate_changes(cls, data):
        if isinstance(data, dict):
            if not data:
                raise ValueError("Provide at least one field to update.")

            if any(value is None for value in data.values()):
                raise ValueError("Updated fields cannot be null.")

        return data


class ProductUpdate(BaseUpdateSchema):
    name: Name | None = None
    price_per_litre: ProductAmount | None = None
    available_litres: ProductAmount | None = None

class UserCreate(BaseSchema):
    first_name: Name
    last_name: Name
    username: Username
    birthdate: Birthdate
    account_balance: Balance = Decimal("0.00")
    password: Password | None = None


class UserUpdate(BaseUpdateSchema):
    first_name: Name | None = None
    last_name: Name | None = None
    username: Username | None = None
    birthdate: Birthdate | None = None
    account_balance: Balance | None = None
    password: Password | None = None


class UserRead(BaseSchema):
    id: int
    first_name: Name
    last_name: Name
    username: Username
    birthdate: date
    account_balance: Balance

class PurchaseCreate(BaseSchema):
    product_id: Annotated[
        int,
        Field(strict=True, gt=0),
    ]

    litres: Annotated[
        ProductAmount,
        Field(gt=Decimal("0.00")),
    ]


class PurchaseRead(BaseSchema):
    id: int

    product: str = Field(
        validation_alias=AliasChoices("product", "product_name"),
    )

    litres: DecimalValue
    total_price: DecimalValue
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def ensure_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)

        return value.astimezone(UTC)


class PurchaseCreated(PurchaseRead):
    remaining_balance: Balance
    remaining_stock_litres: ProductAmount

class TokenResponse(BaseSchema):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
