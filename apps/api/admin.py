from django.contrib import admin
from django.utils import timezone

from . import models, serializers
from .gossiper import (
    publish_handler,
)

source = "admin interface"


@admin.register(models.Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "price", "is_active", "created_at", "updated_at")
    search_fields = ("name",)
    list_filter = ("created_at", "updated_at")
    ordering = ("-created_at",)
    readonly_fields = ("version", "deleted_at", "created_at", "updated_at")
    actions = ("deactivate_selected", "activate_selected")
    change_form_template = "admin/api/product/change_form.html"

    def get_queryset(self, request):
        return models.Product.all_objects.get_queryset()

    @admin.display(boolean=True, description="Active")
    def is_active(self, obj: models.Product):
        return obj.deleted_at is None

    def save_model(self, request, obj: models.Product, form, change):
        if change:
            obj.version += 1

        super().save_model(request, obj, form, change)

        publish_handler(
            "product",
            "updated" if change else "created",
            serializers.ProductSerializer(obj).data,
            source,
        )

    def delete_model(self, request, obj: models.Product):
        publish_handler("product", "deleted", serializers.ProductSerializer(obj).data, source)
        obj.hard_delete()

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            publish_handler("product", "deleted", serializers.ProductSerializer(obj).data, source)
            obj.hard_delete()

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        if request.method == "POST" and object_id:
            obj = models.Product.all_objects.filter(pk=object_id).first()
            if obj is not None:
                if "_deactivate" in request.POST:
                    obj.delete()
                    publish_handler(
                        "product",
                        "deleted",
                        serializers.ProductSerializer(obj).data,
                        source,
                    )
                    self.message_user(request, "Product deactivated.")
                    return super().response_change(request, obj)

                if "_activate" in request.POST:
                    models.Product.all_objects.filter(pk=obj.pk).update(deleted_at=None)
                    obj.deleted_at = None
                    publish_handler(
                        "product",
                        "created",
                        serializers.ProductSerializer(obj).data,
                        source,
                    )
                    self.message_user(request, "Product activated.")
                    return super().response_change(request, obj)

        return super().changeform_view(request, object_id, form_url, extra_context)

    @admin.action(description="Deactivate selected products")
    def deactivate_selected(self, request, queryset):
        for obj in queryset:
            deleted_at = timezone.now()
            models.Product.all_objects.filter(pk=obj.pk).update(deleted_at=deleted_at)
            obj.deleted_at = deleted_at
            publish_handler("product", "deleted", serializers.ProductSerializer(obj).data, source)

    @admin.action(description="Activate selected products")
    def activate_selected(self, request, queryset):
        for obj in queryset:
            if obj.deleted_at is None:
                continue
            models.Product.all_objects.filter(pk=obj.pk).update(deleted_at=None)
            obj.deleted_at = None
            publish_handler("product", "created", serializers.ProductSerializer(obj).data, source)
