from io import BytesIO
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework.test import APIClient

from . import models


def _make_uploaded_image(name="test.png"):
    buffer = BytesIO()
    Image.new("RGB", (10, 10), color=(0, 128, 255)).save(buffer, "PNG")
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type="image/png")


@pytest.fixture()
def api_client():
    return APIClient()


@pytest.fixture()
def factory_user(db):
    user_model = get_user_model()
    u = user_model.objects.create_user(username="factory_tester", password="pass1234")
    group, _ = Group.objects.get_or_create(name="Factory manager")
    u.groups.add(group)
    return u


@pytest.fixture()
def store_user(db):
    user_model = get_user_model()
    u = user_model.objects.create_user(username="store_tester", password="pass1234")
    group, _ = Group.objects.get_or_create(name="Store manager")
    u.groups.add(group)
    return u


@pytest.fixture()
def auth_client(api_client, factory_user):
    api_client.force_authenticate(user=factory_user)
    return api_client


@pytest.fixture()
def store_client(store_user):
    client = APIClient()
    client.force_authenticate(user=store_user)
    return client


@pytest.fixture()
def department(db):
    return models.Department.objects.create(name="Sales", email="sales@example.com")


@pytest.fixture()
def subject(department):
    return models.Subject.objects.create(label="Price inquiry", department=department)


@pytest.mark.django_db
class TestDepartmentContact:
    def test_contact_sends_email_to_department(self, api_client, department, subject):
        with patch("apps.catalog.views.send_mail") as send_mail_mock:
            response = api_client.post(
                f"/api/catalog/departments/{department.id}/contact/",
                {
                    "name": "Jane Doe",
                    "email": "jane@example.com",
                    "phone": "555-1234",
                    "city": "Springfield",
                    "subject": subject.id,
                    "message": "Hello, I have a question.",
                },
            )

        assert response.status_code == 200
        send_mail_mock.assert_called_once()
        _, kwargs = send_mail_mock.call_args
        assert kwargs["to"] == [department.email]
        assert kwargs["reply_to"] == ["jane@example.com"]
        assert kwargs["ctx"]["sender_name"] == "Jane Doe"
        assert kwargs["ctx"]["sender_phone"] == "555-1234"
        assert kwargs["ctx"]["sender_city"] == "Springfield"

    def test_contact_allows_missing_phone_and_city(self, api_client, department, subject):
        with patch("apps.catalog.views.send_mail") as send_mail_mock:
            response = api_client.post(
                f"/api/catalog/departments/{department.id}/contact/",
                {
                    "name": "Jane Doe",
                    "email": "jane@example.com",
                    "subject": subject.id,
                    "message": "Hello, I have a question.",
                },
            )

        assert response.status_code == 200
        _, kwargs = send_mail_mock.call_args
        assert kwargs["ctx"]["sender_phone"] == ""
        assert kwargs["ctx"]["sender_city"] == ""

    def test_contact_rejects_subject_from_other_department(self, api_client, department, subject):
        other_department = models.Department.objects.create(name="Support", email="support@example.com")

        response = api_client.post(
            f"/api/catalog/departments/{other_department.id}/contact/",
            {
                "name": "Jane Doe",
                "email": "jane@example.com",
                "subject": subject.id,
                "message": "Hello.",
            },
        )

        assert response.status_code == 400
        assert "subject" in response.data

    def test_contact_without_department_email_returns_503(self, api_client, subject):
        subject.department.email = ""
        subject.department.save()

        response = api_client.post(
            f"/api/catalog/departments/{subject.department.id}/contact/",
            {
                "name": "Jane Doe",
                "email": "jane@example.com",
                "subject": subject.id,
                "message": "Hello.",
            },
        )

        assert response.status_code == 503

    def test_contact_validates_required_fields(self, api_client, department):
        response = api_client.post(f"/api/catalog/departments/{department.id}/contact/", {})

        assert response.status_code == 400
        assert "name" in response.data
        assert "email" in response.data
        assert "subject" in response.data
        assert "message" in response.data

    def test_department_list_does_not_expose_email(self, api_client, department):
        response = api_client.get("/api/catalog/departments/")

        assert response.status_code == 200
        assert "email" not in response.data[0]


CATALOG_ENDPOINTS = (
    "categories",
    "presentations",
    "gallery",
    "faqs",
    "departments",
    "brands",
    "retailers",
)


