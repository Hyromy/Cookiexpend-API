from rest_framework import serializers

from apps._api.mixins import PublicMixin
from apps.catalog import models


def _unique_active_field_validator(model_class, instance, field_name, value):
    """Validate that `field_name` is unique among active (not soft-deleted) instances of the model."""

    queryset = model_class.objects.filter(**{field_name: value})
    if instance is not None:
        queryset = queryset.exclude(pk=instance.pk)

    if queryset.exists():
        raise serializers.ValidationError(
            f"A {model_class._meta.verbose_name} with this {field_name} already exists."
        )

    return value


def _drop_empty_file(data, field_name):
    """Drop an empty uploaded file from the payload so a PATCH without a new file doesn't clear it."""

    if hasattr(data, "_mutable"):
        data._mutable = True

    if field_name in data and not data[field_name]:
        data.pop(field_name)

    return data


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Category
        fields = ["id", "label", "order", "logo"]

    def to_internal_value(self, data):
        return super().to_internal_value(_drop_empty_file(data, "logo"))

    def validate_label(self, value: str) -> str:
        return _unique_active_field_validator(models.Category, self.instance, "label", value)


class PresentationSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Presentation
        fields = ["id", "label", "order"]

    def validate_label(self, value: str) -> str:
        return _unique_active_field_validator(models.Presentation, self.instance, "label", value)


class GalleryItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.GalleryItem
        fields = ["id", "url", "alt", "order"]

    def to_internal_value(self, data):
        return super().to_internal_value(_drop_empty_file(data, "url"))


class FAQSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.FAQ
        fields = ["id", "question", "answer", "order"]


class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Subject
        fields = ["id", "label", "department", "order"]


class DepartmentSerializer(PublicMixin, serializers.ModelSerializer):
    subjects = serializers.SerializerMethodField()

    # `email` is only used server-side to route contact messages (see the `contact`
    # action) and must stay hidden from anonymous storefront visitors.
    public_fields = {"id", "name", "order", "subjects"}

    class Meta:
        model = models.Department
        fields = ["id", "name", "email", "order", "subjects"]

    def get_subjects(self, instance) -> list:
        return SubjectSerializer(instance.subjects.filter(deleted_at__isnull=True), many=True).data


class BrandSerializer(serializers.ModelSerializer):
    logo_url = serializers.ImageField(source="logo", read_only=True)

    class Meta:
        model = models.Brand
        fields = ["id", "name", "logo", "logo_url"]
        extra_kwargs = {"logo": {"write_only": True, "required": False}}

    def to_internal_value(self, data):
        return super().to_internal_value(_drop_empty_file(data, "logo"))


class RetailerSerializer(serializers.ModelSerializer):
    logo_url = serializers.ImageField(source="logo", read_only=True)

    class Meta:
        model = models.Retailer
        fields = [
            "id", "name", "address", "state", "municipality", "lat", "lng",
            "brand", "logo", "logo_url",
        ]
        extra_kwargs = {"logo": {"write_only": True, "required": False}}

    def to_internal_value(self, data):
        return super().to_internal_value(_drop_empty_file(data, "logo"))

    def to_representation(self, instance):
        res = super().to_representation(instance)
        res["brand"] = BrandSerializer(instance.brand, context=self.context).data if instance.brand_id else None
        return res


class ContactMessageSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True, default="")
    city = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    subject = serializers.PrimaryKeyRelatedField(queryset=models.Subject.objects.all())
    message = serializers.CharField(max_length=2000)

    def validate_subject(self, value):
        department = self.context["department"]
        if value.department_id != department.id:
            raise serializers.ValidationError("Subject does not belong to this department.")
        return value
