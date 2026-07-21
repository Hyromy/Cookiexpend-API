from django.contrib import admin
from django.utils.timezone import now

from apps._redis.gossiper import (
    MODEL,
    publish_handler,
)

SOURCE = "admin interface"


class AdminPanel:
    """
    Base admin panel with soft delete and publish capabilities.

    To use, inherit from this class and set the following attributes:

    - `model_name`: A string representing the model name for publishing.
    - `model_class`: The Django model class associated with this admin.
    - `serializer_class`: The DRF serializer class for the model, used for publishing data.
    """

    list_filter = ("created_at", "updated_at")
    ordering = ("-created_at",)
    readonly_fields = ("version", "deleted_at", "created_at", "updated_at")
    actions = ("deactivate_selected", "activate_selected")
    change_form_template = "change_form.html"

    model_name: MODEL = None
    model_class = None
    serializer_class = None

    def __init__(self, model, admin_site):
        super().__init__(model, admin_site)

        if self.list_display == ("__str__",):
            self.list_display = self._table_display(*self._args(self.search_fields))

    def _can_publish(self) -> bool:
        """Check if the necessary attributes for publishing are set."""

        return self.model_name and self.model_class and self.serializer_class

    def _table_display(self, *args) -> tuple[str]:
        """Helper method to create list_display with an 'is_active' status column."""

        return tuple(["id"] + list(args) + ["is_active"])

    def _args(self, args) -> tuple[str]:
        """Helper method to extract base field names from search_fields for list_display."""

        return (i.split("__")[0] for i in args)

    @admin.display(boolean=True, description="Active")
    def is_active(self, obj):
        """Display whether the object is active."""

        return obj.deleted_at is None

    @admin.action(description="Deactivate selected products")
    def deactivate_selected(self, request, queryset):
        """Soft delete selected objects and publish the deletion event."""

        for obj in queryset:
            deleted_at = now()
            type(obj).all_objects.filter(pk=obj.pk).update(deleted_at=deleted_at)
            obj.deleted_at = deleted_at

            if self._can_publish():
                publish_handler(self.model_name, "deleted", self.serializer_class(obj).data, SOURCE)

    @admin.action(description="Activate selected products")
    def activate_selected(self, request, queryset):
        """Activate selected objects and publish the creation event."""

        for obj in queryset:
            if obj.deleted_at is None:
                continue

            type(obj).all_objects.filter(pk=obj.pk).update(deleted_at=None)
            obj.deleted_at = None

            if self._can_publish():
                publish_handler(self.model_name, "created", self.serializer_class(obj).data, SOURCE)

    def get_queryset(self, request):
        """Override to include soft-deleted objects in the queryset for admin actions."""

        return self.model_class.all_objects.all()

    def save_model(self, request, obj, form, change):
        """Override to publish creation and update events, and to increment version on updates."""

        if change:
            obj.version += 1

        super().save_model(request, obj, form, change)

        if self._can_publish():
            publish_handler(
                self.model_name,
                "updated" if change else "created",
                self.serializer_class(obj).data,
                SOURCE,
            )

    def delete_model(self, request, obj):
        """Hard delete the object and publish the deletion event."""

        if self._can_publish():
            publish_handler(self.model_name, "deleted", self.serializer_class(obj).data, SOURCE)

        obj.hard_delete()

    def delete_queryset(self, request, queryset):
        """Hard delete the objects in the queryset and publish deletion events."""

        for obj in queryset:
            if self._can_publish():
                publish_handler(self.model_name, "deleted", self.serializer_class(obj).data, SOURCE)

            obj.hard_delete()

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        """Override to handle activation and deactivation from the change form view."""

        if request.method == "POST" and object_id:
            obj = self.model_class.all_objects.filter(pk=object_id).first()
            if obj is not None:
                if "_deactivate" in request.POST:
                    obj.delete()
                    if self._can_publish():
                        publish_handler(
                            self.model_name,
                            "deleted",
                            self.serializer_class(obj).data,
                            SOURCE,
                        )
                    self.message_user(request, f"{self.model_name.capitalize()} deactivated.")
                    return super().response_change(request, obj)

                if "_activate" in request.POST:
                    self.model_class.all_objects.filter(pk=obj.pk).update(deleted_at=None)
                    obj.deleted_at = None
                    publish_handler(
                        self.model_name,
                        "created",
                        self.serializer_class(obj).data,
                        SOURCE,
                    )
                    self.message_user(request, f"{self.model_name.capitalize()} activated.")
                    return super().response_change(request, obj)

        return super().changeform_view(request, object_id, form_url, extra_context)
