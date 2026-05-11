from unittest.mock import patch

import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory
from rest_framework.test import APIClient

from .admin import ProductAdmin
from .gossiper import event_name, publish_handler, redis_payload
from .models import Product
from .serializers import ProductSerializer


@pytest.fixture()
def user():
    user_model = get_user_model()
    return user_model.objects.create_user(username="tester", password="pass1234")


@pytest.fixture()
def api_client():
    return APIClient()


@pytest.fixture()
def auth_client(api_client, user):
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture()
def jwt_client(user):
    client = APIClient()
    response = client.post(
        "/auth/token/",
        {"username": user.username, "password": "pass1234"},
    )
    assert response.status_code == 200
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
    return client


@pytest.fixture()
def product(db):
    return Product.objects.create(name="cookie", description="choco", price="5.00")


@pytest.fixture()
def admin_user(db):
    user_model = get_user_model()
    return user_model.objects.create_superuser(
        username="admin",
        email="admin@example.com",
        password="pass1234",
    )


@pytest.fixture()
def rf():
    return RequestFactory()


@pytest.fixture()
def admin_site():
    return AdminSite()


@pytest.fixture()
def product_admin(admin_site):
    return ProductAdmin(Product, admin_site)


@pytest.fixture()
def admin_request(rf, admin_user):
    request = rf.get("/admin/api/product/")
    request.user = admin_user
    SessionMiddleware(lambda r: None).process_request(request)
    request.session.save()
    request._messages = FallbackStorage(request)
    return request


def _admin_post_request(rf, admin_user, path, data):
    request = rf.post(path, data)
    request.user = admin_user
    SessionMiddleware(lambda r: None).process_request(request)
    request.session.save()
    request._messages = FallbackStorage(request)
    return request


