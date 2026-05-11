from rest_framework import serializers

from .models import (
    Product,
)


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ["id", "name", "description", "price", "created_at", "updated_at", "version"]
        read_only_fields = ["id", "created_at", "updated_at", "version"]

    def validate_name(self, value: str) -> str:
        queryset = Product.objects.filter(name=value)
        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("A product with this name already exists.")
        return value
