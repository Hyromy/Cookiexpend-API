from pydantic import (
    Field,
    ValidationInfo,
    field_validator,
)
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,
        env_parse_none_str="null",
    )

    PRODUCTION: bool = False
    DJANGO_SECRET_KEY: str = Field(default="insecure-secret-key")
    USE_SSL: bool = False

    HOSTS: str = Field(default="*")
    CORS_ALLOWED: str = Field(default="")
    CSRF_TRUSTED: str = Field(default="")
    SESSION_DOMAIN: str | None = None

    DB_NAME: str | None = None
    DB_USER: str | None = None
    DB_PASS: str | None = None
    DB_HOST: str | None = None
    DB_PORT: str | None = None

    REDIS_URL: str = Field(default="redis://localhost:6379/0")

    @field_validator("DJANGO_SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, value: str, info: ValidationInfo) -> str:
        if not info.data.get("PRODUCTION"):
            return value

        if len(value) < 64:
            raise ValueError("DJANGO_SECRET_KEY must be at least 64 characters long in production.")

        return value

    @staticmethod
    def _parse_list(value: str) -> list[str]:
        cleaned = value.strip()
        if cleaned.startswith("[") and cleaned.endswith("]"):
            cleaned = cleaned[1:-1]
        cleaned = cleaned.replace('"', "").replace("'", "")

        return [h.strip() for h in cleaned.split(",") if h.strip()]

    @field_validator("HOSTS", "CORS_ALLOWED", "CSRF_TRUSTED")
    @classmethod
    def validate_hosts(cls, value: str, info: ValidationInfo) -> str:
        parsed = cls._parse_list(value)
        if info.data.get("PRODUCTION") and info.field_name == "HOSTS":
            if not parsed or "*" in parsed:
                raise ValueError("HOSTS cannot be empty or contain '*' in production.")

        return value

    @property
    def HOSTS_LIST(self) -> list[str]:
        return self._parse_list(self.HOSTS)

    @property
    def CORS_ALLOWED_LIST(self) -> list[str]:
        return self._parse_list(self.CORS_ALLOWED)

    @property
    def CSRF_TRUSTED_LIST(self) -> list[str]:
        return self._parse_list(self.CSRF_TRUSTED)

    @field_validator("SESSION_DOMAIN")
    @classmethod
    def validate_session_domain(cls, value: str | None, info: ValidationInfo) -> str | None:
        if info.data.get("PRODUCTION"):
            if value is None:
                raise ValueError("SESSION_DOMAIN must be set in production.")

            if value.startswith("."):
                return value[1:]

        return value

    @field_validator("DB_NAME", "DB_USER", "DB_PASS", "DB_HOST", "DB_PORT")
    @classmethod
    def validate_database_fields(cls, value: str | None, info: ValidationInfo) -> str | None:
        if info.data.get("PRODUCTION") and value is None:
            raise ValueError(f"{info.field_name} must be set in production.")

        return value

    @field_validator("REDIS_URL")
    @classmethod
    def validate_redis_url(cls, value: str, info: ValidationInfo) -> str:
        if not value.startswith("redis://"):
            raise ValueError("REDIS_URL must start with 'redis://' in production.")

        if info.data.get("PRODUCTION") and "localhost" in value:
            raise ValueError("REDIS_URL cannot point to localhost in production.")

        return value


config = Config()