class TestApiViews:
    @pytest.mark.django_db
    def test_health_check_allows_anonymous(self, api_client):
        response = api_client.get("/api/health/")

        assert response.status_code == 200
        assert response.json() == {"healthy": True}

    @pytest.mark.django_db
    def test_products_list_requires_auth(self, api_client):
        response = api_client.get("/api/products/")

        assert response.status_code in {401, 403}

    @pytest.mark.django_db
    def test_products_list_with_jwt(self, jwt_client):
        response = jwt_client.get("/api/products/")

        assert response.status_code == 200

    @pytest.mark.django_db
    def test_products_list_with_invalid_jwt(self):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer invalid")

        response = client.get("/api/products/")

        assert response.status_code == 401

    @pytest.mark.django_db
    def test_product_detail_requires_auth(self, api_client, product):
        response = api_client.get(f"/api/products/{product.id}/")

        assert response.status_code in {401, 403}

    @pytest.mark.django_db
    def test_product_update_requires_auth(self, api_client, product):
        response = api_client.patch(
            f"/api/products/{product.id}/",
            {"description": "chips"},
        )

        assert response.status_code in {401, 403}

    @pytest.mark.django_db
    def test_product_delete_requires_auth(self, api_client, product):
        response = api_client.delete(f"/api/products/{product.id}/")

        assert response.status_code in {401, 403}

    @pytest.mark.django_db
    def test_product_create_update_delete_flow(self, auth_client):
        with patch("apps.api.views.publish_handler") as publish_mock:
            create_response = auth_client.post(
                "/api/products/",
                {"name": "cookie", "description": "choco", "price": "5.00"},
            )

        assert create_response.status_code == 201
        product_id = create_response.data["id"]
        publish_mock.assert_called_once()

        product_obj = Product.objects.get(pk=product_id)
        assert product_obj.version == 1

        with patch("apps.api.views.publish_handler") as publish_mock:
            update_response = auth_client.patch(
                f"/api/products/{product_id}/",
                {"description": "chips"},
            )

        assert update_response.status_code == 200
        product_obj.refresh_from_db()
        assert product_obj.version == 2
        publish_mock.assert_called_once()

        with patch("apps.api.views.publish_handler") as publish_mock:
            delete_response = auth_client.delete(f"/api/products/{product_id}/")

        assert delete_response.status_code == 204
        product_obj.refresh_from_db()
        assert product_obj.deleted_at is not None
        publish_mock.assert_called_once()

    @pytest.mark.django_db
    def test_product_update_duplicate_name(self, auth_client):
        first = Product.objects.create(name="cookie", description="choco", price="5.00")
        second = Product.objects.create(name="cake", description="vanilla", price="6.00")

        response = auth_client.patch(
            f"/api/products/{second.id}/",
            {"name": first.name},
        )

        assert response.status_code == 400
        assert "name" in response.data

    @pytest.mark.django_db
    def test_product_validation_price_min(self, auth_client):
        response = auth_client.post(
            "/api/products/",
            {"name": "cookie", "description": "choco", "price": "0.00"},
        )

        assert response.status_code == 400
        assert "price" in response.data

    @pytest.mark.django_db
    def test_product_validation_duplicate_active_name(self, auth_client, product):
        response = auth_client.post(
            "/api/products/",
            {"name": product.name, "description": "choco", "price": "5.00"},
        )

        assert response.status_code == 400
        assert "name" in response.data

    @pytest.mark.django_db
    def test_product_validation_missing_fields(self, auth_client):
        response = auth_client.post(
            "/api/products/",
            {"name": "cookie"},
        )

        assert response.status_code == 400
        assert "description" in response.data
        assert "price" in response.data

    @pytest.mark.django_db
    def test_product_validation_blank_fields(self, auth_client):
        response = auth_client.post(
            "/api/products/",
            {"name": "", "description": "", "price": "5.00"},
        )

        assert response.status_code == 400
        assert "name" in response.data
        assert "description" in response.data

    @pytest.mark.django_db
    def test_product_validation_invalid_price_format(self, auth_client):
        response = auth_client.post(
            "/api/products/",
            {"name": "cookie", "description": "choco", "price": "abc"},
        )

        assert response.status_code == 400
        assert "price" in response.data

    @pytest.mark.django_db
    def test_product_validation_price_decimal_places(self, auth_client):
        response = auth_client.post(
            "/api/products/",
            {"name": "cookie", "description": "choco", "price": "5.123"},
        )

        assert response.status_code == 400
        assert "price" in response.data

    @pytest.mark.django_db
    def test_product_validation_name_max_length(self, auth_client):
        response = auth_client.post(
            "/api/products/",
            {"name": "a" * 256, "description": "choco", "price": "5.00"},
        )

        assert response.status_code == 400
        assert "name" in response.data

    @pytest.mark.django_db
    def test_soft_delete_hides_from_list(self, auth_client, product):
        with patch("apps.api.views.publish_handler"):
            response = auth_client.delete(f"/api/products/{product.id}/")

        assert response.status_code == 204

        list_response = auth_client.get("/api/products/")
        assert list_response.status_code == 200
        assert list_response.data == []

    @pytest.mark.django_db
    def test_soft_deleted_retrieve_returns_404(self, auth_client, product):
        with patch("apps.api.views.publish_handler"):
            response = auth_client.delete(f"/api/products/{product.id}/")

        assert response.status_code == 204
        retrieve = auth_client.get(f"/api/products/{product.id}/")
        assert retrieve.status_code == 404

    @pytest.mark.django_db
    def test_events_streams_messages(self, api_client):
        class FakePubSub:
            def __init__(self):
                self.closed = False
                self.pattern = None

            def psubscribe(self, pattern):
                self.pattern = pattern

            def listen(self):
                yield {"type": "pmessage", "data": b'{"event":"test"}'}

            def close(self):
                self.closed = True

        fake = FakePubSub()
        with patch("apps.api.views.redis_client") as redis_mock:
            redis_mock.pubsub.return_value = fake
            response = api_client.get("/api/events/")
            chunks = []
            for chunk in response.streaming_content:
                if isinstance(chunk, bytes):
                    chunks.append(chunk)
                else:
                    chunks.append(chunk.encode())
            payload = b"".join(chunks).decode()

        assert response.status_code == 200
        assert response["Content-Type"] == "text/event-stream"
        assert response["Cache-Control"] == "no-cache"
        assert response["X-Accel-Buffering"] == "no"
        assert response["Access-Control-Allow-Origin"] == "*"
        assert '"status": "connected"' in payload
        assert '"event":"test"' in payload
        assert fake.pattern == "*"
        assert fake.closed is True

    @pytest.mark.django_db
    def test_events_handles_redis_error(self, api_client):
        class FakePubSub:
            def __init__(self):
                self.closed = False

            def psubscribe(self, pattern):
                return None

            def listen(self):
                raise RuntimeError("redis down")

            def close(self):
                self.closed = True

        fake = FakePubSub()
        with patch("apps.api.views.redis_client") as redis_mock:
            redis_mock.pubsub.return_value = fake
            response = api_client.get("/api/events/")
            chunks = []
            for chunk in response.streaming_content:
                if isinstance(chunk, bytes):
                    chunks.append(chunk)
                else:
                    chunks.append(chunk.encode())
            payload = b"".join(chunks).decode()

        assert response.status_code == 200
        assert '"status": "connected"' in payload
        assert fake.closed is True


