from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    jwt_secret: SecretStr

    access_token_minutes: int = Field(
        default=30,
        ge=1,
        le=1440,
    )

    user_auth_mode: Literal["basic", "token"] = "basic"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("jwt_secret")
    @classmethod
    def validate_jwt_secret(cls, value: SecretStr) -> SecretStr:
        secret = value.get_secret_value()

        if len(secret) < 32 or secret.startswith("replace-with-"):
            raise ValueError(
                "Generate a random JWT_SECRET of at least 32 characters."
            )

        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()