def _catalog_payload(endpoint: str, *, image: bool = False) -> dict:
    if endpoint == "categories":
        return {"label": "New Category", "order": 1, **({"logo": _make_uploaded_image()} if image else {})}
    if endpoint == "presentations":
        return {"label": "New Presentation", "order": 1}
    if endpoint == "gallery":
        return {"alt": "New gallery item", "order": 1, "url": _make_uploaded_image()}
    if endpoint == "faqs":
        return {"question": "New question?", "answer": "New answer.", "order": 1}
    if endpoint == "departments":
        return {"name": "New Department", "email": "new@example.com", "order": 1}
    if endpoint == "brands":
        return {"name": "New Brand", **({"logo": _make_uploaded_image()} if image else {})}
    if endpoint == "retailers":
        return {"name": "New Retailer", "address": "123 Main St", "state": "NY", "municipality": "NYC"}
    raise ValueError(endpoint)


def _create_instance(endpoint: str):
    if endpoint == "categories":
        return models.Category.objects.create(label="Existing Category")
    if endpoint == "presentations":
        return models.Presentation.objects.create(label="Existing Presentation")
    if endpoint == "gallery":
        return models.GalleryItem.objects.create(url=_make_uploaded_image(), alt="Existing item")
    if endpoint == "faqs":
        return models.FAQ.objects.create(question="Existing?", answer="Yes.")
    if endpoint == "departments":
        return models.Department.objects.create(name="Existing Department", email="existing@example.com")
    if endpoint == "brands":
        return models.Brand.objects.create(name="Existing Brand")
    if endpoint == "retailers":
        return models.Retailer.objects.create(
            name="Existing Retailer", address="1 St", state="NY", municipality="NYC"
        )
    raise ValueError(endpoint)


@pytest.mark.django_db
class TestCatalogCrudPermissions:
    @pytest.mark.parametrize("endpoint", CATALOG_ENDPOINTS)
    def test_list_allows_anonymous(self, api_client, endpoint):
        _create_instance(endpoint)

        response = api_client.get(f"/api/catalog/{endpoint}/")

        assert response.status_code == 200
        assert len(response.data) == 1

    @pytest.mark.parametrize("endpoint", CATALOG_ENDPOINTS)
    def test_create_requires_auth(self, api_client, endpoint):
        with patch("apps._api.mixins.publish_handler"):
            response = api_client.post(f"/api/catalog/{endpoint}/", _catalog_payload(endpoint, image=True))

        assert response.status_code in {401, 403}

    @pytest.mark.parametrize("endpoint", CATALOG_ENDPOINTS)
    def test_create_forbidden_for_store_manager(self, store_client, endpoint):
        with patch("apps._api.mixins.publish_handler"):
            response = store_client.post(f"/api/catalog/{endpoint}/", _catalog_payload(endpoint, image=True))

        assert response.status_code == 403

    @pytest.mark.parametrize("endpoint", CATALOG_ENDPOINTS)
    def test_create_allowed_for_factory_manager(self, auth_client, endpoint):
        with patch("apps._api.mixins.publish_handler"):
            response = auth_client.post(f"/api/catalog/{endpoint}/", _catalog_payload(endpoint, image=True))

        assert response.status_code == 201

    @pytest.mark.parametrize("endpoint", CATALOG_ENDPOINTS)
    def test_delete_requires_factory_manager(self, api_client, store_client, endpoint):
        instance = _create_instance(endpoint)

        anon_response = api_client.delete(f"/api/catalog/{endpoint}/{instance.id}/")
        store_response = store_client.delete(f"/api/catalog/{endpoint}/{instance.id}/")

        assert anon_response.status_code in {401, 403}
        assert store_response.status_code == 403

    @pytest.mark.parametrize("endpoint", CATALOG_ENDPOINTS)
    def test_delete_allowed_for_factory_manager(self, auth_client, endpoint):
        instance = _create_instance(endpoint)

        with patch("apps._api.mixins.publish_handler"):
            response = auth_client.delete(f"/api/catalog/{endpoint}/{instance.id}/")

        assert response.status_code == 204


