from rest_framework import serializers

from apps.catalog import models


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Category
        fields = ["id", "label", "order", "logo"]


class PresentationSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Presentation
        fields = ["id", "label", "order"]


class GaleriaItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.GaleriaItem
        fields = ["id", "url", "alt", "order"]


class FAQSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.FAQ
        fields = ["id", "question", "answer", "order"]


class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Subject
        fields = ["id", "label", "order"]


class DepartmentSerializer(serializers.ModelSerializer):
    subjects = SubjectSerializer(many=True, read_only=True)

    class Meta:
        model = models.Department
        fields = ["id", "name", "order", "subjects"]


class BrandSerializer(serializers.ModelSerializer):
    logo_url = serializers.ImageField(source="logo", read_only=True)

    class Meta:
        model = models.Brand
        fields = ["id", "name", "logo_url"]


class RetailerSerializer(serializers.ModelSerializer):
    brand = BrandSerializer(read_only=True)

    class Meta:
        model = models.Retailer
        fields = ["id", "name", "address", "state", "municipality", "lat", "lng", "brand"]


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
