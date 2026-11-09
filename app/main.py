from fastapi import FastAPI

from app.routers.admin import router as admin_router
from app.routers.purchases import router as purchases_router
from app.errors import register_error_handlers
from app.routers.auth import router as auth_router
from app.errors import register_http_error_handler


app = FastAPI(
    title="Fuel Purchase API",
    swagger_ui_parameters={
        "persistAuthorization": True,
    },
)
register_error_handlers(app)
register_http_error_handler(app)

app.include_router(admin_router)
app.include_router(purchases_router)
app.include_router(auth_router)

@app.get("/health/")
def health_check():
    return {"status": "ok"}