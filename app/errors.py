import logging
import sqlite3

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


def register_error_handlers(app: FastAPI):
    @app.exception_handler(OperationalError)
    async def database_error_handler(
        request: Request,
        exception: OperationalError,
    ):
        error_code = getattr(
            exception.orig,
            "sqlite_errorcode",
            None,
        )

        primary_code = (
            error_code & 0xFF
            if isinstance(error_code, int)
            else None
        )

        if primary_code in (
            sqlite3.SQLITE_BUSY,
            sqlite3.SQLITE_LOCKED,
        ):
            return JSONResponse(
                status_code=503,
                content={
                    "detail": "Database is busy. Please try again shortly."
                },
                headers={"Retry-After": "1"},
            )

        logger.exception("Unexpected database operation failure.")

        return JSONResponse(
            status_code=500,
            content={
                "detail": "An unexpected database error occurred."
            },
        )

def register_http_error_handler(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(
        request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.detail},
            headers=exc.headers,
        )