class TestSerializers:
    @pytest.mark.django_db
    def test_product_serializer_read_only_fields(self):
        serializer = ProductSerializer(
            data={
                "name": "cookie",
                "description": "choco",
                "price": "5.00",
                "version": 99,
            },
        )

        assert serializer.is_valid()
        assert "version" not in serializer.validated_data
        product = serializer.save()
        assert product.version == 1

    @pytest.mark.django_db
    def test_product_serializer_output_fields(self, product):
        serializer = ProductSerializer(product)

        assert "id" in serializer.data
        assert "created_at" in serializer.data
        assert "updated_at" in serializer.data
        assert "version" in serializer.data

    @pytest.mark.django_db
    def test_product_serializer_duplicate_active_name(self, product):
        serializer = ProductSerializer(
            data={"name": product.name, "description": "dup", "price": "5.00"},
        )

        assert serializer.is_valid() is False
        assert "name" in serializer.errors

    @pytest.mark.django_db
    def test_product_serializer_missing_fields(self):
        serializer = ProductSerializer(data={"name": "cookie"})

        assert serializer.is_valid() is False
        assert "description" in serializer.errors
        assert "price" in serializer.errors

    @pytest.mark.django_db
    def test_product_serializer_blank_fields(self):
        serializer = ProductSerializer(
            data={"name": "", "description": "", "price": "5.00"},
        )

        assert serializer.is_valid() is False
        assert "name" in serializer.errors
        assert "description" in serializer.errors

    @pytest.mark.django_db
    def test_product_serializer_invalid_price_format(self):
        serializer = ProductSerializer(
            data={"name": "cookie", "description": "choco", "price": "abc"},
        )

        assert serializer.is_valid() is False
        assert "price" in serializer.errors

    @pytest.mark.django_db
    def test_product_serializer_price_decimal_places(self):
        serializer = ProductSerializer(
            data={"name": "cookie", "description": "choco", "price": "5.123"},
        )

        assert serializer.is_valid() is False
        assert "price" in serializer.errors


class TestModels:
    @pytest.mark.django_db
    def test_soft_delete_hides_from_manager(self, product):
        product.delete()

        assert Product.objects.filter(pk=product.pk).count() == 0
        assert Product.all_objects.filter(pk=product.pk).count() == 1

    @pytest.mark.django_db
    def test_deleted_only_manager(self):
        active = Product.objects.create(name="cookie", description="choco", price="5.00")
        deleted = Product.objects.create(name="cake", description="vanilla", price="6.00")
        deleted.delete()

        assert Product.objects.filter(pk=deleted.pk).exists() is False
        assert Product.all_objects.filter(pk=deleted.pk).exists() is True
        assert Product.objects.filter(pk=active.pk).exists() is True
        assert Product.all_objects.filter(pk=active.pk).exists() is True
        assert list(Product.objects.all()) == [active]
        assert list(Product.objects.deleted_only()) == [deleted]

    @pytest.mark.django_db
    def test_soft_delete_allows_recreate_same_name(self, product):
        product.delete()
        recreate = Product.objects.create(
            name="cookie",
            description="vanilla",
            price="6.00",
        )

        assert recreate.pk != product.pk

    @pytest.mark.django_db
    def test_soft_delete_does_not_update_updated_at(self, product):
        updated_at = product.updated_at
        product.delete()

        product.refresh_from_db()
        assert product.updated_at == updated_at

    @pytest.mark.django_db
    def test_model_str(self, product):
        assert str(product) == "cookie - $5.00"

    @pytest.mark.django_db
    def test_hard_delete_removes_row(self, product):
        product.hard_delete()
        assert Product.all_objects.filter(pk=product.pk).exists() is False


