# Fuel Purchase API

A FastAPI application for purchasing fuel using a customer’s account balance.

Administrators manage products, stock, user accounts, and balances. Users purchase fuel and retrieve their purchase history.

## Technologies

- Python 3.13
- FastAPI and Pydantic
- SQLAlchemy and SQLite
- Alembic migrations
- PyJWT for optional user authentication
- pytest and FastAPI TestClient
- Docker and Docker Compose

## Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/admin/products/` | Create a product |
| PATCH | `/api/admin/products/{product_id}/` | Update a product |
| POST | `/api/admin/users/` | Create a user |
| PATCH | `/api/admin/users/{user_id}/` | Update a user |
| POST | `/api/purchases/` | Purchase fuel |
| GET | `/api/purchases/` | Retrieve the identified user's purchases |
| POST | `/api/auth/token/` | Optional password login and token issuance |
| GET | `/health/` | Check that the API responds |

Interactive documentation is available at:

http://127.0.0.1:8000/docs

## Configuration

Copy `.env.example` to `.env`.

In Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

On Linux or macOS:

```bash
cp .env.example .env
```

Generate a signing secret:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

If Python is not installed locally, Docker can generate it:

```powershell
docker run --rm python:3.13-slim python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Set the generated value in `.env`:

```dotenv
DATABASE_URL=sqlite:///./fuel.db
JWT_SECRET=your-generated-secret
ACCESS_TOKEN_MINUTES=30
USER_AUTH_MODE=token
```

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | SQLAlchemy database URL |
| `JWT_SECRET` | Random signing secret of at least 32 characters |
| `ACCESS_TOKEN_MINUTES` | Token lifetime; defaults to 30 minutes |
| `USER_AUTH_MODE` | `basic` or `token`; defaults to `basic` if omitted |

The example JWT placeholder must be replaced before running the application.

Do not commit `.env`, API keys, tokens, or local database files.

## Run locally

Run all commands from the project root.

Create a virtual environment:

```powershell
python -m venv .venv
```

Activate it on Windows:

```powershell
.\.venv\Scripts\Activate.ps1
```

On Linux or macOS:

```bash
source .venv/bin/activate
```

Install dependencies and create the database tables:

```powershell
python -m pip install -r requirements.txt
python -m alembic upgrade head
```

Create an administrator:

```powershell
python -m app.scripts.create_admin --username admin
```

Save the displayed API key securely. Only its hash is stored in the database.

Start the API:

```powershell
python -m uvicorn app.main:app --reload
```

The local SQLite database is stored in `fuel.db`.

## Run with Docker

Docker Desktop or Docker Engine with Docker Compose must be running.

Configure `.env` as described above, then run:

```powershell
docker compose up --build -d
docker compose ps
```

The container applies migrations before starting the API.

Create an administrator in the Docker database:

```powershell
docker compose exec api python -m app.scripts.create_admin --username admin
```

This setup is required once per new database. Existing administrator accounts survive container recreation.

Open:

http://127.0.0.1:8000/docs

View logs:

```powershell
docker compose logs --tail=100 api
```

Stop the application:

```powershell
docker compose down
```

Docker stores SQLite data in the `sqlite_data` named volume at `/app/data/fuel.db`.

The container overrides `DATABASE_URL` to use this path. Its database is separate from the local project's `fuel.db`.

A new developer starts with empty tables and creates their own administrator and test records.

`docker compose down` preserves the volume. Adding `-v` deletes the project's named volumes and their stored data.

Stop local Uvicorn before running Docker if both would use port 8000.

## Administrator authentication

Management endpoints require:

```http
X-Admin-Key: <administrator-api-key>
```

The setup script generates a key in this format:

```text
username.random-secret
```

The complete key is verified against the stored hash.

Administrator keys and user passwords are hashed using PBKDF2-HMAC-SHA256 with a random salt and 600,000 iterations.

Regular user tokens do not grant administrator access.

## User authentication modes

### Basic mode

Set:

```dotenv
USER_AUTH_MODE=basic
```

Purchase and history requests identify the user through:

```http
X-Username: john
```

This is the assessment's simplified identification method. It does not prove ownership of the account.

### Token mode

Set:

```dotenv
USER_AUTH_MODE=token
```

Log in using:

```http
POST /api/auth/token/
Content-Type: application/x-www-form-urlencoded

