from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.db import transaction
from django.utils.crypto import get_random_string
from rest_framework import serializers

from apps.mail.mails import send_mail
from project.config import config

from . import models


def _basic_fields(*args: str) -> list[str]:
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


def _check_profile(request):
    """Helper function to check if the request has an authenticated user with a profile. Raises a ValidationError if not."""

    if not request or not request.user or not hasattr(request.user, "profile"):
        raise serializers.ValidationError(
            {"store": "Authenticated user with a store profile is required."}
        )


class NestedMixin:
    """Mixin to create/update models with a nested object in DRF serializers.

    Use it in serializers that accept a nested field (e.g. `establishment`) and
    need to create or update that related model along with the main one.
    Requirements: define `nested_field` and `nested_model`, and inherit from
    `serializers.ModelSerializer` so `update()` exists.
    """

    nested_field: str
    nested_model: type[models.BaseModel]

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


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        fields = ["id", "username", "email", "password", "first_name", "last_name"]
        read_only_fields = ["id"]


class ProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(write_only=True, required=False)
    email = serializers.EmailField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = models.Profile
        fields = _basic_fields("user", "establishment", "role", "username", "email")
        read_only_fields = _basic_fields("user")

    def _find_establishment_relationship(self, data, key, serializer_class, instance):
        try:
            related_instance = getattr(instance.establishment, key)
            data[key] = serializer_class(related_instance).data
        except (models.Store.DoesNotExist, models.Factory.DoesNotExist):
            data[key] = None

    def _check_integrity(self, username, email):
        if not username:
            raise serializers.ValidationError({"username": "Username is required."})

        if username and models.Profile.objects.filter(user__username=username).exists():
            raise serializers.ValidationError({"username": "Username is already in use."})

        if not email:
            raise serializers.ValidationError({"email": "Email is required."})

        if email and models.Profile.objects.filter(user__email=email).exists():
            raise serializers.ValidationError({"email": "Email is already in use."})

    @transaction.atomic
    def create(self, validated_data):
        username = validated_data.pop("username")
        email = validated_data.pop("email")
        role = validated_data.get("role")

        self._check_integrity(username, email)

        if not username:
            raise serializers.ValidationError({"username": "Username is required."})

        new_user = User.objects.create(username=username, email=email)
        password = get_random_string(length=8)
        new_user.set_password(password)
        new_user.groups.add(Group.objects.get(name=role.capitalize() + " manager"))
        new_user.save()

        profile = models.Profile.objects.create(user=new_user, **validated_data)
        send_mail(
            template="welcome.html",
            ctx={
                "user_display_name": new_user.first_name or new_user.username,
                "temporary_password": password,
                "login_url": config.DEFAULT_FRONTEND,
            },
            subject="¡Bienvenido a Galletas Juanita!",
            to=[email],
        )

        return profile

    def to_representation(self, instance):
        res = super().to_representation(instance)

        res["user"] = UserSerializer(instance.user).data
        self._find_establishment_relationship(res, "store", StoreSerializer, instance)
        self._find_establishment_relationship(res, "factory", FactorySerializer, instance)

        return res


class EstablishmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Establishment
        fields = _basic_fields("name", "municipality", "neighborhood", "street", "number")
        read_only_fields = _basic_fields()

    def validate_name(self, value: str) -> str:
        return _unique_name_validator(models.Establishment, self.instance, value)

    def to_representation(self, instance):
        res = super().to_representation(instance)
        if hasattr(instance, "factory"):
            res["type"] = "factory"
        elif hasattr(instance, "store"):
            res["type"] = "store"
        else:
            res["type"] = None

        return res


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


class ProductSerializer(PublicMixin, serializers.ModelSerializer):
    public_fields = {"name", "img"}

    class Meta:
        model = models.Product
        fields = _basic_fields("sku", "name", "price", "img")
        read_only_fields = _basic_fields()

    def to_internal_value(self, data):
        if hasattr(data, "_mutable"):
            data._mutable = True

        if "img" in data and not data["img"]:
            data.pop("img")

        return super().to_internal_value(data)

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


class StatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Status
        fields = _basic_fields("name", "description")
        read_only_fields = _basic_fields()

    def validate_name(self, value: str) -> str:
        return _unique_name_validator(models.Status, self.instance, value)


