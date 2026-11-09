from typing import Annotated

from fastapi import Header, HTTPException, Security, status
from fastapi.security import (
    APIKeyHeader,
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from sqlalchemy import select
from datetime import UTC, datetime, timedelta
from dataclasses import dataclass
import jwt
from sqlalchemy.orm import Session
from app.config import get_settings
from app.database import SessionLocal
from app.models import Admin, User
import hashlib
import hmac
import secrets


HASH_ITERATIONS = 600_000


def hash_secret(secret: str) -> str:
    salt = secrets.token_bytes(16)

    digest = hashlib.pbkdf2_hmac(
        "sha256",
        secret.encode("utf-8"),
        salt,
        HASH_ITERATIONS,
    )

    return (
        f"pbkdf2_sha256${HASH_ITERATIONS}"
        f"${salt.hex()}${digest.hex()}"
    )


def verify_secret(secret: str, stored_hash: str | None) -> bool:
    if not stored_hash:
        return False

    try:
        algorithm, iterations, salt_hex, digest_hex = stored_hash.split("$")

        if algorithm != "pbkdf2_sha256":
            return False

        if int(iterations) != HASH_ITERATIONS:
            return False

        salt = bytes.fromhex(salt_hex)
        expected_digest = bytes.fromhex(digest_hex)

        if len(salt) != 16 or len(expected_digest) != 32:
            return False

    except ValueError:
        return False

    actual_digest = hashlib.pbkdf2_hmac(
        "sha256",
        secret.encode("utf-8"),
        salt,
        HASH_ITERATIONS,
    )

    return hmac.compare_digest(actual_digest, expected_digest)

admin_key_header = APIKeyHeader(
    name="X-Admin-Key",
    auto_error=False,
)

dummy_key_hash = hash_secret("dummy-value-for-verification")


def require_admin(
    api_key: Annotated[str | None, Security(admin_key_header)],
) -> int:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing or invalid administrator API key.",
        headers={"WWW-Authenticate": "ApiKey"},
    )

    if not api_key or len(api_key) > 200:
        raise unauthorized

    username, separator, secret_part = api_key.partition(".")

    if not separator or not secret_part:
        raise unauthorized

    with SessionLocal() as session:
        admin = session.scalar(
            select(Admin).where(Admin.username == username)
        )

    stored_hash = admin.api_key_hash if admin else dummy_key_hash
    key_is_valid = verify_secret(api_key, stored_hash)

    if not key_is_valid or admin is None:
        raise unauthorized

    return admin.id

TOKEN_ALGORITHM = "HS256"
TOKEN_ISSUER = "fuel-purchase-api"
TOKEN_AUDIENCE = "fuel-users"


def create_access_token(
    user_id: int,
    auth_version: int,
) -> str:
    settings = get_settings()
    now = datetime.now(UTC)

    return jwt.encode(
        {
            "sub": str(user_id),
            "ver": auth_version,
            "iat": now,
            "nbf": now,
            "exp": now + timedelta(
                minutes=settings.access_token_minutes
            ),
            "iss": TOKEN_ISSUER,
            "aud": TOKEN_AUDIENCE,
        },
        settings.jwt_secret.get_secret_value(),
        algorithm=TOKEN_ALGORITHM,
    )


def decode_access_token(token: str) -> dict:
    settings = get_settings()

    return jwt.decode(
        token,
        settings.jwt_secret.get_secret_value(),
        algorithms=[TOKEN_ALGORITHM],
        issuer=TOKEN_ISSUER,
        audience=TOKEN_AUDIENCE,
        options={
            "require": [
                "sub",
                "ver",
                "iat",
                "nbf",
                "exp",
                "iss",
                "aud",
            ],
        },
    )

user_bearer = HTTPBearer(
    scheme_name="UserToken",
    auto_error=False,
)


@dataclass(frozen=True)
class UserIdentity:
    username: str | None = None
    user_id: int | None = None
    auth_version: int | None = None


def token_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing, invalid, or expired access token.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_user_identity(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Security(user_bearer),
    ],
    username: Annotated[
        str | None,
        Header(alias="X-Username", max_length=50),
    ] = None,
) -> UserIdentity:
    settings = get_settings()

    if settings.user_auth_mode == "basic":
        if not username or not username.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="X-Username header is required.",
            )

        return UserIdentity(username=username)

    if credentials is None:
        raise token_error()

    if len(credentials.credentials) > 4096:
        raise token_error()

    try:
        claims = decode_access_token(
            credentials.credentials
        )

        user_id = int(claims["sub"])
        version = claims["ver"]

        if not 0 < user_id <= 9_223_372_036_854_775_807:
            raise ValueError("Invalid user ID.")

        if type(version) is not int or version < 0:
            raise ValueError("Invalid authentication version.")

    except (jwt.InvalidTokenError, ValueError, TypeError):
        raise token_error() from None

    return UserIdentity(
        user_id=user_id,
        auth_version=version,
    )


def resolve_user(
    db: Session,
    identity: UserIdentity,
) -> User:
    if identity.user_id is None:
        user = db.scalar(
            select(User).where(
                User.username == identity.username
            )
        )

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User does not exist.",
            )

        return user

    user = db.get(User, identity.user_id)

    if (
        user is None
        or user.auth_version != identity.auth_version
    ):
        raise token_error()

    return user