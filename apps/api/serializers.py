from django.db import transaction
from rest_framework import serializers

from . import models


def _basic_fields(*args) -> list[str]:
    """Helper function to generate basic fields for serializers, including id, created_at, updated_at, and version."""

    return ["id"] + list(args) + ["created_at", "updated_at", "version"]


def _unique_name_validator(model_class, instance, value):
    """Helper function to validate that the name field is unique among active (not soft-deleted) instances of the model."""

    queryset = model_class.objects.filter(name=value)
    if instance is not None:
        queryset = queryset.exclude(pk=instance.pk)

    if queryset.exists():
        raise serializers.ValidationError(
            f"A {model_class._meta.verbose_name} with this name already exists."
        )

    return value


class NestedMixin:
    nested_field: str
    nested_model: type[models.BaseModel]

    def create_nested(self, validated_data):
        nested_data = validated_data.pop(self.nested_field)
        nested_instance = self.nested_model.objects.create(**nested_data)
        return self.Meta.model.objects.create(
            **validated_data,
            **{self.nested_field: nested_instance},
        )

    def update_nested(self, instance, validated_data):
        nested_data = validated_data.pop(self.nested_field, None)
        if nested_data:
            nested_instance = getattr(instance, self.nested_field)
            for attr, value in nested_data.items():
                setattr(nested_instance, attr, value)
            nested_instance.save()

        return super().update(instance, validated_data)


class EstablishmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Establishment
        fields = _basic_fields("name", "municipality", "neighborhood", "street", "number")
        read_only_fields = _basic_fields()

    def validate_name(self, value: str) -> str:
        return _unique_name_validator(models.Establishment, self.instance, value)


class FactorySerializer(NestedMixin, serializers.ModelSerializer):
    establishment = EstablishmentSerializer()

    nested_field = "establishment"
    nested_model = models.Establishment

    class Meta:
        model = models.Factory
        fields = _basic_fields("establishment")
        read_only_fields = _basic_fields()

    def to_representation(self, instance):
        res = super().to_representation(instance)
        res["establishment"] = EstablishmentSerializer(instance.establishment).data
        return res

    def create(self, validated_data):
        return self.create_nested(validated_data)

    def update(self, instance, validated_data):
        return self.update_nested(instance, validated_data)


class StoreSerializer(NestedMixin, serializers.ModelSerializer):
    establishment = EstablishmentSerializer()

    nested_field = "establishment"
    nested_model = models.Establishment

    class Meta:
        model = models.Store
        fields = _basic_fields("establishment")
        read_only_fields = _basic_fields()

    def to_representation(self, instance):
        res = super().to_representation(instance)
        res["establishment"] = EstablishmentSerializer(instance.establishment).data
        return res

    def create(self, validated_data):
        return self.create_nested(validated_data)

    def update(self, instance, validated_data):
        return self.update_nested(instance, validated_data)


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Product
        fields = _basic_fields("name", "price")
        read_only_fields = _basic_fields()

    def validate_name(self, value: str) -> str:
        return _unique_name_validator(models.Product, self.instance, value)


class PackageSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Package
        fields = _basic_fields("delivery", "product", "quantity")
        read_only_fields = _basic_fields()

    def to_representation(self, instance):
        res = super().to_representation(instance)
        res["delivery"] = DeliverySerializer(instance.delivery).data
        res["product"] = ProductSerializer(instance.product).data
        return res


class DeliverySerializer(serializers.ModelSerializer):
    package = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=True,
    )

    class Meta:
        model = models.Delivery
        fields = _basic_fields("store", "factory", "package")
        read_only_fields = _basic_fields()

    def validate_package(self, value):
        if not value:
            raise serializers.ValidationError("At least one package is required.")

        for item in value:
            if "product" not in item or "quantity" not in item:
                raise serializers.ValidationError("Each package must include product and quantity.")
            if item["quantity"] is None or int(item["quantity"]) <= 0:
                raise serializers.ValidationError("Package quantity must be greater than 0.")

        return value

    @transaction.atomic
    def create(self, validated_data):
        package_data = validated_data.pop("package")
        delivery = models.Delivery.objects.create(**validated_data)
        packages = []

        for item in package_data:
            product = models.Product.objects.get(pk=item["product"])
            packages.append(
                models.Package(
                    delivery=delivery,
                    product=product,
                    quantity=item["quantity"],
                )
            )

        models.Package.objects.bulk_create(packages)
        return delivery

    def to_representation(self, instance):
        res = super().to_representation(instance)
        res["store"] = StoreSerializer(instance.store).data
        res["factory"] = FactorySerializer(instance.factory).data
        res["package"] = [
            {
                "product": ProductSerializer(item.product).data,
                "quantity": item.quantity,
            }
            for item in instance.package_set.all()
        ]
        return res


class InventorySerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Inventory
        fields = _basic_fields("store", "product", "quantity")
        read_only_fields = _basic_fields()

    def to_representation(self, instance):
        res = super().to_representation(instance)
        res["store"] = StoreSerializer(instance.store).data
        res["product"] = ProductSerializer(instance.product).data
        return res


class SellSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Sell
        fields = _basic_fields("store", "date", "total")
        read_only_fields = _basic_fields()

    def to_representation(self, instance):
        res = super().to_representation(instance)
        res["store"] = StoreSerializer(instance.store).data
        return res


class PaymentMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.PaymentMethod
        fields = _basic_fields("name")
        read_only_fields = _basic_fields()

    def validate_name(self, value: str) -> str:
        return _unique_name_validator(models.PaymentMethod, self.instance, value)


class SellDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.SellDetail
        fields = _basic_fields("sell", "product", "quantity", "price")
        read_only_fields = _basic_fields()

    def to_representation(self, instance):
        res = super().to_representation(instance)
        res["sell"] = SellSerializer(instance.sell).data
        res["product"] = ProductSerializer(instance.product).data
        return res


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Payment
        fields = _basic_fields("sell", "payment_method", "amount")
        read_only_fields = _basic_fields()

    def to_representation(self, instance):
        res = super().to_representation(instance)
        res["sell"] = SellSerializer(instance.sell).data
        res["payment_method"] = PaymentMethodSerializer(instance.payment_method).data
        return res