username=john&password=Learning-password-123!
```

A successful response contains:

```json
{
  "access_token": "<signed-token>",
  "token_type": "bearer",
  "expires_in": 1800
}
```

Send the token on purchase and history requests:

```http
Authorization: Bearer <signed-token>
```

In token mode:

- The verified token determines the user.
- `X-Username` does not select another account.
- Expired, invalid, or revoked tokens return `401`.
- Password updates invalidate older tokens by increasing `auth_version`.

Restart local Uvicorn after changing `.env`.

For Docker, recreate the service to load changed environment settings:

```powershell
docker compose up -d --force-recreate api
```

## Try the application

Use `/docs` to perform the following steps.

### 1. Authorize as an administrator

Click **Authorize** and enter the complete administrator API key in the API-key entry.
Swagger UI preserves authorization across page refreshes in the same browser. Expired user tokens must be replaced by logging in again. Clear saved authorization when switching between local and Docker environments, because they use separate databases.
### 2. Create a product

Call `POST /api/admin/products/`:

```json
{
  "name": "Petrol 95",
  "price_per_litre": "500.00",
  "available_litres": "1000.00"
}
```

Save the returned product ID.

### 3. Create a user

Call `POST /api/admin/users/`:

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

The password is optional during account creation. A user needs a password before using token login.

### 4. Identify the user

In token mode, call `/api/auth/token/` and copy the returned token.

Click **Authorize** and paste it into **UserToken**, without adding the `Bearer` prefix.

In basic mode, enter `john` in the purchase endpoint's `X-Username` field.

### 5. Purchase fuel

Call `POST /api/purchases/` using the actual product ID:

```json
{
  "product_id": 1,
  "litres": "10.00"
}
```

For the example values, the total is `5000.00`, the remaining balance is `5000.00`, and remaining stock is `990.00`.

### 6. Retrieve history

Call `GET /api/purchases/` using the same user identification.

Only that user's purchases are returned.

### 7. Update records

PATCH requests accept only the fields being changed.

Example product update:

```json
{
  "price_per_litre": "550.00"
}
```

Example user update:

```json
{
  "account_balance": "15000.00"
}
```

A balance update replaces the balance; it does not add the submitted amount.

Empty PATCH requests and explicit null values are rejected.

## Purchase consistency and decimal handling

Prices, quantities, and balances use Python `Decimal`.

A custom SQLAlchemy type stores two-decimal values as scaled integers in SQLite. For example, `500.25` is stored as `50025`, preserving its exact value.

Send decimal amounts as strings in JSON requests.

- Inputs allow at most two decimal places.
- Prices and stock must be nonnegative.
- Product prices and quantities are limited to `99999999.99`.
- Account balances are limited to `9999999999999999.99`.
- Purchased litres must be greater than zero.
- Totals are rounded once to two decimal places using `ROUND_HALF_UP`.

A purchase acquires SQLite write access with `BEGIN IMMEDIATE` before checking the user, balance, and stock.

Balance deduction, stock deduction, and purchase insertion occur in one transaction. A failed transaction rolls back its changes.

Purchases store snapshots of the product name and price so later product edits do not rewrite historical purchases.

Purchase timestamps are returned in UTC.

## Error responses

| Status | Meaning |
|---|---|
| `400` | Missing basic username, insufficient balance, or insufficient stock |
| `401` | Missing or invalid credentials |
| `404` | User or product does not exist |
| `409` | Username already exists |
| `422` | Invalid request data |
| `503` | SQLite is busy or locked |

A busy-database response includes `Retry-After: 1`.

## Run tests

With the local virtual environment activated:

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q tests
```

Uvicorn does not need to be running.

The tests use temporary SQLite databases and do not modify the development database.

Coverage includes:

- Successful purchases and stored results.
- Failed-purchase rollback.
- Validation and history isolation.
- Administrator permissions and user management.
- Simultaneous purchases competing for balance or stock.
- Unexpected write failures and database locks.
- Fresh database migrations.
- Token authentication and password-reset invalidation.

## Assumptions and limitations

- No frontend or public self-registration is included.
- Administrators create users and manage balances.
- Basic mode follows the assessment's simplified username-header approach.
- SQLite allows one writer at a time and is intended here for a small assessment application.
- Docker runs one API container, with migrations applied at startup.
- Access tokens expire; refresh tokens and a logout endpoint are not implemented.
- Password resets invalidate previously issued user tokens.
- `/health/` checks that the API responds; it is not a database connectivity check.