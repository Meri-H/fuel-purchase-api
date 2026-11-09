import argparse
import secrets

from pydantic import TypeAdapter, ValidationError
from sqlalchemy import select

from app.database import SessionLocal
from app.models import Admin
from app.schemas import Username
from app.security import hash_secret


def main():
    parser = argparse.ArgumentParser(
        description="Create an administrator and generate an API key."
    )

    parser.add_argument("--username", required=True)
    args = parser.parse_args()

    try:
        username = TypeAdapter(Username).validate_python(args.username)
    except ValidationError:
        parser.error(
            "Username must contain 1–50 letters, numbers, "
            "underscores, or hyphens."
        )

    api_key = f"{username}.{secrets.token_urlsafe(32)}"

    with SessionLocal.begin() as session:
        existing_admin = session.scalar(
            select(Admin).where(Admin.username == username)
        )

        if existing_admin is not None:
            parser.error(
                "An administrator with this username already exists."
            )

        session.add(
            Admin(
                username=username,
                api_key_hash=hash_secret(api_key),
            )
        )

    print(f"Administrator '{username}' created.")
    print("Save this API key securely. It is displayed only once:")
    print(api_key)


if __name__ == "__main__":
    main()