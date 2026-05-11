from unittest.mock import patch

import pytest
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
def test_logout_anonymous(client):
    with patch("apps._auth.views.logout") as logout_mock:
        response = client.post("/auth/logout/")

    assert response.status_code == 200
    assert response.json() == {"success": True, "was_authenticated": False}
    logout_mock.assert_called_once()


@pytest.mark.django_db
def test_logout_authenticated(client, user):
    assert client.login(username=user.username, password="pass1234")
    with patch("apps._auth.views.logout") as logout_mock:
        response = client.post("/auth/logout/")

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
def test_logout_get_not_allowed(client):
    response = client.get("/auth/logout/")

    assert response.status_code in {400, 405}