class TestGossiper:
    def test_event_name_valid(self):
        assert event_name("product", "created") == "cookiexpend.product.created"

    def test_event_name_invalid(self):
        with pytest.raises(ValueError):
            event_name("invalid", "created")

    def test_event_name_invalid_action(self):
        with pytest.raises(ValueError):
            event_name("product", "invalid")

    def test_redis_payload_removes_fields(self):
        data = {
            "id": 1,
            "name": "cookie",
            "version": 2,
            "updated_at": "2026-05-10T00:00:00Z",
        }
        payload = redis_payload(
            data,
            event="cookiexpend.product.created",
            version=2,
            updated_at="2026-05-10T00:00:00Z",
            source="test",
        )

        assert payload["data"] == {"id": 1, "name": "cookie"}
        assert payload["version"] == 2
        assert payload["updated_at"] == "2026-05-10T00:00:00Z"
        assert payload["source"] == "test"
        assert "version" not in data
        assert "updated_at" not in data

    def test_redis_payload_missing_fields_raises(self):
        data = {"id": 1, "name": "cookie"}

        with pytest.raises(KeyError):
            redis_payload(
                data,
                event="cookiexpend.product.created",
                version=1,
                updated_at="2026-05-10T00:00:00Z",
                source="test",
            )

    def test_publish_handler_calls_publish_on_redis(self):
        data = {
            "id": 1,
            "name": "cookie",
            "version": 2,
            "updated_at": "2026-05-10T00:00:00Z",
        }
        with patch("apps.api.gossiper.publish_on_redis") as publish_mock:
            publish_handler("product", "created", data, "test")

        channel, payload = publish_mock.call_args.args
        assert channel == "cookiexpend.product.created"
        assert payload["event"] == "cookiexpend.product.created"
        assert payload["data"] == {"id": 1, "name": "cookie"}


class TestAdmin:
    @pytest.mark.django_db
    def test_get_queryset_includes_deleted(self, admin_request, product_admin, product):
        product.delete()

        qs = product_admin.get_queryset(admin_request)
        assert qs.filter(pk=product.pk).exists() is True

    @pytest.mark.django_db
    def test_deactivate_selected_soft_deletes(self, admin_request, product_admin, product):
        updated_at = product.updated_at
        with patch("apps.api.admin.publish_handler") as publish_mock:
            product_admin.deactivate_selected(
                admin_request,
                Product.all_objects.filter(pk=product.pk),
            )

        product.refresh_from_db()
        assert product.deleted_at is not None
        assert product.updated_at == updated_at
        publish_mock.assert_called_once()

    @pytest.mark.django_db
    def test_activate_selected_restores(self, admin_request, product_admin, product):
        product.delete()
        product.refresh_from_db()
        updated_at = product.updated_at

        with patch("apps.api.admin.publish_handler") as publish_mock:
            product_admin.activate_selected(
                admin_request,
                Product.all_objects.filter(pk=product.pk),
            )

        product.refresh_from_db()
        assert product.deleted_at is None
        assert product.updated_at == updated_at
        publish_mock.assert_called_once()

    @pytest.mark.django_db
    def test_delete_model_hard_delete(self, admin_request, product_admin, product):
        with patch("apps.api.admin.publish_handler"):
            product_admin.delete_model(admin_request, product)

        assert Product.all_objects.filter(pk=product.pk).exists() is False

    @pytest.mark.django_db
    def test_delete_queryset_hard_delete(self, admin_request, product_admin):
        Product.objects.create(name="cookie", description="choco", price="5.00")
        Product.objects.create(name="cake", description="vanilla", price="7.00")

        with patch("apps.api.admin.publish_handler"):
            product_admin.delete_queryset(admin_request, Product.all_objects.all())

        assert Product.all_objects.count() == 0

    @pytest.mark.django_db
    def test_changeform_deactivate(self, rf, admin_user, product_admin, product):
        request = _admin_post_request(
            rf,
            admin_user,
            f"/admin/api/product/{product.pk}/change/",
            {"_deactivate": "1"},
        )

        with patch("apps.api.admin.publish_handler"):
            product_admin.changeform_view(request, object_id=str(product.pk))

        product.refresh_from_db()
        assert product.deleted_at is not None

    @pytest.mark.django_db
    def test_changeform_activate(self, rf, admin_user, product_admin, product):
        product.delete()
        product.refresh_from_db()
        updated_at = product.updated_at

        request = _admin_post_request(
            rf,
            admin_user,
            f"/admin/api/product/{product.pk}/change/",
            {"_activate": "1"},
        )

        with patch("apps.api.admin.publish_handler"):
            product_admin.changeform_view(request, object_id=str(product.pk))

        product.refresh_from_db()
        assert product.deleted_at is None
        assert product.updated_at == updated_at
