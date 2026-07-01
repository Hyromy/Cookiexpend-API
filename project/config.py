from typing import (
    Annotated,
    Any,
)

from pydantic import (
    BeforeValidator,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)


def parse_comma_separated_list(v: Any) -> list[str]:
    if isinstance(v, str):
        if not v.strip():
            return []

        cleaned = v.strip().lstrip("[").rstrip("]")

        return [
            item.strip().replace('"', "").replace("'", "")
            for item in cleaned.split(",")
            if item.strip()
        ]

    if isinstance(v, list):
        return [str(item).strip() for item in v]

    return []


CommaSeparatedList = Annotated[list[str], BeforeValidator(parse_comma_separated_list)]


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,
        env_parse_none_str="null",
    )

    # --- General settings ---
    PRODUCTION: bool = False
    DJANGO_SECRET_KEY: str = Field(default="insecure-secret-key")
    USE_SSL: bool = False

    # --- Network ---
    HOSTS: Any = Field(default=["*"])
    DEFAULT_FRONTEND: str = Field(default="http://localhost:5173")
    CORS_ALLOWED: Any = Field(default=None)
    CSRF_TRUSTED: Any = Field(default=None)
    SESSION_DOMAIN: str | None = Field(default=None)

    # --- Database ---
    DB_NAME: str | None = None
    DB_USER: str | None = None
    DB_PASS: str | None = None
    DB_HOST: str | None = None
    DB_PORT: int | None = None

    # --- Redis ---
    REDIS_URL: str = Field(default="redis://localhost:6379/0")

    # --- Email ---
    USE_EMAIL: bool = False
    EMAIL_HOST: str | None = None
    EMAIL_PORT: int | None = None
    EMAIL_HOST_USER: str | None = None
    EMAIL_HOST_PASSWORD: str | None = None
    EMAIL_DOMAIN: str | None = None
    EMAIL_USERNAME: str | None = None

    @field_validator("DJANGO_SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, value: str, info: ValidationInfo) -> str:
        if info.data.get("PRODUCTION") and len(value) < 64:
            raise ValueError("DJANGO_SECRET_KEY must be at least 64 characters long in production.")
        return value

    @field_validator("REDIS_URL")
    @classmethod
    def validate_redis_url(cls, value: str) -> str:
        if not value.startswith("redis://") and not value.startswith("rediss://"):
            raise ValueError("REDIS_URL must start with 'redis://' or 'rediss://'.")
        return value

    @model_validator(mode="after")
    def validate_production_and_dependencies(self) -> "Config":
        is_prod = self.PRODUCTION
        localhost_triggers = ["localhost", "127.0.0.1"]

        self.HOSTS = parse_comma_separated_list(self.HOSTS or ["*"])
        cors_list = parse_comma_separated_list(self.CORS_ALLOWED)
        csrf_list = parse_comma_separated_list(self.CSRF_TRUSTED)

        raw_cors = [self.DEFAULT_FRONTEND] + cors_list
        raw_csrf = [self.DEFAULT_FRONTEND] + csrf_list

        if is_prod:
            self.CORS_ALLOWED = list(
                set(
                    item
                    for item in raw_cors
                    if not any(trigger in item.lower() for trigger in localhost_triggers)
                )
            )
            self.CSRF_TRUSTED = list(
                set(
                    item
                    for item in raw_csrf
                    if not any(trigger in item.lower() for trigger in localhost_triggers)
                )
            )

            if self.HOSTS:
                self.HOSTS = list(
                    set(
                        item
                        for item in self.HOSTS
                        if not any(trigger in item.lower() for trigger in localhost_triggers)
                    )
                )
        else:
            self.CORS_ALLOWED = list(set(raw_cors))
            self.CSRF_TRUSTED = list(set(raw_csrf))

        if not is_prod and self.SESSION_DOMAIN is None:
            self.SESSION_DOMAIN = "localhost"

        if is_prod:
            fields_to_check_str = {
                "DEFAULT_FRONTEND": self.DEFAULT_FRONTEND,
                "SESSION_DOMAIN": self.SESSION_DOMAIN,
                "DB_HOST": self.DB_HOST,
                "REDIS_URL": self.REDIS_URL,
            }
            for name, val in fields_to_check_str.items():
                if val and any(trigger in val.lower() for trigger in localhost_triggers):
                    raise ValueError(
                        f"Security Error: {name} cannot contain 'localhost' or '127.0.0.1' in production mode."
                    )

            if self.HOSTS:
                if "*" in self.HOSTS:
                    raise ValueError("HOSTS cannot contain '*' wildcard in production.")

        if is_prod:
            db_fields = ["DB_NAME", "DB_USER", "DB_PASS", "DB_HOST", "DB_PORT"]
            for field in db_fields:
                if getattr(self, field) is None:
                    raise ValueError(
                        f"Database configuration field '{field}' is strictly required in production."
                    )

            if self.SESSION_DOMAIN is None:
                raise ValueError(
                    "SESSION_DOMAIN is required in production to handle safe cookies across subdomains."
                )

            if self.SESSION_DOMAIN.startswith("."):
                self.SESSION_DOMAIN = self.SESSION_DOMAIN[1:]

        if self.USE_EMAIL:
            required_email_fields = [
                "EMAIL_HOST",
                "EMAIL_PORT",
                "EMAIL_HOST_USER",
                "EMAIL_HOST_PASSWORD",
                "EMAIL_DOMAIN",
            ]
            for field in required_email_fields:
                if getattr(self, field) is None:
                    raise ValueError(f"Email field '{field}' is required when USE_EMAIL is True.")

        return self

    @property
    def DEFAULT_FROM_EMAIL(self) -> str | None:
        if not self.EMAIL_DOMAIN:
            return None

        if self.EMAIL_USERNAME:
            return f"{self.EMAIL_USERNAME} <no-reply@{self.EMAIL_DOMAIN}>"

        return f"no-reply@{self.EMAIL_DOMAIN}"


config = Config()
