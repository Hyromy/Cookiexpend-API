from rest_framework import serializers

from apps._catalog import models


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


class RetailerSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Retailer
        fields = ["id", "name", "address", "state", "municipality", "lat", "lng"]
