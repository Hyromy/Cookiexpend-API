import pytest
from pydantic import ValidationError

from .config import Config


def _base_production_kwargs():
    return {
        "PRODUCTION": True,
        "DJANGO_SECRET_KEY": "x" * 64,
        "USE_SSL": True,
        "HOSTS": "example.com",
        "CORS_ALLOWED": "https://example.com",
        "CSRF_TRUSTED": "https://example.com",
        "SESSION_DOMAIN": "example.com",
        "DB_NAME": "db",
        "DB_USER": "user",
        "DB_PASS": "pass",
        "DB_HOST": "host",
        "DB_PORT": "5432",
        "REDIS_URL": "redis://example.com:6379/0",
    }


def test_defaults_non_production():
    config = Config()

    assert config.PRODUCTION is False
    assert config.DJANGO_SECRET_KEY == "insecure-secret-key"
    assert len(config.HOSTS) >= 1
    assert config.REDIS_URL == "redis://localhost:6379/0"


def test_parse_list_fields_from_string():
    config = Config(
        HOSTS="a.com, b.com",
        CORS_ALLOWED="https://a.com, https://b.com",
        CSRF_TRUSTED="https://a.com",
    )

    assert set(["a.com", "b.com"]).issubset(set(config.HOSTS))
    assert set(["https://a.com", "https://b.com"]).issubset(set(config.CORS_ALLOWED))
    assert set(["https://a.com"]).issubset(set(config.CSRF_TRUSTED))


def test_secret_key_min_length_in_production():
    kwargs = _base_production_kwargs()
    kwargs["DJANGO_SECRET_KEY"] = "short"

    with pytest.raises(ValidationError):
        Config(**kwargs)


def test_hosts_cannot_be_wildcard_in_production():
    kwargs = _base_production_kwargs()
    kwargs["HOSTS"] = "*"

    with pytest.raises(ValidationError):
        Config(**kwargs)


def test_session_domain_required_in_production():
    kwargs = _base_production_kwargs()
    kwargs["SESSION_DOMAIN"] = None

    with pytest.raises(ValidationError):
        Config(**kwargs)


def test_session_domain_strips_leading_dot():
    kwargs = _base_production_kwargs()
    kwargs["SESSION_DOMAIN"] = ".example.com"
    kwargs["DEFAULT_FRONTEND"] = "https://example.com"

    config = Config(**kwargs)

    assert config.SESSION_DOMAIN == "example.com"


def test_database_fields_required_in_production():
    kwargs = _base_production_kwargs()
    kwargs["DB_PASS"] = None

    with pytest.raises(ValidationError):
        Config(**kwargs)


def test_redis_url_scheme_required():
    with pytest.raises(ValidationError):
        Config(REDIS_URL="http://localhost:6379/0")


def test_redis_url_cannot_be_localhost_in_production():
    kwargs = _base_production_kwargs()
    kwargs["REDIS_URL"] = "redis://localhost:6379/0"

    with pytest.raises(ValidationError):
        Config(**kwargs)