class DeliverySerializer(serializers.ModelSerializer):
    package = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False,
    )

    class Meta:
        model = models.Delivery
        fields = _basic_fields("store", "factory", "package")
        read_only_fields = _basic_fields("factory")

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
        request = self.context.get("request")
        _check_profile(request)
        validated_data["factory"] = request.user.profile.establishment.factory

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

    @transaction.atomic
    def update(self, instance, validated_data):
        package_data = validated_data.pop("package", None)
        instance = super().update(instance, validated_data)

        if package_data is None:
            return instance

        product_ids = [item["product"] for item in package_data]
        products_by_id = models.Product.objects.in_bulk(product_ids)
        missing = [
            str(product_id) for product_id in product_ids if product_id not in products_by_id
        ]
        if missing:
            raise serializers.ValidationError(
                {"package": f"Products not found: {', '.join(missing)}"}
            )

        models.Package.objects.filter(delivery=instance).delete()
        packages = [
            models.Package(
                delivery=instance,
                product=products_by_id[item["product"]],
                quantity=item["quantity"],
            )
            for item in package_data
        ]
        models.Package.objects.bulk_create(packages)

        return instance

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
        res["status"] = StatusSerializer(instance.status).data
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
    products = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False,
    )

    class Meta:
        model = models.Sell
        fields = _basic_fields("store", "date", "total", "products")
        read_only_fields = _basic_fields("store", "total")

    def validate_products(self, value):
        if self.instance is not None:
            return value

        if not value:
            raise serializers.ValidationError("At least one product is required.")

        seen_products = set()
        for item in value:
            if "product" not in item or "quantity" not in item:
                raise serializers.ValidationError("Each product must include product and quantity.")

            try:
                product_id = int(item["product"])
            except (TypeError, ValueError) as e:
                raise serializers.ValidationError("Product must be a valid id.") from e

            item["product"] = product_id
            if product_id in seen_products:
                raise serializers.ValidationError("Each product can appear only once.")
            seen_products.add(product_id)

            try:
                quantity = int(item["quantity"])
            except (TypeError, ValueError) as e:
                raise serializers.ValidationError("Product quantity must be a number.") from e

            if quantity <= 0:
                raise serializers.ValidationError("Product quantity must be greater than 0.")

        return value

    def _extract_from_inventory(self, store, products_data, products_by_id):
        product_ids = [item["product"] for item in products_data]
        inventory_by_product_id = {
            inventory_item.product_id: inventory_item
            for inventory_item in models.Inventory.objects.select_for_update()
            .filter(store=store, product_id__in=product_ids)
            .select_related("product")
        }

        insufficient_stock = []
        for item in products_data:
            product_id = item["product"]
            requested_quantity = int(item["quantity"])
            inventory_item = inventory_by_product_id.get(product_id)
            product_obj = products_by_id[product_id]

            if inventory_item is None:
                insufficient_stock.append(
                    {
                        "product": {"id": product_obj.id, "name": product_obj.name},
                        "available": 0,
                        "requested": requested_quantity,
                    }
                )
                continue

            if inventory_item.quantity < requested_quantity:
                insufficient_stock.append(
                    {
                        "product": {"id": product_obj.id, "name": product_obj.name},
                        "available": inventory_item.quantity,
                        "requested": requested_quantity,
                    }
                )

        if insufficient_stock:
            raise serializers.ValidationError({"products": insufficient_stock})

        for item in products_data:
            inventory_item = inventory_by_product_id[item["product"]]
            inventory_item.quantity -= int(item["quantity"])
            inventory_item.save(update_fields=["quantity"])

    def _sell(self, validated_data, products_data, products_by_id):
        total = Decimal("0.00")
        for item in products_data:
            product = products_by_id[item["product"]]
            quantity = int(item["quantity"])
            total += product.price * quantity

        sell = models.Sell.objects.create(total=total, **validated_data)
        details = [
            models.SellDetail(
                sell=sell,
                product=products_by_id[item["product"]],
                quantity=int(item["quantity"]),
                price=products_by_id[item["product"]].price,
            )
            for item in products_data
        ]
        models.SellDetail.objects.bulk_create(details)

        payment_method = models.PaymentMethod.objects.filter(name="cash").first()
        if payment_method is None:
            raise serializers.ValidationError(
                {"payment_method": "Default payment method 'cash' not found."}
            )

        models.Payment.objects.create(
            sell=sell,
            payment_method=payment_method,
            amount=total,
        )

        return sell

    @transaction.atomic
    def create(self, validated_data):
        request = self.context.get("request")
        _check_profile(request)

        validated_data["store"] = request.user.profile.establishment.store

        products_data = validated_data.pop("products", None)
        if not products_data:
            raise serializers.ValidationError({"products": "At least one product is required."})

        product_ids = [item["product"] for item in products_data]
        products_by_id = models.Product.objects.in_bulk(product_ids)
        missing = [
            str(product_id) for product_id in product_ids if product_id not in products_by_id
        ]
        if missing:
            raise serializers.ValidationError(
                {"products": f"Products not found: {', '.join(missing)}"}
            )

        self._extract_from_inventory(validated_data["store"], products_data, products_by_id)
        return self._sell(validated_data, products_data, products_by_id)

    def to_representation(self, instance):
        res = super().to_representation(instance)
        res["store"] = StoreSerializer(instance.store).data
        res["details"] = [
            SellDetailNestedSerializer(item).data for item in instance.selldetail_set.all()
        ]
        res["payments"] = [
            PaymentNestedSerializer(item).data for item in instance.payment_set.all()
        ]
        return res


class PaymentMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.PaymentMethod
        fields = _basic_fields("name")
        read_only_fields = _basic_fields()

    def validate_name(self, value: str) -> str:
        return _unique_name_validator(models.PaymentMethod, self.instance, value)


class SellDetailNestedSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.SellDetail
        fields = _basic_fields("product", "quantity", "price")
        read_only_fields = _basic_fields()

    def to_representation(self, instance):
        res = super().to_representation(instance)
        res["product"] = ProductSerializer(instance.product).data
        return res


class PaymentNestedSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Payment
        fields = _basic_fields("payment_method", "amount")
        read_only_fields = _basic_fields()

    def to_representation(self, instance):
        res = super().to_representation(instance)
        res["payment_method"] = PaymentMethodSerializer(instance.payment_method).data
        return res


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
