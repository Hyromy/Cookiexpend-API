from rest_framework import viewsets
from rest_framework.permissions import AllowAny

from apps._catalog import models, serializers


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.Category.objects.all().order_by("order")
    serializer_class = serializers.CategorySerializer
    permission_classes = [AllowAny]


class PresentationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.Presentation.objects.all()
    serializer_class = serializers.PresentationSerializer
    permission_classes = [AllowAny]


class GaleriaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.GaleriaItem.objects.all()
    serializer_class = serializers.GaleriaItemSerializer
    permission_classes = [AllowAny]


class FAQViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.FAQ.objects.all()
    serializer_class = serializers.FAQSerializer
    permission_classes = [AllowAny]


class DepartmentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.Department.objects.all().prefetch_related("subjects")
    serializer_class = serializers.DepartmentSerializer
    permission_classes = [AllowAny]


class RetailerViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.Retailer.objects.all()
    serializer_class = serializers.RetailerSerializer
    permission_classes = [AllowAny]
