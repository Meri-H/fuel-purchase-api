# Fuel Purchase API

FastAPI backend for purchasing fuel using an account balance. Administrators manage products, stock, users and balances; users purchase fuel and view their own history.

**Stack:** Python 3.13, FastAPI, Pydantic, SQLAlchemy, SQLite, Alembic, PyJWT and pytest. Docker support is included.

## Configuration

Run commands from the project root. Copy `.env.example` to `.env`:

```powershell
Copy-Item .env.example .env
```

On Linux/macOS, use `cp .env.example .env`.

Generate a JWT signing secret:

```shell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Without local Python, use:

```shell
docker run --rm python:3.13-slim python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Configure `.env`, replacing the secret placeholder:

```dotenv
DATABASE_URL=sqlite:///./fuel.db
JWT_SECRET=<generated-secret-at-least-32-characters>
ACCESS_TOKEN_MINUTES=30
USER_AUTH_MODE=token
```

Do not commit `.env`, real credentials or database files.

## Run locally

Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

On Linux/macOS, activate with `source .venv/bin/activate`.

Install dependencies, apply migrations, create an administrator and start:

```shell
python -m pip install -r requirements.txt
python -m alembic upgrade head
python -m app.scripts.create_admin --username admin
python -m uvicorn app.main:app --reload
```

Save the administrator API key printed by the setup command; only its hash is stored. Administrator creation is required once per new database.

Swagger: http://127.0.0.1:8000/docs

## Run with Docker

With Docker running and `.env` configured:

```shell
docker compose up --build -d
docker compose ps
docker compose exec api python -m app.scripts.create_admin --username admin
```

Migrations run automatically at startup. Open the same Swagger URL above.

Docker stores its separate database at `/app/data/fuel.db` in the `sqlite_data` volume. A new installation starts with empty tables and needs its own administrator.

```shell
docker compose logs --tail 100 api
docker compose down
```

Stopping preserves data; `docker compose down -v` deletes the named volume and its data. Stop local Uvicorn before starting Docker on the same port.

## Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/admin/products/` | Create product |
| PATCH | `/api/admin/products/{product_id}/` | Update product, price or stock |
| POST | `/api/admin/users/` | Create user |
| PATCH | `/api/admin/users/{user_id}/` | Update user or balance |
| POST | `/api/purchases/` | Purchase fuel |
| GET | `/api/purchases/` | View identified user's history |
| POST | `/api/auth/token/` | Log in and obtain a user token |
| GET | `/health/` | Check API availability |

## Authentication

Administrator endpoints always require `X-Admin-Key: <complete-api-key>`. User tokens do not grant administrator access.

User identification is selected through `USER_AUTH_MODE`:

- **`basic`:** send `X-Username: john`. This follows the assessment's simplified identification method and does not verify account ownership.
- **`token`:** log in at `POST /api/auth/token/` using form fields `username` and `password`, then send `Authorization: Bearer <token>`. `X-Username` is ignored.

Passwords are optional when creating users, but required for token login. Password length is 12–128 characters. Password changes invalidate previously issued tokens.

In Swagger, click **Authorize** to enter the administrator key or user token. Paste the user token without adding `Bearer`. Authorization persists across page refreshes; expired tokens require another login. Clear saved credentials when switching between local and Docker databases.

Restart local Uvicorn after changing `.env`. For Docker, run:

```shell
docker compose up -d --force-recreate api
```

## Example workflow

In Swagger, authorize as an administrator and create a product:

```json
{
  "name": "Petrol 95",
  "price_per_litre": "500.00",
  "available_litres": "1000.00"
}
```

Create a user using an example password for demonstration:

```json
{
  "first_name": "John",
  "last_name": "Smith",
  "username": "john",
  "birthdate": "2000-01-01",
  "account_balance": "10000.00",
  "password": "Learning-password-123!"
}
```

Log in as `john` and authorize with the returned token, or supply `X-Username` in basic mode. Purchase using the actual product ID:

```json
{
  "product_id": 1,
  "litres": "10.00"
}
```

Expected: `201`, total `5000.00`, remaining balance `5000.00` and remaining stock `990.00`. Retrieve the purchase using `GET /api/purchases/`.

PATCH requests contain only changed fields. Updating `account_balance` replaces the balance rather than adding to it.

## Tests

With the local virtual environment activated:

```shell
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Tests use temporary databases; no running server is needed. They cover purchases, rollback, validation, permissions, history isolation, concurrency, migrations and token authentication.

## Design notes and limitations

- Python `Decimal` values are stored as exact scaled integers in SQLite. Send amounts as JSON strings with at most two decimal places; totals use `ROUND_HALF_UP`.
- Purchases update balance, stock and history in one transaction. `BEGIN IMMEDIATE` serializes competing SQLite writes; failed transactions roll back.
- History preserves product name and price snapshots; timestamps are returned in UTC.
- Invalid requests return appropriate `400`, `401`, `404`, `409` or `422` responses. Database contention returns `503` with `Retry-After: 1`.
- Administrators create users; no frontend or public registration is included.
- SQLite supports one writer at a time. Docker runs one API container.
- Refresh tokens and an API logout endpoint are not implemented.
- `/health/` checks API availability, not database connectivity.