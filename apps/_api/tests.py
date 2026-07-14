from contextlib import contextmanager
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.contrib import admin
from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import AnonymousUser
from django.core.validators import MinValueValidator
from django.db import connection
from django.db import models as django_models
from django.test import RequestFactory
from django.test.utils import isolate_apps
from rest_framework import serializers

from .admin import AdminPanel
from .mixins import MixinViewSet, NestedMixin, PublicMixin
from .models import BaseModel, money, unique_active_constraint
from .serializers import auditory_fields
from .views import api_health_check


@contextmanager
def model_tables(*models_to_create):
    with connection.schema_editor() as schema_editor:
        for model in models_to_create:
            schema_editor.create_model(model)

    try:
        yield
    finally:
        with connection.schema_editor() as schema_editor:
            for model in reversed(models_to_create):
                schema_editor.delete_model(model)


class TestViews:
    class TestApiHealthCheck:
        def test_returns_healthy_response(self):
            request = RequestFactory().get("/api/health/")

            response = api_health_check(request)

            assert response.status_code == 200
            assert response.data == {"healthy": True}


class TestSerializers:
    class TestAuditoryFields:
        def test_includes_core_audit_fields(self):
            fields = auditory_fields("name", "email")

            assert fields == ["id", "name", "email", "created_at", "updated_at", "version"]

        def test_keeps_input_order(self):
            fields = auditory_fields("first", "second", "third")

            assert fields == [
                "id",
                "first",
                "second",
                "third",
                "created_at",
                "updated_at",
                "version",
            ]


@pytest.mark.django_db(transaction=True)
class TestModels:
    class TestMoney:
        def test_builds_decimal_field_with_minimum_validator(self):
            field = money()

            assert field.max_digits == 6
            assert field.decimal_places == 2
            assert any(
                isinstance(validator, MinValueValidator)
                and validator.limit_value == Decimal("0.01")
                for validator in field.validators
            )

        def test_supports_custom_sizes(self):
            field = money(6, 3)

            assert field.max_digits == 9
            assert field.decimal_places == 3

    class TestUniqueActiveConstraint:
        def test_builds_soft_delete_unique_constraint(self):
            constraint = unique_active_constraint("product", "name", "sku")

            assert constraint.fields == ("name", "sku")
            assert constraint.name == "unique_active_product_name_sku"
            assert constraint.condition == django_models.Q(deleted_at__isnull=True)

    class TestBaseModelSoftDelete:
        @isolate_apps()
        def test_delete_marks_row_as_deleted_and_manager_hides_it(self):
            class SoftDeleteSample(BaseModel):
                name = django_models.CharField(max_length=50)

                class Meta:
                    app_label = "api_tests"

            with model_tables(SoftDeleteSample):
                sample = SoftDeleteSample.all_objects.create(name="cookie")

                assert SoftDeleteSample.objects.count() == 1

                sample.delete()

                assert sample.deleted_at is not None
                assert SoftDeleteSample.objects.filter(pk=sample.pk).exists() is False
                assert SoftDeleteSample.all_objects.filter(pk=sample.pk).exists() is True
                assert list(SoftDeleteSample.objects.deleted_only()) == [sample]

        @isolate_apps()
        def test_hard_delete_removes_row(self):
            class HardDeleteSample(BaseModel):
                name = django_models.CharField(max_length=50)

                class Meta:
                    app_label = "api_tests"

            with model_tables(HardDeleteSample):
                sample = HardDeleteSample.all_objects.create(name="cake")

                sample.hard_delete()

                assert HardDeleteSample.all_objects.filter(pk=sample.pk).exists() is False


