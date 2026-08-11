from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Measurement

User = get_user_model()


class MeasurementViewSetTests(APITestCase):

    def setUp(self):
        self.url = "/api/sistema-medicion-iot/measurements/"

        self.valid_data = {
            "station": "Pes-001",
            "process": "G001",
            "time_ms": 12500,
        }

        # Usuario Bot
        self.bot_user = User.objects.create_user(
            username="bot_pes_001",
            password="testpassword123",
        )

        self.bot_group, _ = Group.objects.get_or_create(
            name="Bot"
        )

        self.bot_user.groups.add(
            self.bot_group
        )

        # Usuario Factory Manager
        self.factory_user = User.objects.create_user(
            username="factory_manager",
            password="testpassword123",
        )

        self.factory_group, _ = Group.objects.get_or_create(
            name="Factory manager"
        )

        self.factory_user.groups.add(
            self.factory_group
        )

        # Usuario Store Manager
        self.store_user = User.objects.create_user(
            username="store_manager",
            password="testpassword123",
        )

        self.store_group, _ = Group.objects.get_or_create(
            name="Store manager"
        )

        self.store_user.groups.add(
            self.store_group
        )

    def test_get_measurements_requires_authentication(self):
        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_post_measurement_requires_authentication(self):
        response = self.client.post(
            self.url,
            self.valid_data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_factory_manager_can_get_measurements(self):
        self.client.force_authenticate(
            user=self.factory_user
        )

        response = self.client.get(
            self.url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertTrue(
            response.data["success"]
        )

    def test_bot_can_create_measurement(self):
        self.client.force_authenticate(
            user=self.bot_user
        )

        response = self.client.post(
            self.url,
            self.valid_data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertTrue(
            response.data["success"]
        )

        self.assertEqual(
            Measurement.objects.count(),
            1,
        )

        measurement = Measurement.objects.first()

        self.assertEqual(
            measurement.station,
            "Pes-001",
        )

        self.assertEqual(
            measurement.process,
            "G001",
        )

    def test_bot_cannot_get_measurements(self):
        self.client.force_authenticate(
            user=self.bot_user
        )

        response = self.client.get(
            self.url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_factory_manager_cannot_create_measurement(self):
        self.client.force_authenticate(
            user=self.factory_user
        )

        response = self.client.post(
            self.url,
            self.valid_data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_bot_cannot_create_invalid_measurement(self):
        self.client.force_authenticate(
            user=self.bot_user
        )

        invalid_data = {
            "station": "Pes-001",
            "process": "G001",
        }

        response = self.client.post(
            self.url,
            invalid_data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )