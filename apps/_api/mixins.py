from typing import Any

from django.db.models import QuerySet
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets

from apps._redis.gossiper import MODEL, publish_handler

from .models import BaseModel


class NestedMixin:
    """Mixin to create/update models with a nested object in DRF serializers.

    Use it in serializers that accept a nested field (e.g. `establishment`) and
    need to create or update that related model along with the main one.
    Requirements: define `nested_field` and `nested_model`, and inherit from
    `serializers.ModelSerializer` so `update()` exists.
    """

    nested_field: str
    nested_model: BaseModel

    def create_nested(self, validated_data):
        """Create the nested model first, then the main model."""

        nested_data = validated_data.pop(self.nested_field)
        nested_instance = self.nested_model.objects.create(**nested_data)
        return self.Meta.model.objects.create(
            **validated_data,
            **{self.nested_field: nested_instance},
        )

    def update_nested(self, instance, validated_data):
        """Update the nested model if provided and delegate the rest."""

        nested_data = validated_data.pop(self.nested_field, None)
        if nested_data:
            nested_instance = getattr(instance, self.nested_field)
            for attr, value in nested_data.items():
                setattr(nested_instance, attr, value)
            nested_instance.save()

        return super().update(instance, validated_data)


class PublicMixin:
    """
    Mixin to filter serializer fields based on user authentication status.
    If the user is not authenticated, only the fields specified in `public_fields` will be included
    in the serialized output.
    """

    public_fields: set[str]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.public_fields is None:
            return

        request = self.context.get("request")
        if request and (not request.user or not request.user.is_authenticated):
            for field_name in set(self.fields.keys()):
                if field_name not in self.public_fields:
                    self.fields.pop(field_name)


class MixinViewSet(viewsets.ModelViewSet):
    """Mixin viewset to handle common logic, publishing events to Redis on create, update, and delete operations."""

    model_name: MODEL

    filter_backends = [DjangoFilterBackend]

    SOURCE = "api request"

    def perform_create(self, serializer):
        """Override the default create behavior to publish an event after saving the new instance."""

        instance = serializer.save()
        instance.refresh_from_db()

        publish_handler(self.model_name, "created", self.get_serializer(instance).data, self.SOURCE)

    def perform_update(self, serializer):
        """Override the default update behavior to publish an event after saving the updated instance. Increment the version number on update."""

        instance = serializer.save()
        instance.version += 1
        instance.save()

        instance.refresh_from_db()

        publish_handler(self.model_name, "updated", self.get_serializer(instance).data, self.SOURCE)

    def perform_destroy(self, instance):
        """Override the default destroy behavior to publish an event before deleting the instance. Include the instance data in the event payload before deletion."""

        data = self.get_serializer(instance).data
        instance.delete()

        publish_handler(self.model_name, "deleted", data, self.SOURCE)

    def get_self_queryset(
        self,
        *,
        model: BaseModel,
        queryset_select_related_fields: list[str],
        filter_group_to_all: dict[str, Any],
        filter_group_to_self: dict[str, Any],
        filter_query: str,
    ) -> QuerySet:
        """
        Helper method to return a queryset filtered based on the user's permissions. If the user belongs
        to the group specified in filter_group_to_all, they can see all records. If they belong to the
        group specified in filter_group_to_self, they can only see records related to their establishment.
        Otherwise, they cannot see any records.
        """

        user = self.request.user

        if not user or user.is_anonymous:
            return model.objects.none()

        queryset = model.objects.select_related(*queryset_select_related_fields)

        if user.is_superuser or user.is_staff or user.groups.filter(**filter_group_to_all).exists():
            return queryset.all()

        if user.groups.filter(**filter_group_to_self).exists():
            if hasattr(user, "profile") and user.profile.establishment:
                user_establishment_id = user.profile.establishment.id
                return queryset.filter(
                    **{f"{filter_query}__establishment_id": user_establishment_id}
                )

            return model.objects.none()

        return model.objects.none()