@pytest.mark.django_db
class TestCatalogFieldBehavior:
    def test_category_duplicate_label_rejected(self, auth_client):
        models.Category.objects.create(label="Cookies")

        with patch("apps._api.mixins.publish_handler"):
            response = auth_client.post("/api/catalog/categories/", {"label": "Cookies", "order": 0})

        assert response.status_code == 400
        assert "label" in response.data

    def test_presentation_duplicate_label_rejected(self, auth_client):
        models.Presentation.objects.create(label="Bag")

        with patch("apps._api.mixins.publish_handler"):
            response = auth_client.post("/api/catalog/presentations/", {"label": "Bag", "order": 0})

        assert response.status_code == 400
        assert "label" in response.data

    def test_category_update_without_new_logo_keeps_existing(self, auth_client):
        # Category.save() reprocesses (and renames) the logo on every save regardless
        # of whether this request touched it, so this only asserts the logo survives
        # (isn't cleared) — not that the filename is byte-for-byte unchanged.
        category = models.Category.objects.create(label="Cookies", logo=_make_uploaded_image())

        with patch("apps._api.mixins.publish_handler"):
            response = auth_client.patch(
                f"/api/catalog/categories/{category.id}/", {"label": "Cookies Updated"}
            )

        assert response.status_code == 200
        category.refresh_from_db()
        assert category.logo.name

    def test_category_logo_is_absolute_url(self, api_client):
        category = models.Category.objects.create(label="Cookies")
        models.Category.objects.filter(pk=category.pk).update(logo="categories/test.webp")

        response = api_client.get(f"/api/catalog/categories/{category.id}/")

        assert response.data["logo"].startswith("http://testserver/media/")

    def test_department_email_hidden_from_anonymous_detail(self, api_client, department):
        response = api_client.get(f"/api/catalog/departments/{department.id}/")

        assert response.status_code == 200
        assert "email" not in response.data

    def test_department_email_visible_to_factory_manager(self, auth_client, department):
        response = auth_client.get(f"/api/catalog/departments/{department.id}/")

        assert response.status_code == 200
        assert response.data["email"] == department.email

    def test_subject_create_and_filter_by_department(self, auth_client, department):
        other_department = models.Department.objects.create(name="Other", email="other@example.com")
        models.Subject.objects.create(label="Other subject", department=other_department)

        with patch("apps._api.mixins.publish_handler"):
            response = auth_client.post(
                "/api/catalog/subjects/",
                {"label": "New subject", "department": department.id, "order": 0},
            )
        assert response.status_code == 201

        list_response = auth_client.get(f"/api/catalog/subjects/?department={department.id}")
        assert list_response.status_code == 200
        assert len(list_response.data) == 1
        assert list_response.data[0]["label"] == "New subject"

    def test_department_nests_its_subjects(self, api_client, department, subject):
        response = api_client.get(f"/api/catalog/departments/{department.id}/")

        assert response.status_code == 200
        assert len(response.data["subjects"]) == 1
        assert response.data["subjects"][0]["label"] == subject.label

    def test_retailer_create_with_brand(self, auth_client):
        brand = models.Brand.objects.create(name="Acme")

        with patch("apps._api.mixins.publish_handler"):
            response = auth_client.post(
                "/api/catalog/retailers/",
                {
                    "name": "Acme Downtown",
                    "address": "123 Main St",
                    "state": "NY",
                    "municipality": "NYC",
                    "brand": brand.id,
                },
            )

        assert response.status_code == 201
        assert response.data["brand"]["id"] == brand.id
        assert response.data["brand"]["name"] == "Acme"

    def test_retailer_without_brand_returns_null(self, api_client):
        retailer = models.Retailer.objects.create(
            name="Independent", address="1 St", state="NY", municipality="NYC"
        )

        response = api_client.get(f"/api/catalog/retailers/{retailer.id}/")

        assert response.data["brand"] is None

    def test_brand_logo_is_absolute_url_and_not_writable_via_logo_url(self, auth_client):
        brand = models.Brand.objects.create(name="Acme")
        models.Brand.objects.filter(pk=brand.pk).update(logo="brands/test.webp")

        response = auth_client.get(f"/api/catalog/brands/{brand.id}/")

        assert response.data["logo_url"].startswith("http://testserver/media/")
        assert "logo" not in response.data

    def test_gallery_item_requires_image_on_create(self, auth_client):
        with patch("apps._api.mixins.publish_handler"):
            response = auth_client.post("/api/catalog/gallery/", {"alt": "No image", "order": 0})

        assert response.status_code == 400
        assert "url" in response.data