@pytest.mark.django_db(transaction=True)
class TestMixins:
    class TestNestedMixin:
        @isolate_apps()
        def test_create_nested_builds_related_instance_first(self):
            class Profile(django_models.Model):
                city = django_models.CharField(max_length=50)

                class Meta:
                    app_label = "api_tests"

                def __str__(self):
                    return self.city

            class Account(django_models.Model):
                name = django_models.CharField(max_length=50)
                profile = django_models.ForeignKey(Profile, on_delete=django_models.CASCADE)

                class Meta:
                    app_label = "api_tests"

                def __str__(self):
                    return self.name

            class AccountSerializer(NestedMixin, serializers.ModelSerializer):
                nested_field = "profile"
                nested_model = Profile

                class Meta:
                    model = Account
                    fields = ["id", "name", "profile"]

            with model_tables(Profile, Account):
                serializer = AccountSerializer()

                account = serializer.create_nested(
                    {"name": "Main", "profile": {"city": "Springfield"}}
                )

                assert account.pk is not None
                assert account.profile.city == "Springfield"

        @isolate_apps()
        def test_update_nested_updates_related_instance(self):
            class Profile(django_models.Model):
                city = django_models.CharField(max_length=50)

                class Meta:
                    app_label = "api_tests"

                def __str__(self):
                    return self.city

            class Account(django_models.Model):
                name = django_models.CharField(max_length=50)
                profile = django_models.ForeignKey(Profile, on_delete=django_models.CASCADE)

                class Meta:
                    app_label = "api_tests"

                def __str__(self):
                    return self.name

            class AccountSerializer(NestedMixin, serializers.ModelSerializer):
                nested_field = "profile"
                nested_model = Profile

                class Meta:
                    model = Account
                    fields = ["id", "name", "profile"]

            with model_tables(Profile, Account):
                profile = Profile.objects.create(city="Old Town")
                account = Account.objects.create(name="Main", profile=profile)

                serializer = AccountSerializer()
                updated = serializer.update_nested(
                    account,
                    {"name": "Updated", "profile": {"city": "New Town"}},
                )

                profile.refresh_from_db()
                account.refresh_from_db()

                assert updated.name == "Updated"
                assert account.name == "Updated"
                assert profile.city == "New Town"

    class TestPublicMixin:
        class ExampleSerializer(PublicMixin, serializers.Serializer):
            public_fields = {"public"}
            public = serializers.CharField()
            secret = serializers.CharField()

        def test_hides_private_fields_for_anonymous_users(self):
            request = RequestFactory().get("/")
            request.user = AnonymousUser()

            serializer = self.ExampleSerializer(context={"request": request})

            assert set(serializer.fields) == {"public"}

        def test_keeps_all_fields_for_authenticated_users(self):
            request = RequestFactory().get("/")
            request.user = SimpleNamespace(is_authenticated=True)

            serializer = self.ExampleSerializer(context={"request": request})

            assert set(serializer.fields) == {"public", "secret"}

    class TestMixinViewSet:
        @isolate_apps()
        def test_perform_create_update_and_destroy_publish_events(self):
            class Thing(BaseModel):
                name = django_models.CharField(max_length=50)

                class Meta:
                    app_label = "api_tests"

            class ThingSerializer(serializers.ModelSerializer):
                class Meta:
                    model = Thing
                    fields = ["id", "name", "created_at", "updated_at", "deleted_at", "version"]
                    read_only_fields = ["id", "created_at", "updated_at", "deleted_at", "version"]

            class ThingViewSet(MixinViewSet):
                queryset = Thing.objects.all()
                serializer_class = ThingSerializer
                model_name = "product"

            with model_tables(Thing):
                viewset = ThingViewSet()
                viewset.get_serializer = lambda instance: ThingSerializer(instance)

                create_serializer = ThingSerializer(data={"name": "cookie"})
                assert create_serializer.is_valid(), create_serializer.errors

                with patch("apps._api.mixins.publish_handler") as publish_mock:
                    viewset.perform_create(create_serializer)

                created = Thing.objects.get()
                assert created.version == 1
                assert publish_mock.call_args.args[1] == "created"

                update_serializer = ThingSerializer(created, data={"name": "pie"})
                assert update_serializer.is_valid(), update_serializer.errors

                with patch("apps._api.mixins.publish_handler") as publish_mock:
                    viewset.perform_update(update_serializer)

                created.refresh_from_db()
                assert created.name == "pie"
                assert created.version == 2
                assert publish_mock.call_args.args[1] == "updated"

                with patch("apps._api.mixins.publish_handler") as publish_mock:
                    viewset.perform_destroy(created)

                assert created.deleted_at is not None
                assert Thing.objects.filter(pk=created.pk).exists() is False
                assert Thing.all_objects.filter(pk=created.pk).exists() is True
                assert publish_mock.call_args.args[1] == "deleted"


