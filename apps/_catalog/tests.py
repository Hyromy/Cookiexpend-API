from unittest.mock import patch

import pytest
from rest_framework.test import APIClient

from . import models


@pytest.fixture()
def api_client():
    return APIClient()


@pytest.fixture()
def department(db):
    return models.Department.objects.create(name="Sales", email="sales@example.com")


@pytest.fixture()
def subject(department):
    return models.Subject.objects.create(label="Price inquiry", department=department)


@pytest.mark.django_db
class TestDepartmentContact:
    def test_contact_sends_email_to_department(self, api_client, department, subject):
        with patch("apps._catalog.views.send_mail") as send_mail_mock:
            response = api_client.post(
                f"/api/departments/{department.id}/contact/",
                {
                    "name": "Jane Doe",
                    "email": "jane@example.com",
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

    def test_contact_rejects_subject_from_other_department(self, api_client, department, subject):
        other_department = models.Department.objects.create(name="Support", email="support@example.com")

        response = api_client.post(
            f"/api/departments/{other_department.id}/contact/",
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
            f"/api/departments/{subject.department.id}/contact/",
            {
                "name": "Jane Doe",
                "email": "jane@example.com",
                "subject": subject.id,
                "message": "Hello.",
            },
        )

        assert response.status_code == 503

    def test_contact_validates_required_fields(self, api_client, department):
        response = api_client.post(f"/api/departments/{department.id}/contact/", {})

        assert response.status_code == 400
        assert "name" in response.data
        assert "email" in response.data
        assert "subject" in response.data
        assert "message" in response.data

    def test_department_list_does_not_expose_email(self, api_client, department):
        response = api_client.get("/api/departments/")

        assert response.status_code == 200
        assert "email" not in response.data[0]
