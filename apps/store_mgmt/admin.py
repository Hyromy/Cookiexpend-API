from django.contrib import admin

from apps._api.admin import AdminPanel

from . import models, serializers


@admin.register(models.Profile)
class ProfileAdmin(AdminPanel, admin.ModelAdmin):
    model_name = "profile"
    model_class = models.Profile
    serializer_class = serializers.ProfileSerializer

    search_fields = ("user__username", "user__email", "establishment__name")


@admin.register(models.Establishment)
class EstablishmentAdmin(AdminPanel, admin.ModelAdmin):
    model_name = "establishment"
    model_class = models.Establishment
    serializer_class = serializers.EstablishmentSerializer

    search_fields = ("name", "municipality", "neighborhood", "street", "number")


@admin.register(models.Factory)
class FactoryAdmin(AdminPanel, admin.ModelAdmin):
    model_name = "factory"
    model_class = models.Factory
    serializer_class = serializers.FactorySerializer

    search_fields = ("establishment__name",)


@admin.register(models.Store)
class StoreAdmin(AdminPanel, admin.ModelAdmin):
    model_name = "store"
    model_class = models.Store
    serializer_class = serializers.StoreSerializer

    search_fields = ("establishment__name",)


@admin.register(models.Product)
class ProductAdmin(AdminPanel, admin.ModelAdmin):
    model_name = "product"
    model_class = models.Product
    serializer_class = serializers.ProductSerializer

    search_fields = ("sku", "name", "price")


@admin.register(models.ProductImage)
class ProductImageAdmin(AdminPanel, admin.ModelAdmin):
    model_name = "product_image"
    model_class = models.ProductImage
    serializer_class = serializers.ProductImageSerializer

    search_fields = ("product__sku", "product__name")


@admin.register(models.Status)
class StatusAdmin(AdminPanel, admin.ModelAdmin):
    model_name = "status"
    model_class = models.Status
    serializer_class = serializers.StatusSerializer

    search_fields = ("name", "description")


@admin.register(models.Delivery)
class DeliveryAdmin(AdminPanel, admin.ModelAdmin):
    model_name = "delivery"
    model_class = models.Delivery
    serializer_class = serializers.DeliverySerializer

    search_fields = ("store__establishment__name", "factory__establishment__name", "status__name")


@admin.register(models.Inventory)
class InventoryAdmin(AdminPanel, admin.ModelAdmin):
    model_name = "inventory"
    model_class = models.Inventory
    serializer_class = serializers.InventorySerializer

    search_fields = ("store__establishment__name", "product__name", "quantity")


@admin.register(models.Sell)
class SellAdmin(AdminPanel, admin.ModelAdmin):
    model_name = "sell"
    model_class = models.Sell
    serializer_class = serializers.SellSerializer

    search_fields = ("store__establishment__name", "date", "total")


@admin.register(models.PaymentMethod)
class PaymentMethodAdmin(AdminPanel, admin.ModelAdmin):
    model_name = "payment_method"
    model_class = models.PaymentMethod
    serializer_class = serializers.PaymentMethodSerializer

    search_fields = ("name",)


@admin.register(models.Package)
class PackageAdmin(AdminPanel, admin.ModelAdmin):
    model_name = "package"
    model_class = models.Package
    serializer_class = serializers.PackageSerializer

    search_fields = ("delivery__store__establishment__name", "product__name", "quantity")


@admin.register(models.SellDetail)
class SellDetailAdmin(AdminPanel, admin.ModelAdmin):
    model_name = "sell_detail"
    model_class = models.SellDetail
    serializer_class = serializers.SellDetailSerializer

    search_fields = ("product__name", "sell__id", "quantity", "price")


@admin.register(models.Payment)
class PaymentAdmin(AdminPanel, admin.ModelAdmin):
    model_name = "payment"
    model_class = models.Payment
    serializer_class = serializers.PaymentSerializer

    search_fields = ("sell__id", "payment_method__name", "amount")