@pytest.mark.django_db(transaction=True)
class TestAdmin:
    class TestAdminPanel:
        @isolate_apps()
        def test_initializes_list_display_and_respects_active_state(self):
            class Thing(BaseModel):
                name = django_models.CharField(max_length=50)

                class Meta:
                    app_label = "api_tests"

            class ThingSerializer(serializers.ModelSerializer):
                class Meta:
                    model = Thing
                    fields = ["id", "name", "created_at", "updated_at", "deleted_at", "version"]

            class ThingAdmin(AdminPanel, admin.ModelAdmin):
                search_fields = ("name",)
                list_display = ("__str__",)
                model_name = "product"
                model_class = Thing
                serializer_class = ThingSerializer

            with model_tables(Thing):
                admin_instance = ThingAdmin(Thing, AdminSite())

                assert admin_instance.list_display == ("id", "name", "is_active")

                thing = Thing.objects.create(name="cookie")
                assert admin_instance.is_active(thing) is True

                thing.delete()
                assert admin_instance.is_active(thing) is False

        @isolate_apps()
        def test_soft_delete_and_restore_actions_publish_events(self):
            class Thing(BaseModel):
                name = django_models.CharField(max_length=50)

                class Meta:
                    app_label = "api_tests"

            class ThingSerializer(serializers.ModelSerializer):
                class Meta:
                    model = Thing
                    fields = ["id", "name", "created_at", "updated_at", "deleted_at", "version"]

            class ThingAdmin(AdminPanel, admin.ModelAdmin):
                search_fields = ("name",)
                list_display = ("__str__",)
                model_name = "product"
                model_class = Thing
                serializer_class = ThingSerializer

            with model_tables(Thing):
                admin_instance = ThingAdmin(Thing, AdminSite())
                request = RequestFactory().post("/admin/")
                thing = Thing.objects.create(name="cookie")

                with patch("apps._api.admin.publish_handler") as publish_mock:
                    admin_instance.deactivate_selected(request, [thing])

                thing.refresh_from_db()
                assert thing.deleted_at is not None
                assert publish_mock.call_args.args[1] == "deleted"

                with patch("apps._api.admin.publish_handler") as publish_mock:
                    admin_instance.activate_selected(request, [thing])

                thing.refresh_from_db()
                assert thing.deleted_at is None
                assert publish_mock.call_args.args[1] == "created"

        @isolate_apps()
        def test_save_and_delete_model_publish_events(self):
            class Thing(BaseModel):
                name = django_models.CharField(max_length=50)

                class Meta:
                    app_label = "api_tests"

            class ThingSerializer(serializers.ModelSerializer):
                class Meta:
                    model = Thing
                    fields = ["id", "name", "created_at", "updated_at", "deleted_at", "version"]

            class ThingAdmin(AdminPanel, admin.ModelAdmin):
                search_fields = ("name",)
                list_display = ("__str__",)
                model_name = "product"
                model_class = Thing
                serializer_class = ThingSerializer

            with model_tables(Thing):
                admin_instance = ThingAdmin(Thing, AdminSite())
                request = RequestFactory().post("/admin/")
                thing = Thing.objects.create(name="cookie")
                thing.name = "pie"

                with patch("apps._api.admin.publish_handler") as publish_mock:
                    admin_instance.save_model(request, thing, form=None, change=True)

                thing.refresh_from_db()
                assert thing.version == 2
                assert thing.name == "pie"
                assert publish_mock.call_args.args[1] == "updated"

                with patch("apps._api.admin.publish_handler") as publish_mock:
                    admin_instance.delete_model(request, thing)

                assert Thing.all_objects.filter(pk=thing.pk).exists() is False
                assert publish_mock.call_args.args[1] == "deleted"
