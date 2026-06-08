from unittest.mock import patch

import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory
from rest_framework.test import APIClient

from . import models
from .admin import ProductAdmin
from .gossiper import event_name, publish_handler, redis_payload
from .models import Product
from .serializers import ProductSerializer


@pytest.fixture()
def user(db):
    user_model = get_user_model()
    u = user_model.objects.create_user(username="tester", password="pass1234")
    g1, _ = Group.objects.get_or_create(name="Factory manager")
    g2, _ = Group.objects.get_or_create(name="Store manager")
    u.groups.add(g1, g2)
    return u


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
    return Product.objects.create(name="cookie", price="5.00")


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


CRUD_ENDPOINTS = (
    ("factories", models.Factory),
    ("stores", models.Store),
    ("deliveries", models.Delivery),
    ("inventories", models.Inventory),
    ("sells", models.Sell),
    ("payment-methods", models.PaymentMethod),
    ("sell-details", models.SellDetail),
    ("payments", models.Payment),
)

CREATE_ENDPOINTS = (
    ("factories", models.Factory),
    ("stores", models.Store),
    ("deliveries", models.Delivery),
    ("sells", models.Sell),
    ("sell-details", models.SellDetail),
    ("payments", models.Payment),
)


def _create_establishment(name="Cookiexpend"):
    return models.Establishment.objects.create(
        name=name,
        municipality="Springfield",
        neighborhood="Central",
        street="Main",
        number="123",
    )


def _create_product(name="cookie"):
    return models.Product.objects.create(name=name, price="5.00")


def _create_factory(establishment=None):
    if establishment is None:
        establishment = _create_establishment("Factory")
    return models.Factory.objects.create(establishment=establishment)


def _create_store(establishment=None):
    if establishment is None:
        establishment = _create_establishment("Store")
    return models.Store.objects.create(establishment=establishment)


def _create_delivery(factory=None, store=None):
    if factory is None and store is None:
        establishment = _create_establishment("Delivery")
        factory = _create_factory(establishment)
        store = _create_store(establishment)
    elif factory is None:
        factory = _create_factory(store.establishment)
    elif store is None:
        store = _create_store(factory.establishment)

    return models.Delivery.objects.create(factory=factory, store=store)


def _create_sell(store=None):
    if store is None:
        store = _create_store()
    return models.Sell.objects.create(store=store, total="10.00")


def _create_payment_method(name="cash"):
    payment_method, _ = models.PaymentMethod.objects.get_or_create(name=name)
    return payment_method


def _create_inventory(store=None, product=None, quantity=5):
    if store is None:
        store = _create_store()
    if product is None:
        product = _create_product()

    return models.Inventory.objects.create(store=store, product=product, quantity=quantity)


def _payload_for_endpoint(endpoint: str) -> dict:
    if endpoint == "factories":
        return {
            "establishment": {
                "name": "New Factory Est",
                "municipality": "Springfield",
                "neighborhood": "Industrial",
                "street": "Avenue",
                "number": "42",
            }
        }
    if endpoint == "stores":
        return {
            "establishment": {
                "name": "New Store Est",
                "municipality": "Springfield",
                "neighborhood": "Retail",
                "street": "Boulevard",
                "number": "5",
            }
        }
    if endpoint == "deliveries":
        establishment = _create_establishment("Delivery")
        factory = _create_factory(establishment)
        store = _create_store(establishment)
        product = _create_product()
        return {
            "factory": factory.id,
            "store": store.id,
            "package": [{"product": product.id, "quantity": 10}],
        }
    if endpoint == "inventories":
        store = _create_store()
        product = _create_product()
        return {"store": store.id, "product": product.id, "quantity": 5}
    if endpoint == "sells":
        store = _create_store()
        product = _create_product()
        _create_inventory(store=store, product=product, quantity=5)
        _create_payment_method("cash")
        return {
            "store": store.id,
            "products": [{"product": product.id, "quantity": 1}],
        }
    if endpoint == "payment-methods":
        return {"name": "cash_new"}
    if endpoint == "sell-details":
        sell = _create_sell()
        product = _create_product()
        return {
            "sell": sell.id,
            "product": product.id,
            "quantity": 1,
            "price": "5.00",
        }
    if endpoint == "payments":
        sell = _create_sell()
        payment_method = _create_payment_method("credit")
        return {
            "sell": sell.id,
            "payment_method": payment_method.id,
            "amount": "5.00",
        }

    raise ValueError(f"Unsupported endpoint: {endpoint}")


