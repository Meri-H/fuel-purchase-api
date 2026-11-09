import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run_alembic(database_url, *arguments):
    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            *arguments,
        ],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0, (
        result.stdout + "\n" + result.stderr
    )


def test_migrations_create_a_fresh_database(tmp_path):
    database_file = tmp_path / "migration_test.db"
    database_url = f"sqlite:///{database_file.as_posix()}"

    assert not database_file.exists()

    run_alembic(database_url, "upgrade", "head")

    assert database_file.exists()

    # Applying the latest migrations again should succeed.
    run_alembic(database_url, "upgrade", "head")

    # Check for model changes missing from the migrations.
    run_alembic(database_url, "check")

    engine = create_engine(database_url)

    try:
        with engine.connect() as connection:
            inspector = inspect(connection)

            assert set(inspector.get_table_names()) == {
                "alembic_version",
                "products",
                "users",
                "admins",
                "purchases",
            }

            foreign_keys = inspector.get_foreign_keys(
                "purchases"
            )

            referenced_tables = {
                foreign_key["referred_table"]
                for foreign_key in foreign_keys
            }

            assert referenced_tables == {
                "users",
                "products",
            }

    finally:
        engine.dispose()