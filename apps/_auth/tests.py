from unittest.mock import patch

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client
from rest_framework.test import APIClient


@pytest.fixture()
def user():
    user_model = get_user_model()
    return user_model.objects.create_user(username="tester", password="pass1234")


@pytest.fixture()
def client():
    return Client()


@pytest.fixture()
def api_client():
    return APIClient()


@pytest.mark.django_db
def test_logout_anonymous(api_client):
    with patch("apps._auth.views.logout"):
        response = api_client.post("/auth/logout/")

    assert response.status_code == 401


@pytest.mark.django_db
def test_logout_authenticated(api_client, user):
    api_client.force_authenticate(user=user)
    with patch("apps._auth.views.logout") as logout_mock:
        response = api_client.post("/auth/logout/")

    assert response.status_code == 200
    assert response.json() == {"success": True, "was_authenticated": True}
    logout_mock.assert_called_once()


@pytest.mark.django_db
def test_token_obtain_pair(api_client, user):
    response = api_client.post(
        "/auth/token/",
        {"username": user.username, "password": "pass1234"},
    )

    assert response.status_code == 200
    assert "access" in response.data
    assert "refresh" in response.data


@pytest.mark.django_db
def test_token_obtain_pair_invalid_password(api_client, user):
    response = api_client.post(
        "/auth/token/",
        {"username": user.username, "password": "wrong"},
    )

    assert response.status_code == 401


@pytest.mark.django_db
def test_token_obtain_pair_missing_fields(api_client):
    response = api_client.post("/auth/token/", {"username": "tester"})

    assert response.status_code == 400


@pytest.mark.django_db
def test_token_obtain_pair_inactive_user(api_client, user):
    user.is_active = False
    user.save(update_fields=["is_active"])

    response = api_client.post(
        "/auth/token/",
        {"username": user.username, "password": "pass1234"},
    )

    assert response.status_code == 401


@pytest.mark.django_db
def test_token_refresh(api_client, user):
    obtain = api_client.post(
        "/auth/token/",
        {"username": user.username, "password": "pass1234"},
    )
    assert obtain.status_code == 200

    refresh_token = obtain.data["refresh"]
    response = api_client.post("/auth/token/refresh/", {"refresh": refresh_token})

    assert response.status_code == 200
    assert "access" in response.data


@pytest.mark.django_db
def test_token_refresh_invalid_token(api_client):
    response = api_client.post("/auth/token/refresh/", {"refresh": "invalid"})

    assert response.status_code == 401


@pytest.mark.django_db
def test_token_refresh_missing_field(api_client):
    response = api_client.post("/auth/token/refresh/", {})

    assert response.status_code == 400


@pytest.mark.django_db
def test_logout_get_not_allowed(api_client, user):
    api_client.force_authenticate(user=user)
    response = api_client.get("/auth/logout/")

    assert response.status_code == 405


@pytest.mark.django_db
def test_login_session_allows_me_with_same_client(api_client):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="sessionuser",
        email="session@example.com",
        password="pass1234",
    )

    login_response = api_client.post(
        "/auth/login/",
        {"email": user.email, "password": "pass1234"},
        format="json",
    )
    assert login_response.status_code == 200
    assert login_response.data["success"] is True

    me_response = api_client.get("/auth/me/")
    assert me_response.status_code == 200
    assert me_response.data["id"] == user.id


def test_local_cookie_defaults_are_browser_compatible():
    # Browsers reject SameSite=None when Secure is false.
    assert settings.SESSION_COOKIE_SAMESITE == settings.CSRF_COOKIE_SAMESITE
    assert settings.SESSION_COOKIE_SECURE == settings.CSRF_COOKIE_SECURE

    if settings.SESSION_COOKIE_SAMESITE == "None":
        assert settings.SESSION_COOKIE_SECURE is True
    else:
        assert settings.SESSION_COOKIE_SAMESITE == "Lax"