class TestLogicAndEndpoints:
    def test_status_change_handler_logic(self):
        from apps.api.views import status_change_handler

        assert status_change_handler("pending", 1) == "in_progress"
        assert status_change_handler("in_progress", 1) == "completed"
        assert status_change_handler("in_progress", -1) == "cancelled"
        assert status_change_handler("cancelled", 1) == "in_progress"

        with pytest.raises(ValueError):
            status_change_handler("pending", -1)
        with pytest.raises(ValueError):
            status_change_handler("completed", 1)

    @pytest.mark.django_db
    def test_delivery_status_endpoint(self, auth_client):
        # Aseguramos que existan los estados (por si no se corrió el seeder en test config)
        models.Status.objects.get_or_create(id=1, name="pending")
        models.Status.objects.get_or_create(id=2, name="in_progress")
        models.Status.objects.get_or_create(id=3, name="completed")

        delivery = _create_delivery()
        product = _create_product()
        models.Package.objects.create(delivery=delivery, product=product, quantity=5)

        # Transición 1: Pending -> In Progress
        response = auth_client.patch(
            f"/api/deliveries/{delivery.id}/status/", {"step": 1}, format="json"
        )
        assert response.status_code == 200
        delivery.refresh_from_db()
        assert delivery.status.name == "in_progress"

        # Transición 2: In Progress -> Completed
        response = auth_client.patch(
            f"/api/deliveries/{delivery.id}/status/", {"step": 1}, format="json"
        )
        assert response.status_code == 200
        delivery.refresh_from_db()
        assert delivery.status.name == "completed"

        # Debe haber aumentado el inventario porque el estado completó con ID=3
        inventory = models.Inventory.objects.get(store=delivery.store, product=product)
        assert inventory.quantity == 5


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
        )

        assert response.status_code in {401, 403}

    @pytest.mark.django_db
    def test_product_delete_requires_auth(self, api_client, product):
        response = api_client.delete(f"/api/products/{product.id}/")

        assert response.status_code in {401, 403}

    @pytest.mark.django_db
    @pytest.mark.parametrize("endpoint,_model_class", CRUD_ENDPOINTS)
    def test_crud_list_requires_auth(self, api_client, endpoint, _model_class):
        response = api_client.get(f"/api/{endpoint}/")

        assert response.status_code in {401, 403}

    @pytest.mark.django_db
    @pytest.mark.parametrize("endpoint,model_class", CREATE_ENDPOINTS)
    def test_crud_create_minimal(self, auth_client, endpoint, model_class):
        payload = _payload_for_endpoint(endpoint)

        with patch("apps.api.views.publish_handler"):
            response = auth_client.post(f"/api/{endpoint}/", payload, format="json")

        assert response.status_code == 201
        assert model_class.objects.filter(pk=response.data["id"]).exists()

    @pytest.mark.django_db
    def test_product_create_update_delete_flow(self, auth_client):
        with patch("apps.api.views.publish_handler") as publish_mock:
            create_response = auth_client.post(
                "/api/products/",
                {"name": "cookie", "price": "5.00"},
            )

        assert create_response.status_code == 201
        product_id = create_response.data["id"]
        publish_mock.assert_called_once()

        product_obj = Product.objects.get(pk=product_id)
        assert product_obj.version == 1

        with patch("apps.api.views.publish_handler") as publish_mock:
            update_response = auth_client.patch(
                f"/api/products/{product_id}/",
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
        first = Product.objects.create(name="cookie", price="5.00")
        second = Product.objects.create(name="cake", price="6.00")

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
            {"name": "cookie", "price": "0.00"},
        )

        assert response.status_code == 400
        assert "price" in response.data

    @pytest.mark.django_db
    def test_product_validation_duplicate_active_name(self, auth_client, product):
        response = auth_client.post(
            "/api/products/",
            {"name": product.name, "price": "5.00"},
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
        assert "price" in response.data

    @pytest.mark.django_db
    def test_product_validation_blank_fields(self, auth_client):
        response = auth_client.post(
            "/api/products/",
            {"name": "", "price": "5.00"},
        )

        assert response.status_code == 400
        assert "name" in response.data

    @pytest.mark.django_db
    def test_product_validation_invalid_price_format(self, auth_client):
        response = auth_client.post(
            "/api/products/",
            {"name": "cookie", "price": "abc"},
        )

        assert response.status_code == 400
        assert "price" in response.data

    @pytest.mark.django_db
    def test_product_validation_price_decimal_places(self, auth_client):
        response = auth_client.post(
            "/api/products/",
            {"name": "cookie", "price": "5.123"},
        )

        assert response.status_code == 400
        assert "price" in response.data

    @pytest.mark.django_db
    def test_product_validation_name_max_length(self, auth_client):
        response = auth_client.post(
            "/api/products/",
            {"name": "a" * 256, "price": "5.00"},
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
    def test_events_streams_messages(self, user):
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
        client = APIClient()
        client.force_login(user)

        with patch("apps.api.views.redis_client") as redis_mock:
            redis_mock.pubsub.return_value = fake
            response = client.get("/api/events/")
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
    def test_events_handles_redis_error(self, user):
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
        client = APIClient()
        client.force_login(user)

        with patch("apps.api.views.redis_client") as redis_mock:
            redis_mock.pubsub.return_value = fake
            response = client.get("/api/events/")
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
    def test_sell_creation_consumes_inventory(self, admin_user):
        client = APIClient()
        client.force_authenticate(user=admin_user)

        store = _create_store()
        product = _create_product()
        _create_inventory(store=store, product=product, quantity=5)
        _create_payment_method("cash")

        with patch("apps.api.views.publish_handler"):
            response = client.post(
                "/api/sells/",
                {
                    "store": store.id,
                    "products": [{"product": product.id, "quantity": 3}],
                },
                format="json",
            )

        assert response.status_code == 201
        inventory = models.Inventory.objects.get(store=store, product=product)
        assert inventory.quantity == 2
        sell = models.Sell.objects.get(pk=response.data["id"])
        assert sell.total == 15
        assert models.SellDetail.objects.filter(sell=sell, product=product, quantity=3).exists()
        assert models.Payment.objects.filter(sell=sell, amount="15.00").exists()

    @pytest.mark.django_db
    def test_sell_creation_rejects_insufficient_inventory(self, admin_user):
        client = APIClient()
        client.force_authenticate(user=admin_user)

        store = _create_store()
        product = _create_product()
        _create_inventory(store=store, product=product, quantity=1)
        _create_payment_method("cash")

        response = client.post(
            "/api/sells/",
            {
                "store": store.id,
                "products": [{"product": product.id, "quantity": 2}],
            },
            format="json",
        )

        assert response.status_code == 400
        errors = response.data["products"]
        assert isinstance(errors, list)
        assert errors, errors
        first = errors[0]
        assert first["product"]["name"] == product.name
        assert int(str(first["available"])) == 1
        assert int(str(first["requested"])) == 2
        assert models.Sell.objects.count() == 0
        assert models.Inventory.objects.get(store=store, product=product).quantity == 1

    @pytest.mark.django_db
    def test_product_serializer_duplicate_active_name(self, product):
        serializer = ProductSerializer(
            data={"name": product.name, "price": "5.00"},
        )

        assert serializer.is_valid() is False
        assert "name" in serializer.errors

    @pytest.mark.django_db
    def test_product_serializer_missing_fields(self):
        serializer = ProductSerializer(data={"name": "cookie"})

        assert serializer.is_valid() is False
        assert "price" in serializer.errors

    @pytest.mark.django_db
    def test_product_serializer_blank_fields(self):
        serializer = ProductSerializer(
            data={"name": "", "price": "5.00"},
        )

        assert serializer.is_valid() is False
        assert "name" in serializer.errors

    @pytest.mark.django_db
    def test_product_serializer_invalid_price_format(self):
        serializer = ProductSerializer(
            data={"name": "cookie", "price": "abc"},
        )

        assert serializer.is_valid() is False
        assert "price" in serializer.errors

    @pytest.mark.django_db
    def test_product_serializer_price_decimal_places(self):
        serializer = ProductSerializer(
            data={"name": "cookie", "price": "5.123"},
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
        active = Product.objects.create(name="cookie", price="5.00")
        deleted = Product.objects.create(name="cake", price="6.00")
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

    def test_redis_payload_includes_envelope(self):
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
            model="product",
            action="created",
        )

        assert payload["data"] == data
        assert payload["version"] == 2
        assert payload["updated_at"] == "2026-05-10T00:00:00Z"
        assert payload["source"] == "test"
        assert payload["model"] == "product"
        assert payload["action"] == "created"

    def test_redis_payload_missing_fields_allows_none(self):
        data = {"id": 1, "name": "cookie"}

        payload = redis_payload(
            data,
            event="cookiexpend.product.created",
            version=None,
            updated_at=None,
            source="test",
            model="product",
            action="created",
        )

        assert payload["data"] == data
        assert payload["version"] is None
        assert payload["updated_at"] is None

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
        assert payload["data"] == data


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
        Product.objects.create(name="cookie", price="5.00")
        Product.objects.create(name="cake", price="7.00")

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
